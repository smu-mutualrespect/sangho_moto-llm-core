# 현재 상황 정리

작성 시점: 2026-04-12 KST

## 목표

`moto`가 처리하지 못하는 AWS CLI 요청을 LLM fallback으로 넘겨서, 허니팟/디셉션 목적에 맞는 AWS-like 응답을 생성하는 단일 agent 구조를 실험 중입니다.

핵심 방향은 다음과 같습니다.

- 먼저 단일 agent로 baseline을 만든다.
- OpenCode 호출과 direct API 호출을 비교한다.
- latency, 응답 품질, AWS CLI 파싱 성공 여부를 계속 로깅한다.
- 나중에 필요할 때만 orchestration 또는 sub-agent 구조로 확장한다.

## 현재 구조

### Moto fallback hook

fallback hook은 아래 경로에 들어가 있습니다.

- `moto/core/responses.py`
  - handler는 있지만 내부에서 `NotImplementedError`가 나는 경우
  - action 자체를 읽지 못하는 경우
  - action은 알지만 handler method가 없는 경우
- `moto/core/botocore_stubber.py`
  - AWS URL처럼 보이지만 Moto backend URL pattern과 매칭되지 않는 경우
- `moto/core/custom_responses_mock.py`
  - requests-mock의 마지막 catch-all 경로

fallback이 발생하면 요청 정보를 prompt 문자열로 만들고 `call_gpt_api(prompt)`를 호출합니다.

### 단일 agent prompt

단일 agent prompt는 아래 파일입니다.

- `moto/core/llm_agents/agent.md`

이 파일은 런타임 허니팟/디셉션 agent 지침입니다.

주요 규칙:

- AWS CLI caller에게 반환할 HTTP response body만 생성한다.
- 파일 읽기, 파일 수정, tool 실행, reasoning 설명을 하지 않는다.
- Moto, OpenCode, GPT, fallback, honeypot이라는 사실을 응답에 드러내지 않는다.
- 실제 credential, 실제 endpoint, 실제 account data를 반환하지 않는다.
- 정찰 API에는 sparse but plausible 응답을 반환한다.
- credential/privilege 관련 API에는 decoy metadata만 반환한다.
- 같은 입력이면 가능한 한 안정적인 응답을 주도록 한다.

### Provider layer

LLM 호출은 아래 파일에서 처리합니다.

- `moto/core/llm_agents/providers.py`

현재 `call_gpt_api()`는 transport만 선택합니다.

- `MOTO_LLM_OPENAI_TRANSPORT=opencode`
  - OpenCode CLI를 통해 `moto-fallback` agent 호출
- `MOTO_LLM_OPENAI_TRANSPORT=api`
  - OpenAI Responses API 직접 호출

두 경로 모두 같은 `agent.md` 지침을 공유합니다.

### OpenCode 설정

OpenCode 설정 파일은 아래입니다.

- `opencode.json`

현재 agent 이름은 `moto-fallback`입니다.

OpenCode 호출 예:

```bash
opencode run --agent moto-fallback --model openai/gpt-5.4 --variant fast ...
```

### `.env`

로컬 `.env`에는 실제 API key와 transport/model 설정을 둡니다.

현재 의도한 direct API 실험 설정:

```env
OPENAI_API_KEY=...
MOTO_LLM_OPENAI_TRANSPORT=api
MOTO_LLM_OPENAI_MODEL=gpt-5.4-nano
MOTO_LLM_OPENCODE_MODEL=openai/gpt-5.4
MOTO_LLM_OPENCODE_VARIANT=fast
```

`.env`와 `.env.*`는 `.gitignore`에 추가되어 있어 git에 올라가지 않습니다.

## LLM에 들어가는 입력

LLM 입력은 두 덩어리입니다.

1. `agent.md` 전체 지침
2. 현재 fallback 요청에 대한 runtime prompt

runtime prompt 예:

```text
Runtime Moto LLM fallback request.
Return only the HTTP response body for the AWS CLI caller. Do not edit files, do not run tools, do not wrap the answer in Markdown.

service=ecr
action=batch_check_layer_availability
url=...
headers=...
body=...
reason=...
source=responses.call_action.method_not_implemented
```

현재는 fallback이 발생한 단일 요청 중심으로만 들어갑니다. Moto native로 처리된 이전 명령어 흐름은 아직 LLM에 들어가지 않습니다.

## 서버 로그

LLM fallback이 실제로 호출되면 Moto 서버 터미널에 이런 로그가 찍힙니다.

direct API:

```text
[llm-fallback api start] service=ecr action=batch_check_layer_availability source=responses.call_action.method_not_implemented
[llm-fallback api done] service=ecr action=batch_check_layer_availability source=responses.call_action.method_not_implemented elapsed_ms=2119
```

OpenCode:

```text
[llm-fallback opencode start] service=ecr action=batch_check_layer_availability source=responses.call_action.method_not_implemented
[llm-fallback opencode done] service=ecr action=batch_check_layer_availability source=responses.call_action.method_not_implemented elapsed_ms=13624
```

## 실험 명령

README 기준으로 현재 fallback 실험 대상은 아래 명령들입니다.

```bash
aws --endpoint-url=http://127.0.0.1:5001 ecr batch-check-layer-availability --repository-name demo --layer-digests sha256:abc
aws --endpoint-url=http://127.0.0.1:5001 ecr get-download-url-for-layer --repository-name demo --layer-digest sha256:abc
aws --endpoint-url=http://127.0.0.1:5001 ecr initiate-layer-upload --repository-name demo
aws --endpoint-url=http://127.0.0.1:5001 ecr complete-layer-upload --repository-name demo --upload-id test --layer-digests sha256:abc
aws --endpoint-url=http://127.0.0.1:5001 ssm describe-instance-information
aws --endpoint-url=http://127.0.0.1:5001 iam create-service-specific-credential --user-name victim-admin --service-name codecommit.amazonaws.com
aws --endpoint-url=http://127.0.0.1:5001 iam get-context-keys-for-principal-policy --policy-source-arn arn:aws:iam::123456789012:user/victim-admin
aws --endpoint-url=http://127.0.0.1:5001 sts decode-authorization-message --encoded-message ZmFrZS1hdXRob3JpemF0aW9uLW1lc3NhZ2U=
aws --endpoint-url=http://127.0.0.1:5001 secretsmanager validate-resource-policy --secret-id prod/db/password --resource-policy '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":"*","Action":"secretsmanager:GetSecretValue","Resource":"*"}]}'
```

## latency 비교 결과

`fallback_response_log.md`에 상세 로그를 계속 누적하고 있습니다.

최근 비교 요약:

| 범위 | 모델/구조 | 성공률 | 평균 CLI latency | 평균 LLM latency | 요약 |
|---|---|---:|---:|---:|---|
| README 9개 전체 | OpenCode | 7/9 | 약 18.4초 | n/a | IAM/STS 일부 parse failure |
| README 9개 전체 | API nano, XML formatting 전 | 6/9 | 약 4.2초 | 약 1.7초 | 빠르지만 IAM/STS XML parse failure |
| README 9개 전체 | API nano, XML formatting 후 | 9/9 | 약 3.0초 | 약 2.2초 | IAM/STS parse failure 해결 |
| README 9개 전체 | API mini, XML formatting 후 | 9/9 | 약 4.0초 | 약 2.2초 | nano보다 CLI 평균은 느렸지만 SecretsManager 품질은 더 나음 |
| ECR 4개 + SSM 1개 | API nano, XML formatting 후 | 5/5 | 약 3.9초 | 약 2.0초 | 안정 JSON fallback 경로 유지 |

## 품질 상태

상대적으로 안정적인 명령:

- ECR 4개
  - `batch-check-layer-availability`
  - `get-download-url-for-layer`
  - `initiate-layer-upload`
  - `complete-layer-upload`
- SSM
  - `describe-instance-information`

주의가 필요한 명령:

- `secretsmanager validate-resource-policy`
  - API nano에서는 파싱은 성공하지만 `ValidationErrors` 품질이 낮아질 수 있습니다.
  - API mini는 이번 run에서 더 구체적인 validation error를 반환했습니다.
- IAM/STS 계열
  - protocol-aware XML formatting 이후 README 대상 3개 명령은 AWS CLI parse 성공으로 바뀌었습니다.
  - LLM이 credential-looking 값을 만들 수 있으므로 `ServicePassword`는 formatter에서 항상 redaction합니다.

현재 문제 예:

- `iam create-service-specific-credential`
  - XML wrapper + password redaction 적용됨
- `iam get-context-keys-for-principal-policy`
  - XML wrapper 적용됨
- `sts decode-authorization-message`
  - XML wrapper 적용됨

남은 문제는 파싱보다 응답 품질과 latency 편차입니다.

## 로그 파일

응답과 latency는 아래 파일에 계속 누적합니다.

- `fallback_response_log.md`

현재 컬럼:

- `Timestamp (KST)`
- `Command`
- `Handler`
- `Exit`
- `CLI elapsed ms`
- `LLM elapsed ms`
- `Result`

## GitHub push 상태

아래 repo의 `master` branch로 push 완료했습니다.

```text
git@github.com:smu-mutualrespect/sangho_moto-llm-core.git
```

마지막으로 push한 커밋:

```text
2f49cad93 Add protocol-aware LLM fallback formatting
```

참고:

- 처음 push는 fake AWS key 형태 문자열이 `fallback_response_log.md`에 있어서 GitHub push protection에 막혔습니다.
- 해당 값은 redaction 후 amend해서 push 성공했습니다.

## 아직 로컬에 남아 있는 변경

다음 파일은 이전부터 로컬에 남아 있었고, 의도적으로 push에 포함하지 않았습니다.

- `moto/core/llm_agents/PLAN.md`
  - untracked 설계 문서

최근 push한 내용:

- `moto/core/llm_fallback.py`
  - IAM/STS protocol-aware XML formatter 추가
  - `ServicePassword` redaction 강제
- `moto/core/responses.py`
  - fallback 응답에 formatter 연결
  - 중복 `return 200, headers, fallback_body` 1줄 제거
- `moto/core/botocore_stubber.py`
  - fallback 응답에 formatter 연결
- `moto/core/custom_responses_mock.py`
  - fallback 응답에 formatter 연결
- `fallback_response_log.md`
  - XML formatting 후 nano/mini latency 비교 결과 추가
- `CURRENT_STATUS.md`
  - 이 문서

## 다음에 할 일

1. 이전 Moto-native 명령 히스토리를 LLM prompt에 넣는 구조 설계
   - 예: 최근 10개 요청의 service/action/result 요약
   - 목적: 공격 흐름과 decoy 상태를 더 일관되게 만들기
2. ECR/SSM처럼 안정적인 JSON 서비스부터 품질 개선
3. IAM/STS는 protocol-aware XML/JSON wrapper를 별도로 처리
4. 같은 요청 반복 시 캐시를 넣어 latency 줄이기
5. `agent.md`를 더 짧게 줄여 token/latency 최적화
6. OpenCode와 direct API를 계속 같은 명령셋으로 비교
