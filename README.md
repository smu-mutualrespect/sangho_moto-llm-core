# moto-llm-core

`moto`의 미구현 요청 경로에 LLM fallback을 붙이기 위한 초기 코어 세팅 저장소입니다.

이 저장소는 완성형 구현보다는 시작점에 가깝습니다. 팀원들이 이 저장소를 fork하거나 clone한 뒤, 각자 `agent` 구조, prompt 설계, 응답 포맷, 정책 로직을 확장해 나가는 것을 전제로 합니다.

## 먼저 이런 명령으로 fallback을 실험해보자

아래 명령들은 현재 로컬 테스트에서 LLM fallback 응답이 확인된 예시들입니다.

- `aws --endpoint-url=http://127.0.0.1:5001 ecr batch-check-layer-availability --repository-name demo --layer-digests sha256:abc`
  - 컨테이너 레지스트리 탐색 또는 업로드 준비 흐름처럼 보이는 명령입니다.
- `aws --endpoint-url=http://127.0.0.1:5001 ecr get-download-url-for-layer --repository-name demo --layer-digest sha256:abc`
  - 이미지 레이어를 가져오려는 시도처럼 보여서 공격 행위 시뮬레이션에 잘 맞습니다.
- `aws --endpoint-url=http://127.0.0.1:5001 ecr initiate-layer-upload --repository-name demo`
  - 악성 이미지 업로드 시작 흐름처럼 보일 수 있습니다.
- `aws --endpoint-url=http://127.0.0.1:5001 ecr complete-layer-upload --repository-name demo --upload-id test --layer-digests sha256:abc`
  - 업로드 마무리 단계처럼 보이기 때문에 흔적 분석용으로도 쓸 만합니다.
- `aws --endpoint-url=http://127.0.0.1:5001 ssm describe-instance-information`
  - 내부 인프라나 관리 대상 탐색용 정찰 흐름에 잘 맞습니다.
- `aws --endpoint-url=http://127.0.0.1:5001 iam create-service-specific-credential --user-name victim-admin --service-name codecommit.amazonaws.com`
  - 기존 `iam create-access-key`는 `moto` 자체 구현으로 처리되므로, 자격 증명 생성 허니팟 흐름은 이 명령으로 먼저 실험합니다.
- `aws --endpoint-url=http://127.0.0.1:5001 iam get-context-keys-for-principal-policy --policy-source-arn arn:aws:iam::123456789012:user/victim-admin`
  - 권한/정책 조건을 탐색하는 IAM 정찰 흐름입니다.
- `aws --endpoint-url=http://127.0.0.1:5001 sts decode-authorization-message --encoded-message ZmFrZS1hdXRob3JpemF0aW9uLW1lc3NhZ2U=`
  - 기존 `sts get-caller-identity`는 `moto` 자체 구현으로 처리되므로, 거부된 권한의 상세 정보를 캐려는 흐름은 이 명령으로 실험합니다.
- `aws --endpoint-url=http://127.0.0.1:5001 secretsmanager validate-resource-policy --secret-id prod/db/password --resource-policy '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":"*","Action":"secretsmanager:GetSecretValue","Resource":"*"}]}'`
  - 기존 `secretsmanager list-secrets`는 `moto` 자체 구현으로 처리되므로, Secret 접근 정책 검증/오남용 흐름은 이 명령으로 실험합니다.

아래 명령들은 같은 실험에서 `moto` 자체 구현 또는 자체 에러로 처리되었습니다. fallback 동작 확인용 baseline으로는 쓸 수 있지만, 현재 상태에서는 LLM fallback 검증 명령은 아닙니다.

- `aws --endpoint-url=http://127.0.0.1:5001 iam create-user --user-name victim-admin`
- `aws --endpoint-url=http://127.0.0.1:5001 iam create-access-key --user-name victim-admin`
- `aws --endpoint-url=http://127.0.0.1:5001 iam attach-user-policy --user-name victim-admin --policy-arn arn:aws:iam::aws:policy/AdministratorAccess`
- `aws --endpoint-url=http://127.0.0.1:5001 sts get-caller-identity`
- `aws --endpoint-url=http://127.0.0.1:5001 secretsmanager list-secrets`

추가 조사에서 아래 IAM 후보는 아직 README 실험 명령으로 쓰지 않는 것이 좋다고 봤습니다.

- `iam simulate-principal-policy`
  - 허니팟 시나리오에는 잘 맞지만, 현재 fallback 실패 시 기본 JSON이 IAM XML 파서로 들어가 `invalid XML` 에러가 발생했습니다.
- `iam generate-service-last-accessed-details`
  - 서비스 접근 정찰 시나리오에는 맞지만, 현재 fallback 실패 시 기본 JSON이 IAM XML 파서로 들어가 `invalid XML` 에러가 발생했습니다.
- `iam list-service-specific-credentials`
  - fallback은 탔지만 AWS CLI가 기대한 `ListServiceSpecificCredentialsResult` wrapper와 맞지 않아 파싱 실패했습니다.

## 현재 `moto`에서 바꾼 부분

이번 변경은 `moto`가 요청을 끝까지 처리하지 못하는 경로에 fallback hook를 넣는 데 집중했습니다.

### 수정한 파일

- [`responses.py`](/mnt/c/Users/Administrator/Desktop/honey/moto/moto/core/responses.py)
  - 핸들러는 있는데 내부에서 `NotImplementedError`가 나는 경우
  - action 자체를 읽지 못하는 경우
  - action은 알지만 해당 핸들러 메서드가 없는 경우
- [`botocore_stubber.py`](/mnt/c/Users/Administrator/Desktop/honey/moto/moto/core/botocore_stubber.py)
  - backend URL 매칭이 안 되는 경우
- [`custom_responses_mock.py`](/mnt/c/Users/Administrator/Desktop/honey/moto/moto/core/custom_responses_mock.py)
  - requests-mock의 최종 catch-all 경로
- [`llm_fallback.py`](/mnt/c/Users/Administrator/Desktop/honey/moto/moto/core/llm_fallback.py)
  - 공통 entrypoint 역할만 하도록 얇게 유지
- [`llm_agents/providers.py`](/mnt/c/Users/Administrator/Desktop/honey/moto/moto/core/llm_agents/providers.py)
  - OpenCode와 direct API transport를 선택하는 provider 구현
- [`llm_agents/agent.md`](/mnt/c/Users/Administrator/Desktop/honey/moto/moto/core/llm_agents/agent.md)
  - OpenCode와 direct API 호출이 공유하는 단일 fallback agent prompt
- [`opencode.json`](/mnt/c/Users/Administrator/Desktop/honey/moto/opencode.json)
  - `openai/gpt-5.4` 기반 `moto-fallback` OpenCode agent 설정

## 현재 fallback 흐름

현재 fallback 흐름은 의도적으로 단순하게 잡혀 있습니다.

1. `moto`가 요청을 처리한다.
2. 특정 미구현/미매칭 경로에 도달하면 fallback 분기로 들어간다.
3. fallback 코드가 요청 정보를 바탕으로 prompt를 만든다.
4. [`llm_fallback.py`](/mnt/c/Users/Administrator/Desktop/honey/moto/moto/core/llm_fallback.py)가 공통 entrypoint 역할을 한다.
5. 실제 LLM 호출은 [`llm_agents/providers.py`](/mnt/c/Users/Administrator/Desktop/honey/moto/moto/core/llm_agents/providers.py)에서 수행한다.
6. 기본 transport는 OpenCode CLI이며, `opencode run --agent moto-fallback --model openai/gpt-5.4` 형태로 호출한다.
7. direct OpenAI API transport를 쓰는 경우에도 같은 [`llm_agents/agent.md`](/mnt/c/Users/Administrator/Desktop/honey/moto/moto/core/llm_agents/agent.md)를 instructions로 넣는다.
8. LLM 호출이 성공하면 그 응답 텍스트를 body로 사용한다.
9. LLM 호출이 실패하면 현재는 아래 JSON을 반환한다.

```json
{"message":"llm_fallback!!"}
```

## 단일 에이전트로 효율을 뽑는 기준

지금 구조에서 중요한 것은 agent 수를 늘리는 것이 아니라, 단일 runtime agent가 매 요청에서 얼마나 짧은 문맥으로 얼마나 그럴듯한 응답을 내느냐입니다.

단일 agent baseline에서 우선순위는 아래 순서가 맞습니다.

1. latency를 줄이기 위해 prompt를 짧게 유지한다.
2. quality를 올리기 위해 응답 shape를 서비스별로 강하게 제한한다.
3. consistency를 유지하기 위해 동일 입력에는 최대한 같은 출력이 나오게 한다.
4. 미구현 API 전체를 커버하려고 하기보다 공격자가 실제로 많이 두드릴 API부터 맞춘다.

즉, `README.md`에 적어둔 실험 명령을 많이 아는 agent보다, 실제 AWS 허니팟 요청에서 필요한 최소 필드만 보고 바로 AWS-like body를 뱉는 agent가 더 낫습니다.

### 단일 agent에서 latency를 줄이는 방법

- provider에 넘기는 request context를 compact하게 유지한다.
- header/body는 전부 넘기지 말고, 필요한 키만 남기거나 길이를 잘라낸다.
- `agent.md`는 설명형 문서가 아니라 runtime 규격 문서처럼 짧고 강하게 유지한다.
- 가능하면 OpenCode subprocess 비용보다 direct API transport가 유리한지 별도로 측정한다.
- 서비스별 실패 유형을 많이 아는 것보다, `service/action/source/reason/body` 정도의 핵심 정보로 바로 분기하는 편이 빠르다.

### 단일 agent에서 quality를 올리는 방법

- 자유서술을 줄이고 서비스별 response schema를 강하게 강제한다.
- reconnaissance 계열은 빈 리스트 또는 희소한 결과를 우선한다.
- privilege/credential 계열은 decoy metadata만 반환하고 실제 capability는 주지 않는다.
- IAM/XML 계열은 CLI parser가 기대하는 wrapper를 먼저 맞춘다.
- 같은 리소스 이름이나 digest가 들어오면 응답 shape가 흔들리지 않도록 한다.

### 실제로 확인해야 하는 것

단일 agent 최적화는 결국 아래 세 개를 같이 봐야 합니다.

- `p50/p95 fallback latency`
- AWS CLI parser 통과율
- 동일 요청 재실행 시 응답 일관성

이 세 개가 안 맞으면 agent가 똑똑해 보여도 허니팟 운영 품질은 떨어집니다.

## 지금 fallback이 걸리는 지점

### 1. 핸들러는 있는데 내부 구현이 비어 있는 경우

- 파일: [`responses.py`](/mnt/c/Users/Administrator/Desktop/honey/moto/moto/core/responses.py)
- 의미:
  - 핸들러 메서드는 존재함
  - 하지만 내부에서 `NotImplementedError`가 발생함

### 2. action 자체를 읽지 못하는 경우

- 파일: [`responses.py`](/mnt/c/Users/Administrator/Desktop/honey/moto/moto/core/responses.py)
- 의미:
  - 요청은 들어왔지만
  - `moto`가 action 이름을 결정하지 못함

### 3. action은 알지만 핸들러 메서드가 없는 경우

- 파일: [`responses.py`](/mnt/c/Users/Administrator/Desktop/honey/moto/moto/core/responses.py)
- 의미:
  - action 이름은 파악됨
  - 그런데 Response 클래스에 해당 메서드가 없음

### 4. backend URL 매칭이 안 되는 경우

- 파일: [`botocore_stubber.py`](/mnt/c/Users/Administrator/Desktop/honey/moto/moto/core/botocore_stubber.py)
- 의미:
  - AWS URL 형태는 맞음
  - 하지만 `moto` backend URL pattern과 매칭되지 않음

### 5. requests-mock catch-all 경로로 떨어지는 경우

- 파일: [`custom_responses_mock.py`](/mnt/c/Users/Administrator/Desktop/honey/moto/moto/core/custom_responses_mock.py)
- 의미:
  - requests-mock의 마지막 catch-all 경로에 걸림

## 현재 코드 구조

현재 구조는 팀 단위 확장을 염두에 둔 최소 세팅입니다.

```text
moto/moto/core/
  llm_fallback.py
  llm_agents/
    __init__.py
    agent.md
    providers.py
opencode.json
```

### 각 파일의 역할

- `llm_fallback.py`
  - 공통 entrypoint
  - fallback 확인용 JSON 응답 생성
  - 실제 provider 호출은 `llm_agents` 쪽을 참조
- `llm_agents/providers.py`
  - provider 구현
  - `call_gpt_api(...)`
  - `call_claude_api(...)`
  - 기본 GPT transport는 OpenCode
  - `MOTO_LLM_OPENAI_TRANSPORT=api`를 주면 direct OpenAI Responses API 사용
- `llm_agents/agent.md`
  - OpenCode와 direct OpenAI API가 공유하는 단일 fallback agent prompt
- `opencode.json`
  - `moto-fallback` OpenCode agent 설정

## 다음에 바꿔야 할 부분

지금 구조는 시작점일 뿐이고, 실제 agent 기반 구조로 확장하려면 아래 부분을 바꿔야 합니다.

### 1. fallback 응답 검증셋 확장하기

현재 확인된 fallback 명령은 ECR 4개와 SSM 1개입니다. 이후에는 서비스별로 fallback이 실제로 타는 명령과 `moto` 자체 구현으로 처리되는 명령을 분리해서 관리하는 것이 좋습니다.

### 2. prompt 구조 정교화하기

현재 prompt는 단일 agent baseline입니다.

이후에는 최소한 아래 정보를 명확히 구분해서 prompt를 구성하는 것이 좋습니다.

- 서비스 이름
- action 이름
- fallback이 발생한 source
- 실패 이유
- read-only 요청인지 여부
- 원하는 출력 형식

### 3. LLM에게 넘기는 정보 구조화하기

지금은 prompt 문자열 위주지만, 이후에는 더 구조적으로 넘기는 것이 좋습니다.

추천 필드:

- `service`
- `action`
- `source`
- `reason`
- `method`
- `url`
- `headers`
- `body`
- `region`
- read-only 여부

### 4. 응답 포맷 개선하기

현재 fallback 응답은 실험용으로 단순화되어 있습니다.

이후에는 아래 방향으로 가는 것이 좋습니다.

- 서비스별 JSON 형식 맞추기
- 필요 시 XML 형식 맞추기
- status code 세분화
- 허니팟 로깅용 메타데이터 추가

## 팀원들을 위한 메모

- 이 저장소는 초기 코어 세팅입니다.
- 각자 fork 또는 clone해서 `llm_agents`, prompt 설계, 응답 포맷을 원하는 방향으로 확장하면 됩니다.
- 현재 구현은 최종 아키텍처가 아닙니다.
- 현재 구현의 목적은 `moto`의 fallback hook 지점이 실제로 도달 가능한지, 그리고 GPT / Claude 연동 지점을 어디에 둘 수 있는지를 검증하는 것입니다.
