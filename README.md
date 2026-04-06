# moto-llm-core

`moto`의 미구현 요청 경로에 LLM fallback을 붙이기 위한 초기 코어 세팅 저장소입니다.

이 저장소는 완성형 구현보다는 시작점에 가깝습니다. 팀원들이 이 저장소를 fork하거나 clone한 뒤, 각자 `agent` 구조, prompt 설계, 응답 포맷, 정책 로직을 확장해 나가는 것을 전제로 합니다.

## 먼저 이런 명령으로 실험해보자

아래 명령들은 허니팟 관점에서 비교적 현실감이 있고, 현재 fallback 구조를 실험해보기에도 적절한 예시들입니다.

- `aws --endpoint-url=http://127.0.0.1:5001 ecr batch-check-layer-availability --repository-name demo --layer-digests sha256:abc`
  - 컨테이너 레지스트리 탐색 또는 업로드 준비 흐름처럼 보이는 명령입니다.
- `aws --endpoint-url=http://127.0.0.1:5001 ecr get-download-url-for-layer --repository-name demo --layer-digest sha256:abc`
  - 이미지 레이어를 가져오려는 시도처럼 보여서 공격 행위 시뮬레이션에 잘 맞습니다.
- `aws --endpoint-url=http://127.0.0.1:5001 ecr initiate-layer-upload --repository-name demo`
  - 악성 이미지 업로드 시작 흐름처럼 보일 수 있습니다.
- `aws --endpoint-url=http://127.0.0.1:5001 ecr complete-layer-upload --repository-name demo --upload-id test --layer-digests sha256:abc`
  - 업로드 마무리 단계처럼 보이기 때문에 흔적 분석용으로도 쓸 만합니다.
- `aws --endpoint-url=http://127.0.0.1:5001 iam create-user --user-name victim-admin`
  - 계정 생성 또는 권한 확보 시도로 보이기 때문에 허니팟 가치가 높습니다.
- `aws --endpoint-url=http://127.0.0.1:5001 iam create-access-key --user-name victim-admin`
  - 자격 증명 생성 또는 탈취 흐름과 잘 맞습니다.
- `aws --endpoint-url=http://127.0.0.1:5001 iam attach-user-policy --user-name victim-admin --policy-arn arn:aws:iam::aws:policy/AdministratorAccess`
  - 공격자 관점에서 매우 전형적인 권한 상승 패턴입니다.
- `aws --endpoint-url=http://127.0.0.1:5001 sts get-caller-identity`
  - 거의 필수 수준의 초기 정찰 명령입니다.
- `aws --endpoint-url=http://127.0.0.1:5001 secretsmanager list-secrets`
  - 민감 정보 탐색 시나리오에 잘 맞습니다.
- `aws --endpoint-url=http://127.0.0.1:5001 ssm describe-instance-information`
  - 내부 인프라나 관리 대상 탐색용 정찰 흐름에 잘 맞습니다.

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
  - GPT / Claude API 호출 함수 구현

## 현재 fallback 흐름

현재 fallback 흐름은 의도적으로 단순하게 잡혀 있습니다.

1. `moto`가 요청을 처리한다.
2. 특정 미구현/미매칭 경로에 도달하면 fallback 분기로 들어간다.
3. fallback 코드가 요청 정보를 바탕으로 prompt를 만든다.
4. [`llm_fallback.py`](/mnt/c/Users/Administrator/Desktop/honey/moto/moto/core/llm_fallback.py)가 공통 entrypoint 역할을 한다.
5. 실제 GPT / Claude API 호출은 [`llm_agents/providers.py`](/mnt/c/Users/Administrator/Desktop/honey/moto/moto/core/llm_agents/providers.py)에서 수행한다.
6. LLM 호출이 성공하면 그 응답 텍스트를 body로 사용한다.
7. LLM 호출이 실패하면 현재는 아래 JSON을 반환한다.

```json
{"message":"llm_fallback!!"}
```

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
    providers.py
```

### 각 파일의 역할

- `llm_fallback.py`
  - 공통 entrypoint
  - fallback 확인용 JSON 응답 생성
  - 실제 provider 호출은 `llm_agents` 쪽을 참조
- `llm_agents/providers.py`
  - 최소 provider 구현
  - `call_gpt_api(...)`
  - `call_claude_api(...)`

## 다음에 바꿔야 할 부분

지금 구조는 시작점일 뿐이고, 실제 agent 기반 구조로 확장하려면 아래 부분을 바꿔야 합니다.

### 1. `llm_agents`를 실제 agent 구조로 확장하기

지금은 provider 함수만 들어 있지만, 이후에는 실제 agent 역할을 분리하는 구조로 가는 것이 좋습니다.

### 2. prompt 구조 다시 설계하기

현재 prompt는 의도적으로 단순합니다.

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
