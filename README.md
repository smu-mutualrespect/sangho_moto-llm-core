# moto-llm-core

`moto`의 미구현 AWS API 경로를 허니팟 응답기로 전환하기 위한 LLM fallback 실험 저장소다. 지금 상태는 단순한 `"llm_fallback!!"` 수준을 넘어서, `single agent -> response plan -> shape adapter -> protocol renderer -> validator` 흐름으로 응답을 생성하고, 기본 경로는 direct OpenAI Responses API 또는 Anthropic Claude Messages API 호출이다.

## 이번에 바꾼 것

이번 작업은 크게 세 축이다.

1. 구조 변경
- LLM이 최종 JSON/XML body를 직접 쓰지 않게 바꿨다.
- 대신 `ResponsePlan`만 만들고, 실제 응답 shape 채우기와 protocol 직렬화는 코드가 담당한다.
- 이 구조 덕분에 malformed 응답이 줄고, 모델이 흔들려도 core field를 보호할 수 있게 됐다.

2. 범용 응답기 강화
- 요청 body를 정규화해서 `request_params`, `target_identifiers`, `body_format`을 읽도록 바꿨다.
- AWS service model output shape를 재귀적으로 읽어 structure/list/string/timestamp를 채우는 `shape_adapter`를 넣었다.
- `validator`에 empty success, unsafe URL, world-state mismatch 같은 품질 가드를 추가했다.
- `response_plan` 단계에서 핵심 field omit 금지, 빈 reconnaissance 응답 금지 같은 안정화 로직을 넣었다.

3. 실제 모델 경로 연결 및 튜닝
- `provider.py`에 OpenAI Responses API와 Anthropic Claude Messages API wrapper를 두고, `.env`에 있는 키 기준으로 provider를 자동 선택하게 했다.
- `TUNING_PLAN.md`, `artifacts/tuning/command_corpus.json`, `scripts/run_honeypot_tuning_batches.py`를 추가해서 50개 공격성 높은 명령 corpus를 batch로 돌릴 수 있게 했다.
- live 모델 호출 기준으로 튜닝하면서 timestamp 자연어 힌트, 공용 URL, account-id 불일치 ARN, 빈 SSM inventory 같은 문제를 잡았다.

## 핵심 파일

- `moto/core/llm_agents/agent.py`
  - fallback 전체 orchestration
- `moto/core/llm_agents/normalizer.py`
  - JSON/query 요청 파라미터 추출
- `moto/core/llm_agents/response_plan.py`
  - LLM 출력 plan 파싱 및 안정화
- `moto/core/llm_agents/shape_adapter.py`
  - service model shape 기반 payload 생성
- `moto/core/llm_agents/protocol_renderer.py`
  - AWS protocol 직렬화
- `moto/core/llm_agents/validator.py`
  - safety/quality/world-state 검증
- `moto/core/llm_agents/runtime/provider.py`
  - OpenAI / Claude 호출 및 `.env` 기반 provider 자동 선택
- `scripts/run_honeypot_tuning_batches.py`
  - tuning corpus batch runner

## LLM provider 설정

`.env`에 `OPENAI_API_KEY`가 있으면 OpenAI를 사용하고, OpenAI 키 없이 `ANTHROPIC_API_KEY`만 있으면 Claude를 자동으로 사용한다. 둘 다 있을 때 Claude를 강제로 쓰려면 `MOTO_LLM_PROVIDER=anthropic`을 넣으면 된다.

```bash
ANTHROPIC_API_KEY=sk-ant-...
MOTO_LLM_ANTHROPIC_MODEL=claude-sonnet-4-20250514
```

## 현재 응답 흐름

1. `moto`가 요청을 처리하다가 미구현/미매칭 경로로 빠진다.
2. `agent.py`가 요청을 canonical form으로 정규화한다.
3. LLM은 최종 body가 아니라 `response_plan`만 제안한다.
4. `shape_adapter.py`가 AWS output shape를 읽고 payload를 채운다.
5. `protocol_renderer.py`가 JSON/XML/query protocol로 직렬화한다.
6. `validator.py`가 safety와 품질을 검사한다.
7. 검증 실패 시 sparse regeneration 또는 safe fallback으로 내려간다.

## live tuning 결과

live API 실행으로 50개 공격성 높은 corpus를 5개씩 10 batch로 돌렸다.

- 1차 full run
  - 50 scenarios
  - 47 validation pass
  - 1 safe fallback
  - 0 `provider_call_failed`
  - 0 placeholder hit
- 이후 재튜닝
  - 자연어 timestamp hint 정규화
  - explicit ARN account/region 재작성
  - nested explicit hint type coercion
  - ECR `downloadUrl` safe decoy URL 치환
  - SSM `DescribeInstanceInformation` 최소 decoy 자산 강제
- 실패 batch 재실행 결과
  - `batch_3`: 5/5 pass
  - `batch_5`: 5/5 pass
  - `batch_7`: 5/5 pass

관련 기록:
- `TUNING_PLAN.md`
- `artifacts/tuning/tuning_log.md`
- `artifacts/tuning`

## 실제 API 10개 실측

아래 표는 `2026-04-16`에 로컬 server mode로 `http://127.0.0.1:5001`에 실제 요청을 보내서 측정한 결과다. 원본 전체 stdout/stderr는 `artifacts/runtime_cli_10_results.json`에 저장했다.

서버 실행 예시:

```bash
PYTHONPATH=. \
MOTO_LLM_ENV_FILE=.env \
python3 -m moto.server -H 127.0.0.1 -p 5001
```

CLI 실행 환경:

```bash
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_DEFAULT_REGION=us-east-1
AWS_EC2_METADATA_DISABLED=true
```

| # | Command | Return | Time (ms) | Response summary |
| --- | --- | --- | ---: | --- |
| 1 | `aws --endpoint-url=http://127.0.0.1:5001 ssm describe-instance-information` | 0 | 23397.916 | `InstanceInformationList`에 Linux managed instance 2개 반환 |
| 2 | `aws --endpoint-url=http://127.0.0.1:5001 ecr batch-check-layer-availability --repository-name demo --layer-digests sha256:abc` | 0 | 26143.260 | `layers=[]`, `failures=[InvalidLayerDigest]` |
| 3 | `aws --endpoint-url=http://127.0.0.1:5001 ecr get-download-url-for-layer --repository-name demo --layer-digest sha256:abc` | 0 | 24105.275 | `downloadUrl=mock://ecr/demo/blobs/sha256/abc`, `layerDigest=sha256:abc` |
| 4 | `aws --endpoint-url=http://127.0.0.1:5001 ecr initiate-layer-upload --repository-name demo` | 0 | 19023.771 | `uploadId=demo-upload-51de7666`, `partSize=20971520` |
| 5 | `aws --endpoint-url=http://127.0.0.1:5001 ecr complete-layer-upload --repository-name demo --upload-id test --layer-digests sha256:abc` | 0 | 20281.045 | `registryId=123456789012`, `repositoryName=demo`, `uploadId=test`, `layerDigest=sha256:abc` |
| 6 | `aws --endpoint-url=http://127.0.0.1:5001 iam get-context-keys-for-principal-policy --policy-source-arn arn:aws:iam::123456789012:user/victim-admin` | 0 | 21047.315 | `ContextKeyNames=[]` |
| 7 | `aws --endpoint-url=http://127.0.0.1:5001 iam list-service-specific-credentials --user-name victim-admin` | 0 | 17349.547 | `ServiceSpecificCredentials=[]`, `IsTruncated=false` |
| 8 | `aws --endpoint-url=http://127.0.0.1:5001 iam generate-service-last-accessed-details --arn arn:aws:iam::123456789012:user/victim-admin` | 0 | 18097.830 | `JobId=job-51de7666` |
| 9 | `aws --endpoint-url=http://127.0.0.1:5001 secretsmanager validate-resource-policy --secret-id prod/db/password --resource-policy '{...}'` | 0 | 22720.226 | `PolicyValidationPassed=false`, wildcard principal/action 경고 1건 반환 |
| 10 | `aws --endpoint-url=http://127.0.0.1:5001 sts decode-authorization-message --encoded-message ZmFrZS1hdXRob3JpemF0aW9uLW1lc3NhZ2U=` | 0 | 21939.998 | `DecodedMessage`에 denial context JSON 반환 |

## 실측 응답 예시

### 1. `ssm describe-instance-information`

```json
{
  "InstanceInformationList": [
    {
      "InstanceId": "i-899ce78f30fc2789d",
      "PingStatus": "Online",
      "PlatformType": "Linux",
      "PlatformName": "Amazon Linux",
      "IamRole": "ReadOnlyOpsRole",
      "IPAddress": "10.42.3.151"
    }
  ]
}
```

### 3. `ecr get-download-url-for-layer`

```json
{
  "downloadUrl": "mock://ecr/demo/blobs/sha256/abc",
  "layerDigest": "sha256:abc"
}
```

### 9. `secretsmanager validate-resource-policy`

```json
{
  "PolicyValidationPassed": false,
  "ValidationErrors": [
    {
      "CheckName": "SECURITY_WARNING",
      "ErrorMessage": "This resource policy allows broad access via wildcard principal and action combination."
    }
  ]
}
```

## 지금 남은 한계

- latency는 아직 높다. 실측 10개가 대체로 17~26초 구간이다.
- 일부 IAM/list 계열은 shape-valid하지만 아직 sparse하다.
- `missing_echo` 기준으로 보면 일부 list/describe API는 attacker input을 더 자연스럽게 재반영할 여지가 있다.
- world-state continuity는 서비스 간 장기 세션 관점에서 더 보강할 수 있다.

## 다음 우선순위

1. list/describe 계열의 request-aware echo 보강
2. 서비스별 world-state consistency 확장
3. latency 절감
   - prompt 축소
   - shape hint 압축
   - fast-path heuristic 강화
4. fallback-safe-error 대신 sparse success regeneration 비율 확대
