# Agentic Runtime 목표 문서

## 배경

현재 이 레포의 LLM fallback runtime은 두 경로로 나뉘어 있다.

- `workflow`: 기본 경로. LLM 출력값을 비교적 직접 파싱하고 serialize한다.
- `agentic`: agent에 가까운 경로. `response_plan`을 만들고, AWS output shape에 맞게 payload를 생성한 뒤 serialize, validate, retry를 수행한다.

목표는 이 이중 구조를 없애고, 단일 `agentic` runtime을 기본 실행 경로로 만드는 것이다. 단, 구조가 복잡해져서는 안 되며, 단일 agent의 단순성과 성능을 유지해야 한다.

## 최종 목표

Moto의 LLM fallback runtime을 기본적으로 단일 agentic runtime으로 동작하게 만든다.

agent는 실제 제한된 runtime agent처럼 아래 흐름으로 동작해야 한다.

1. 들어온 AWS 요청을 정규화한다.
2. session history와 world state를 읽는다.
3. 응답 계획인 `response_plan`을 만들거나 선택한다.
4. botocore output shape를 기준으로 plan을 payload로 변환한다.
5. 올바른 AWS protocol에 맞게 response body를 serialize한다.
6. parseability, protocol compatibility, safety, required core field를 검증한다.
7. 검증 실패 시 최대 1회만 재시도한다.
8. audit, latency, quality metadata를 남긴다.

AWS 응답 구조 검증 기준은 사용자가 지정한 AWS CLI Command Reference URL의 각 명령 `Output` 섹션과 같은 구조로 둔다.
참고 기준: https://docs.aws.amazon.com/cli/latest/reference/#cli-aws

따라서 benchmark는 parse/protocol/required field만 보지 말고, 아래를 모두 검증해야 한다.

1. 40개 benchmark command 각각에 대해 AWS CLI reference의 실제 command page URL을 찾는다.
2. command page의 `Output` 섹션이 현재 benchmark corpus의 service/operation과 같은 명령을 설명하는지 확인한다.
3. AWS CLI 문서의 `Output` 구조와 같은 botocore service model output shape를 기준으로 top-level field뿐 아니라 nested structure/list/map/scalar까지 재귀적으로 비교한다.
4. 문서 URL, service, operation, output shape 이름, 검증 결과를 artifact에 기록한다.
5. AWS CLI 문서와 botocore model이 불일치하거나, 문서 page를 찾지 못한 명령은 통과로 처리하지 말고 별도 리스크로 기록한다.

LLM이 최종 wire-format response body를 직접 작성하면 안 된다. LLM은 decision-making과 `response_plan` 생성에 집중하고, shape 생성, rendering, validation은 deterministic runtime code가 담당해야 한다.

## 성공 조건

1. 기본 LLM fallback 경로가 단일 agentic runtime을 사용해야 한다.
2. 기존 `workflow` 경로는 제거하고, fallback runtime은 agentic 경로에 집중해야 한다.
3. provider는 OpenAI Responses API 기반 direct API 경로만 사용한다.
4. LLM은 최종 body 생성이 아니라 response planning에만 필요해야 한다.
5. validation 실패 시 최대 1회만 재계획해야 한다. 가능하면 deterministic fast path로 LLM 호출 자체를 피한다.
6. 40개의 AWS CLI command benchmark corpus를 repo 안에 정의해야 한다.
7. benchmark runner는 corpus에서 매번 7개 명령어를 랜덤 샘플링할 수 있어야 한다.
8. benchmark는 각 샘플의 latency와 quality 결과를 기록해야 한다.
9. offline/stub benchmark는 사전 검증용일 뿐이며, 최종 성능 판단은 실제 OpenAI Responses API live benchmark 결과를 기준으로 해야 한다.
10. live OpenAI Responses API 7개 샘플 benchmark를 반드시 실행해야 한다.
11. live 7개 샘플 benchmark에서 각 fallback 응답 생성 시간이 3초 미만인지 확인해야 한다. 3초 미만이 어렵다면 4초 미만 보조 목표를 적용하고, 초과 항목은 원인을 기록한다.
12. 관련 pytest가 통과해야 한다.
13. `MOTO_LLM_RUNTIME_MODE`를 지정하지 않아도 agentic runtime이 기본으로 사용되는 테스트가 있어야 한다.
14. benchmark와 live 실험은 token usage를 함께 기록해야 한다.
15. live 7개 샘플 결과가 4초 미만 상한과 품질 기준을 대부분 만족하면, 40개 전체 명령어 corpus에 대해서도 live OpenAI Responses API 실험을 실행해야 한다.
16. AWS CLI reference URL 기반 1차 구조 검증을 반드시 실행해야 한다. 이 검증은 실제 command page를 찾아 `Output` 섹션과 같은 응답 구조인지 확인하고, 전체 40개 명령어에 대해 nested output shape까지 재귀적으로 검증해야 한다.
17. 1차 구조 검증에서 실패한 명령어는 latency 최적화 전에 먼저 수정해야 한다.
18. 2차 성능 검증에서는 전체 40개 명령어가 실제 OpenAI Responses API live mode에서 모두 3초 이내로 가능한지 확인해야 한다.
19. 3초 이내가 되지 않는 명령어는 token cap, prompt 축소, deterministic fast path, retry 제거, serializer 최적화 중 어떤 조치가 효과가 있었는지 비교 실험하고 기록해야 한다.
20. 마지막 보고에는 변경 파일, 검증 명령, AWS CLI URL 구조 검증 결과, benchmark 결과, token usage, 3초 달성 여부, 남은 리스크가 포함되어야 한다.

## 응답 품질 기준

각 fallback 응답은 아래 조건을 만족해야 한다.

- 예상 AWS protocol에 따라 JSON 또는 XML로 parse 가능해야 한다.
- service와 operation에 맞는 protocol family를 사용해야 한다.
- 대상 operation의 required core output field를 포함해야 한다.
- AWS CLI 문서 `Output`과 같은 botocore output shape의 top-level response field와 충돌하지 않아야 한다.
- AWS CLI 문서 `Output`과 같은 nested structure, list item, map, scalar shape와도 충돌하지 않아야 한다.
- 실제 URL, credential, private key, 실제 account data를 노출하면 안 된다.
- fake account ID와 region consistency lock을 지켜야 한다.
- 공격자가 입력한 identifier는 안전하고 설득력을 높이는 경우에만 echo해야 한다.
- reconnaissance, inventory 계열 API는 sparse하지만 그럴듯한 응답을 반환해야 한다.

`quality_pass`는 아래 조건이 모두 참일 때만 참으로 기록한다.

- `parseable=true`
- `protocol_match=true`
- `required_core_fields_present=true`
- `aws_output_shape_pass=true`
- `aws_output_shape_recursive_pass=true`
- `aws_cli_reference_verified=true`
- `safety_pass=true`
- `latency_ms < 3000`

## Latency 목표

benchmark 목표는 아래와 같다.

- 전체 corpus 크기: 40개 명령어
- 한 번의 benchmark sample size: 무작위 7개 명령어
- 최종 평가 기준: 실제 OpenAI Responses API direct API live benchmark
- 1차 목표 latency: live benchmark에서 전체 40개 fallback 응답이 모두 3초 미만
- 보조 latency 기준: 3초 미만 달성이 어렵다면 각 fallback 응답은 최대 4초 미만까지 허용하되, 이것은 최종 성공이 아니라 원인 분석 대상이다.
- latency 측정 기준: fallback이 실제로 발생한 뒤 `handle_aws_request` 또는 그에 준하는 fallback runtime entrypoint에 진입한 시점부터 response body가 반환되는 시점까지
- latency 측정에서 서버 기동 시간, AWS CLI 프로세스 시작 시간, 테스트 fixture 준비 시간은 제외한다.
- offline/stub benchmark mode: 구현 검증과 회귀 테스트용이다. 최종 latency/token/quality 판단에는 사용하지 않는다.
- live provider mode: OpenAI Responses API direct API만 사용한다. 실제 `OPENAI_API_KEY`가 필요하다.
- OpenCode/opencode 기반 transport는 제거하거나 사용하지 않는다.
- live provider 실험은 input tokens, output tokens, total tokens, model, response id, latency를 함께 기록한다.

live provider가 안정적으로 3초 미만을 만족하지 못하면, 최대 4초 미만을 보조 지표로 함께 기록한다. 4초도 만족하지 못하면 그 결과를 그대로 기록하고 이유를 문서화한다. offline/stub 결과로 live provider의 느린 결과를 숨기면 안 된다.

2차 성능 검증은 아래 순서로 진행한다.

1. live 7개 샘플에서 3초 초과 항목을 찾는다.
2. output token cap, prompt 길이, retry 발생 여부, deterministic fast path 가능 여부를 기록한다.
3. token cap을 낮추는 실험은 응답 구조 품질을 깨지 않는 선에서만 인정한다.
4. deterministic fast path를 추가할 경우에도 실제 live API 실험을 생략하면 안 된다. 단, LLM이 필요한 planning 단계가 줄어든 경우 그 이유와 효과를 기록한다.
5. live 40개 전체 corpus에서 3초 이하 통과 수, 4초 이하 통과 수, 초과 명령어 목록, 초과 원인을 저장한다.

## 구현 방향

우선순위는 아래와 같다.

1. `agentic` runtime을 기본 실행 모드로 만든다.
2. 기존 workflow 경로는 제거한다. compatibility가 꼭 필요한 경우에도 별도 workflow 구현을 유지하지 말고 agentic runtime으로 위임한다.
3. 중복된 provider, prompt, parser, orchestration 경로를 줄인다.
4. output shape와 safe value가 명확한 common operation은 deterministic fast path를 우선 사용한다.
5. LLM은 deterministic planning이 부족할 때만 사용한다.
6. retry count는 낮게 유지한다. open-ended loop 대신 validation-driven correction을 사용한다.
7. service-specific special case는 좁게 유지하고 테스트로 보호한다.
8. 관련 없는 Moto service 동작은 변경하지 않는다.
9. OpenCode/opencode transport 경로는 제거하거나 비활성화하고, 실험은 OpenAI Responses API direct API 기준으로 진행한다.
10. 실험 중 token usage를 계속 확인하고, latency와 품질이 비슷하다면 token 사용량이 더 낮은 방향을 우선한다.

## Benchmark Corpus

Benchmark는 아래에 있는 40개의 명령어 셋 중 무작위 7개를 선택한다.

각 command는 AWS CLI reference의 실제 command page와 매핑되어야 한다.

매핑 규칙:

- base URL: `https://docs.aws.amazon.com/cli/latest/reference/`
- service 이름은 AWS CLI command의 service segment를 사용한다.
- operation 이름은 AWS CLI command의 subcommand segment를 사용한다.
- command page URL 예: `aws ec2 describe-volume-status` -> `https://docs.aws.amazon.com/cli/latest/reference/ec2/describe-volume-status.html`
- benchmark artifact에는 각 command별 `aws_cli_reference_url`, `aws_cli_reference_found`, `aws_cli_output_section_found`, `botocore_service`, `botocore_operation`, `botocore_output_shape`를 저장한다.
- URL의 command page가 실제 command와 맞지 않거나 `Output` 섹션을 찾지 못하면 `aws_cli_reference_verified=false`로 기록한다.

aws bedrock list-foundation-models
aws ec2 monitor-instances --instance-ids i-1234567890abcdef0
aws ec2 unmonitor-instances --instance-ids i-1234567890abcdef0
aws ec2 describe-reserved-instances
aws ec2 describe-reserved-instances-listings
aws ec2 purchase-reserved-instances-offering --reserved-instances-offering-id aaaaaa11-bbbb-cccc-ddd-example1 --instance-count 1
aws ec2 describe-volume-status --volume-ids vol-1234567890abcdef0
aws ec2 modify-volume-attribute --volume-id vol-1234567890abcdef0 --auto-enable-io
aws ec2 create-spot-datafeed-subscription --bucket my-honeypot-bucket
aws ec2 describe-bundle-tasks
aws resource-explorer-2 list-indexes
aws resource-explorer-2 list-views
aws resource-explorer-2 search --query-string "*" --view-arn <view-arn>
aws support describe-services --region us-east-1
aws support describe-trusted-advisor-check-result --check-id <check-id> --language en --region us-east-1
aws support describe-trusted-advisor-check-summaries --check-ids <check-id> --region us-east-1
aws eks list-addons --cluster-name <cluster-name>
aws eks describe-addon-versions
aws ssm start-session --target <instance-id>
aws ecs execute-command --cluster <cluster-name> --task <task-id> --container <container-name> --interactive --command "/bin/sh"
aws billingconductor list-billing-groups
aws frauddetector get-detectors
aws detective list-graphs
aws auditmanager list-assessments
aws outposts list-outposts
aws appflow list-flows
aws omics list-runs
aws mgn describe-source-servers
aws codeguru-reviewer list-repository-associations
aws backup-gateway list-gateways
aws ssm describe-instance-information
aws ecr batch-check-layer-availability --repository-name demo --layer-digests sha256:abc
aws ecr get-download-url-for-layer --repository-name demo --layer-digest sha256:abc
aws ecr initiate-layer-upload --repository-name demo
aws ecr complete-layer-upload --repository-name demo --upload-id test --layer-digests sha256:abc
aws iam get-context-keys-for-principal-policy --policy-source-arn arn:aws:iam::123456789012:user/victim-admin
aws iam list-service-specific-credentials --user-name victim-admin
aws iam generate-service-last-accessed-details --arn arn:aws:iam::123456789012:user/victim-admin
aws secretsmanager validate-resource-policy --secret-id prod/db/password --resource-policy '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":"*","Action":"secretsmanager:GetSecretValue","Resource":"*"}]}'
aws sts decode-authorization-message --encoded-message ZmFrZS1hdXRob3JpemF0aW9uLW1lc3NhZ2U=


위 command corpus에는 `<view-arn>`, `<check-id>`, `<cluster-name>`, `<instance-id>`, `<task-id>`, `<container-name>` 같은 placeholder가 남아 있을 수 있다.

goal 실행 전에 먼저 placeholder별 fake 값을 주입한 실험을 수행해야 한다.

이 사전 실험의 목적은 아래와 같다.

- placeholder에 임의의 fake 값을 넣어도 request normalization이 일관되게 동작하는지 확인한다.
- 같은 fake 값이 request, response, audit, benchmark summary에서 일관되게 반영되는지 확인한다.
- fake ARN의 account ID와 region이 world state consistency lock과 충돌하지 않는지 확인한다.
- shell redirection 같은 실행 위험이 있는 placeholder는 benchmark runner 내부에서 안전하게 치환하거나, 직접 shell 실행 대신 runtime harness에서 안전하게 처리한다.
- 사전 실험 결과를 benchmark 결과와 별도로 기록한다.

## Benchmark Runner

benchmark runner는 아래 기능을 가져야 한다.

1. 40-command corpus를 로드한다.
2. corpus에서 무작위 7개 명령어를 랜덤 샘플링한다.
3. 각 명령어를 fallback runtime 또는 direct runtime harness에 실행한다.
4. 명령어별 latency를 측정한다.
5. response quality를 검증한다.
6. 결과를 JSON으로 저장한다.
7. 가능하면 Markdown summary도 저장한다.
8. token usage를 기록한다.
9. 7개 샘플 benchmark가 목표에 가까워지면 40개 전체 command corpus benchmark를 실행한다.
10. AWS CLI reference URL 검증 결과를 기록한다.
11. top-level output shape뿐 아니라 nested output shape까지 재귀 검증한다.
12. 3초 초과 항목은 별도 latency diagnosis 필드에 원인을 기록한다.

추천 출력 위치:

- `artifacts/agentic_runtime/latest_results.json`
- `artifacts/agentic_runtime/latest_summary.md`
- `artifacts/agentic_runtime/aws_cli_reference_check.json`
- `artifacts/agentic_runtime/latency_diagnosis.json`

runner는 아래 옵션을 지원해야 한다.

- 재현 가능한 deterministic seed
- offline/stubbed provider mode는 사전 검증용으로만 사용
- 실제 provider 호출은 OpenAI Responses API direct API만 사용
- OpenCode/opencode transport 사용 금지
- live 실험에서는 token usage 기록 필수
- live 실험 결과 파일은 offline/stub 결과와 구분되는 이름으로 저장

AWS CLI reference 1차 검증 runner는 아래 항목을 명령어별로 저장해야 한다.

- command ID
- command string
- expected AWS CLI reference URL
- URL 접근 성공 여부
- command page title 또는 heading
- `Output` section 존재 여부
- botocore service / operation 매핑
- botocore output shape 이름
- top-level output shape pass/fail
- recursive output shape pass/fail
- mismatch path 목록

recursive mismatch path 예:

- `DescribeVolumeStatusOutput.VolumeStatuses[0].Actions[0]`
- `DescribeVolumeStatusOutput.VolumeStatuses[0].VolumeStatus.Details[0]`

## 실제 API 실험 요구사항

이 목표는 반드시 실제 OpenAI Responses API를 사용해 검증해야 한다.

진행 순서는 아래를 따른다.

1. 먼저 AWS CLI reference URL 기반 1차 구조 검증을 실행한다.
2. 1차 구조 검증은 40개 전체 command에 대해 실제 command page URL, `Output` 섹션 존재 여부, botocore output shape 매핑, recursive response shape 일치 여부를 확인한다.
3. 1차 구조 검증 실패가 있으면 실패한 명령어를 먼저 수정하고 다시 검증한다.
4. 그 다음 offline/stub mode로 runner와 품질 검증 로직이 동작하는지 빠르게 확인한다.
5. 실제 `OPENAI_API_KEY`를 사용해서 live 7개 샘플 benchmark를 실행한다.
6. live 7개 샘플 결과에서 latency, token usage, quality failure를 분석한다.
7. live 7개 샘플이 4초 미만 상한과 품질 기준을 대부분 만족하면 live 40개 전체 corpus benchmark를 실행한다.
8. live 40개 전체 결과를 기준으로 모든 명령어가 3초 이내로 줄어들 수 있는지 2차 성능 검증을 수행한다.
9. 3초 초과 명령어가 남아 있으면 latency diagnosis를 남기고, 가능한 최적화 실험을 최소 1회 이상 수행한다.
10. live 40개 전체 실행이 비용이나 시간 때문에 어렵다면, 실행하지 않은 이유와 예상 비용/토큰 리스크를 명확히 보고한다.

live 결과 저장 위치 예:

- `artifacts/agentic_runtime/aws_cli_reference_check.json`
- `artifacts/agentic_runtime/live_sample_7_results.json`
- `artifacts/agentic_runtime/live_sample_7_summary.md`
- `artifacts/agentic_runtime/live_full_40_results.json`
- `artifacts/agentic_runtime/live_full_40_summary.md`
- `artifacts/agentic_runtime/latency_diagnosis.json`

live 결과에는 최소한 아래 항목이 있어야 한다.

- command ID
- service / operation
- latency_ms
- under_3s
- under_4s
- quality_pass
- validation_reason
- input_tokens
- output_tokens
- total_tokens
- model
- response_id
- aws_cli_reference_url
- aws_cli_reference_verified
- aws_output_shape_pass
- aws_output_shape_recursive_pass
- aws_output_shape_mismatches
- latency_diagnosis

## 추천 검증 명령

기존 repo의 test style을 따르고, 검증 범위는 너무 넓히지 않는다.

기본 검증:

```bash
pytest tests/test_core/test_llm_agents_runtime.py
```

AWS CLI reference URL 기반 1차 구조 검증:

```bash
python scripts/benchmark_agentic_runtime.py --check-aws-cli-reference --all --results artifacts/agentic_runtime/aws_cli_reference_check.json
```

offline/stub benchmark 사전 검증:

```bash
python scripts/benchmark_agentic_runtime.py --sample-size 7 --seed 1
```

실제 OpenAI Responses API 7개 샘플 검증:

```bash
python scripts/benchmark_agentic_runtime.py --sample-size 7 --seed 1 --live --results artifacts/agentic_runtime/live_sample_7_results.json --summary artifacts/agentic_runtime/live_sample_7_summary.md
```

실제 OpenAI Responses API 40개 전체 검증:

```bash
python scripts/benchmark_agentic_runtime.py --all --seed 1 --live --results artifacts/agentic_runtime/live_full_40_results.json --summary artifacts/agentic_runtime/live_full_40_summary.md
```

3초 목표 2차 성능 검증:

```bash
python scripts/benchmark_agentic_runtime.py --all --seed 1 --live --latency-diagnosis --results artifacts/agentic_runtime/live_full_40_results.json --summary artifacts/agentic_runtime/live_full_40_summary.md
```

## 제약 조건

- 기본 test와 기본 benchmark는 외부 네트워크를 요구하면 안 된다.
- test와 offline/stub benchmark에는 `OPENAI_API_KEY`나 live provider key가 필요하면 안 된다.
- live benchmark에는 실제 `OPENAI_API_KEY`를 사용해야 한다.
- Moto 전체 구조를 크게 바꾸는 대규모 리팩터링은 피한다.
- 관련 없는 AWS service 동작을 변경하지 않는다.
- 사용자가 만든 기존 변경사항을 되돌리지 않는다.
- secret을 tracked file에 저장하지 않는다.
- audit log, benchmark result, Markdown summary에는 `Authorization`, `X-Amz-Security-Token`, access key, secret key, session token을 원문으로 저장하지 않는다. 반드시 redact한다.
- OpenCode/opencode 기반 실험은 진행하지 않는다.
- OpenAI Responses API 기반 실험에서는 token usage를 반드시 기록한다.
- live benchmark 결과를 offline/stub 결과로 대체하지 않는다.
- 최종 runtime은 읽기 쉽고 테스트하기 쉬워야 한다.

## 추적해야 할 리스크

- AWS CLI reference HTML 구조가 변경되면 `Output` 섹션 파싱이 깨질 수 있다.
- AWS CLI 문서 버전과 로컬 botocore service model 버전이 다르면 일부 output shape가 다르게 보일 수 있다.
- top-level shape가 맞아도 nested list item이나 nested structure가 틀릴 수 있다. 예를 들어 `DescribeVolumeStatus`의 `Actions[]`, `VolumeStatus.Details[]`는 string이 아니라 structure여야 한다.
- live LLM 호출은 3초 미만을 안정적으로 만족하지 못할 수 있다.
- 3초 미만이 어렵다면 4초 미만을 보조 지표로 기록하되, 4초도 넘는 명령어는 별도 원인 분석 대상이다.
- 3초 초과 원인이 provider latency인지, prompt/token 크기인지, retry/validation 재시도인지, serializer/shape 변환 비용인지 구분해야 한다.
- query XML 계열 AWS protocol은 serializer 처리가 까다로울 수 있다.
- 기존 테스트가 오래된 workflow 이름이나 helper API를 참조할 수 있다.
- workflow 경로 제거 과정에서 오래된 테스트나 환경변수 호환성이 깨질 수 있다.
- service-specific fast path가 많아지면 유지보수가 어려워질 수 있다.

## 최종 보고 요구사항

작업 완료 시 아래 내용을 요약한다.

- 변경한 파일
- runtime path의 변경 전/후 구조
- 실행한 test와 결과
- AWS CLI reference URL 기반 1차 구조 검증 결과
- command별 reference URL 검증 통과/실패
- recursive output shape 검증 통과/실패와 mismatch path
- 실행한 benchmark command
- 샘플링된 command ID
- live 샘플별 latency
- live 샘플별 token usage
- live 샘플별 quality pass/fail
- live 3초 목표 달성 여부
- live 4초 상한 충족 여부
- live 40개 전체 corpus 기준 3초 초과 명령어와 원인 분석
- 3초 이내로 줄이기 위해 수행한 2차 최적화 실험과 결과
- live 40개 전체 corpus 실험 결과 또는 미실행 사유
- offline/stub 결과는 참고자료로만 별도 표시
- 남은 리스크와 다음 권장 작업
