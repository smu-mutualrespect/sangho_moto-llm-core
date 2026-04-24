# LLM Honeypot Runtime Report

## 1. 요약

이 저장소는 `moto`의 미구현 AWS API 처리 지점에 LLM 기반 허니팟 응답기를 붙이는 작업을 진행했다. 초기 상태는 "fallback이 걸리면 단순 문자열 또는 실험용 JSON을 반환"하는 수준이었고, 현재는 아래 흐름으로 바뀌었다.

1. 요청 정규화
2. 단일 agent가 `response plan` 생성
3. shape adapter가 AWS output shape를 채움
4. protocol renderer가 JSON/XML/query protocol로 직렬화
5. validator가 safety/quality/world-state를 검증
6. 필요 시 sparse regeneration 또는 safe fallback

또한 direct OpenAI Responses API 경로를 기본값으로 유지하면서, 필요할 때만 `opencode` transport를 쓰도록 분리했고, 공격자가 칠 법한 50개 명령 corpus를 batch로 돌려가며 튜닝했다.

## 2. 처음 상태와 문제점

처음 상태의 핵심 문제는 4가지였다.

1. LLM이 최종 응답 body를 직접 쓰려는 구조였다.
2. 서비스별 JSON/XML/query protocol 차이를 코드가 보장하지 못했다.
3. 요청 파라미터와 응답 필드의 연결이 약했다.
4. 모델 호출이 실패하면 fallback은 되더라도 허니팟 품질이 너무 낮았다.

이 구조로는 다음 문제가 반복된다.

- malformed JSON/XML
- 필수 field 누락
- 빈 객체 `{}` 같은 어색한 성공 응답
- 실측마다 흔들리는 값
- 서비스별 protocol mismatch

## 3. 어떻게 바꿨는지

### 3.1 fallback entrypoint 정리

변경 파일:
- `moto/core/responses.py`
- `moto/core/botocore_stubber.py`
- `moto/core/custom_responses_mock.py`
- `moto/core/llm_fallback.py`

변경 내용:
- `moto` 내부 여러 fallback 지점에서 직접 prompt를 만들고 provider를 호출하던 구조를 제거했다.
- 공통 entrypoint로 `handle_aws_request()`를 사용하게 정리했다.
- 즉, 이제 미구현 경로든 catch-all 경로든 모두 같은 runtime pipeline으로 흘러간다.

의미:
- fallback 동작이 한 군데로 모였다.
- 서비스별 동작 차이를 한 레이어에서 제어할 수 있게 됐다.

### 3.2 요청 정규화 레이어 추가

변경 파일:
- `moto/core/llm_agents/normalizer.py`

추가된 정보:
- `service`
- `operation`
- `request_params`
- `target_identifiers`
- `body_format`
- `principal_type`
- `probe_style`

예를 들어 아래 입력을 넣으면:

```bash
aws --endpoint-url=http://127.0.0.1:5001 ecr complete-layer-upload \
  --repository-name demo \
  --upload-id test \
  --layer-digests sha256:abc
```

정규화 단계에서 최소한 이런 정보가 뽑힌다.

- `repositoryName=demo`
- `uploadId=test`
- `layerDigest=sha256:abc`

의미:
- 모델이 단순히 `ecr`만 보고 막연한 응답을 하는 게 아니라, 실제 요청값과 이어진 응답을 낼 수 있다.

### 3.3 response plan 도입

변경 파일:
- `moto/core/llm_agents/response_plan.py`

핵심 아이디어:
- 모델은 최종 JSON/XML 문자열을 만들지 않는다.
- 대신 아래 같은 `ResponsePlan`만 만든다.

```json
{
  "mode": "success",
  "posture": "sparse",
  "entity_hints": {
    "instance_count": 2
  },
  "field_hints": {
    "PlatformType": "Linux"
  },
  "omit_fields": []
}
```

추가한 안정화 로직:
- `error_mode`와 `response_plan.mode` 분리
- 핵심 output field 보호
- 일부 reconnaissance API는 빈 응답 금지
- `downloadUrl` 같은 field는 unsafe 형태면 사전 치환

의미:
- 모델 자유도를 줄이고, 형식 제어권을 코드 쪽으로 가져왔다.

### 3.4 shape adapter 도입

변경 파일:
- `moto/core/llm_agents/shape_adapter.py`

역할:
- botocore service model output shape를 읽어 응답 payload를 생성한다.

현재 하는 일:
- `structure`, `list`, `map`, `string`, `boolean`, `integer`, `timestamp`를 재귀적으로 생성
- member 이름, enum, shape 이름, 입력 파라미터를 보고 plausible value 생성
- explicit hint가 shape 타입과 안 맞아도 coercion
- ARN/account/region consistency 유지
- timestamp 자연어 힌트를 ISO/epoch로 정규화

실제로 여기서 해결한 문제:
- `recent`
- `recent-ish but established`
- 잘못된 account id ARN
- `map<string,string>`에 list/dict가 들어가며 깨지는 케이스

의미:
- "허니팟 같은 값"은 유지하면서도 AWS serializer가 먹을 payload만 만들게 됐다.

### 3.5 protocol renderer 추가

변경 파일:
- `moto/core/llm_agents/protocol_renderer.py`
- `moto/core/llm_agents/renderer.py`

역할:
- shape adapter가 만든 Python object를 실제 wire format으로 직렬화한다.

지원 대상:
- JSON
- rest-json
- query
- XML 계열

의미:
- 모델이나 adapter는 형식이 아니라 데이터만 고민하면 된다.

### 3.6 validator 강화

변경 파일:
- `moto/core/llm_agents/validator.py`

추가한 검증:
- `{}` 같은 empty success 금지
- unsafe public URL 패턴 차단
- XML namespace 허용 예외 처리
- `DescribeInstanceInformation` 같은 operation의 핵심 member 확인
- world-state account lock mismatch 확인

실제로 막은 문제:
- `https://...` public URL을 그대로 내보내는 ECR 응답
- account id가 틀린 ARN
- `{}` 같은 쓸모없는 성공 응답

### 3.7 opencode transport 연결

변경 파일:
- `moto/core/llm_agents/providers.py`
- `moto/core/llm_agents/opencode_agent.md`
- `opencode.json`

추가 내용:
- `MOTO_LLM_OPENAI_TRANSPORT=opencode`
- `MOTO_LLM_OPENCODE_TIMEOUT`
- OpenCode JSON event 파싱
- `.env` 기반 실제 API key 로딩

의미:
- 단순 deterministic fallback이 아니라, 실제 live model로 실험 가능해졌다.

## 4. 튜닝 과정

추가 파일:
- `TUNING_PLAN.md`
- `artifacts/tuning/command_corpus.json`
- `scripts/run_honeypot_tuning_batches.py`
- `artifacts/tuning/tuning_log.md`

방식:
- 공격자가 칠 법한 50개 명령을 선정
- 5개씩 10 batch로 실행
- batch마다 summary와 audit 저장
- 문제점을 기록하고 rule/adapter/validator를 수정
- 실패 batch만 재실행

대표적으로 잡은 문제:

1. ECR download URL이 public `https://...` 형태로 나와 validator에 걸림
- 수정: `mock://ecr/...` decoy URL로 치환

2. SSM `DescribeInstanceInformation`이 빈 리스트를 반환
- 수정: 최소 1개 이상 decoy instance 강제

3. timestamp field에 자연어 힌트가 들어가 serializer 단계에서 실패
- 수정: shape-aware coercion 추가

4. ARN account id가 world-state와 달라 fallback으로 내려감
- 수정: explicit ARN rewrite 추가

5. nested field 타입이 흔들려 runtime exception 발생
- 수정: `string`/`boolean`/`integer`/`float` coercion 추가

## 5. 실측 결과

### 5.1 10개 실제 AWS CLI server mode 결과

측정 방식:
- `python3 -m moto.server -H 127.0.0.1 -p 5001`
- `MOTO_LLM_ENV_FILE=.env`
- `MOTO_LLM_OPENAI_TRANSPORT=opencode`
- 실제 AWS CLI로 `http://127.0.0.1:5001` 호출

결과 파일:
- `artifacts/runtime_cli_10_results.json`

집계:
- 평균: `21410.618ms`
- 중앙값: `21493.656ms`
- 최소: `17349.547ms`
- 최대: `26143.260ms`

즉 현재 체감 성능은:
- 평균 약 `21.41초`
- 보통 `17초 ~ 26초`

### 5.2 representative audit 기준 내부 지연

대표 audit를 보면 전체 지연의 대부분이 실제 모델 호출에 있다.

| Case | LLM duration | Total duration |
| --- | ---: | ---: |
| `ecr get-download-url-for-layer` | `17020.854ms` | `18480.848ms` |
| `ssm describe-instance-information` | `12100.958ms` | `14657.889ms` |
| `sts decode-authorization-message` | `7574.050ms` | `9305.350ms` |
| `ecr initiate-layer-upload` | `12170.332ms` | `13590.084ms` |

관찰:
- 보통 전체 시간의 대부분이 `LLM duration`
- 나머지는 prompt 구성, subprocess, shape adaptation, rendering, validation

## 6. 왜 느린가

현재 느린 이유는 한 가지가 아니라 5가지가 겹쳐 있다.

### 6.1 가장 큰 원인: 실제 모델 호출

지금은 `opencode`를 통해 실제 OpenAI API key를 사용한다. 따라서 요청 하나마다 네트워크 왕복 + 모델 추론 시간이 발생한다.

대표적으로:
- `17020ms`
- `12100ms`
- `7574ms`

이 구간만으로 이미 전체 지연의 대부분이 설명된다.

### 6.2 subprocess 비용

지금 OpenAI를 직접 SDK로 붙인 게 아니라 `opencode run ...` subprocess를 띄운다.

즉 요청마다:
- 프로세스 생성
- prompt 전달
- JSON event 스트림 파싱
- 종료

이 오버헤드가 붙는다.

이 경로는 구현은 편하지만 latency 면에서는 손해다.

### 6.3 prompt/context가 아직 크다

단순 명령 하나라도 지금은 다음 정보들이 같이 들어간다.

- canonical request
- target identifiers
- persona/prompt instruction
- output schema 힌트
- safety/shape 관련 제약

이건 품질에는 좋지만 토큰 수와 추론 시간을 늘린다.

### 6.4 shape-driven post-processing 비용

모델 응답 후에도 바로 끝나지 않는다.

후처리 단계:
- response plan 파싱
- shape adapter 재귀 생성
- protocol render
- safety validator
- 필요 시 regeneration/fallback

이건 모델 시간보다는 작지만, 몇 초 단위로 누적된다.

### 6.5 허니팟 품질을 위해 sparse보다 plausible 쪽으로 기울어 있음

단순히 빠르게 하려면 `{}` 또는 극단적으로 짧은 응답을 주면 된다. 하지만 지금은 공격자가 믿을 만한 decoy shape를 맞추려 하기 때문에:

- instance list
- uploadId
- layerDigest
- decoded message
- policy validation error

같은 구조를 실제로 채운다.

즉 latency와 deception quality를 맞바꾸고 있는 상태다.

## 7. 지금까지 무엇을 했는지 한 줄 요약

처음에는 `moto`의 미구현 API에서 그냥 LLM 문자열을 던지던 구조였고, 지금은 실제 요청 파라미터를 읽어 shape-safe payload를 만들고, `opencode`를 통한 live 모델 호출까지 붙여서 50개 corpus와 실제 10개 AWS CLI endpoint 실측으로 튜닝한 상태다.

## 8. 다음에 뭘 하면 빨라질까

우선순위는 이 순서가 맞다.

1. `opencode` subprocess 대신 direct OpenAI API fast path 추가
- subprocess 오버헤드 제거

2. prompt 축소
- operation family별 최소 prompt template 도입
- schema hint 길이 줄이기

3. heuristic short-circuit
- 일부 reconnaissance API는 model 호출 없이 deterministic path로 즉시 처리
- 예: `List*`, `Describe*` 중 단순 목록형

4. cache / memoization
- 동일 canonical request에 대해 같은 response plan 재사용

5. validator/regeneration 횟수 감소
- 지금은 quality를 위해 보수적으로 검사한다.
- pre-sanitization이 더 좋아지면 재시도 비용을 줄일 수 있다.

## 9. 현재 상태 평가

좋아진 점:
- malformed response 문제 대폭 감소
- 실제 HTTP server mode + AWS CLI end-to-end 검증 완료
- 실제 API key 경로까지 확인
- live `opencode` 기반 tuning loop 정착

아직 부족한 점:
- 평균 `21초`는 허니팟 runtime으로 느리다
- 일부 list/describe 응답은 아직 sparse하다
- world-state continuity는 더 강화할 수 있다
- artifact가 많아서 운영용과 연구용 산출물 분리가 필요하다

## 10. 참고 파일

- `README.md`
- `TUNING_PLAN.md`
- `artifacts/tuning/tuning_log.md`
- `artifacts/runtime_cli_10_results.json`
- `moto/core/llm_agents/agent.py`
- `moto/core/llm_agents/response_plan.py`
- `moto/core/llm_agents/shape_adapter.py`
- `moto/core/llm_agents/protocol_renderer.py`
- `moto/core/llm_agents/validator.py`
- `moto/core/llm_agents/providers.py`
