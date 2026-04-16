# LLM Agent Refactoring Report (Honeypot Persona & Single Agent)

본 보고서는 AWS 허니팟 프로젝트의 LLM Fallback 시스템을 단일 에이전트 구조로 리팩토링한 내역을 상세히 기록합니다.

## 1. 목적
- **중앙 집중화:** 여러 파일에 분산된 LLM 호출 로직을 `agent.py` 하나로 통합하여 유지보수성 향상.
- **페르소나 강화:** 에이전트에게 "AWS 허니팟 서버"라는 명확한 역할을 부여하여 응답 품질 개선.
- **비교 편의성:** 환경변수 하나로 엔진(GPT/Claude)을 즉시 교체하여 모델 간 성능 비교 가능.

---

## 2. 파일별 변경 사항 (Before / After)

### [신규 생성] moto/core/llm_agents/agent.py
에이전트의 공통 프롬프트와 엔진 스위칭 로직을 담은 핵심 파일입니다.

**After:**
```python
SYSTEM_PROMPT = """...보안 허니팟을 위한 AWS API 서버 시뮬레이터다..."""

def handle_aws_request(service, action, url, headers, body, reason, source):
    # 공통 프롬프트 구성 후 MOTO_LLM_PROVIDER에 따라 엔진 선택
    provider = os.getenv("MOTO_LLM_PROVIDER", "gpt").lower()
    if provider == "claude":
        return call_claude_api(prompt)
    else:
        return call_gpt_api(prompt)
```

---

### moto/core/llm_agents/__init__.py
에이전트 함수를 외부에서 쉽게 사용할 수 있도록 export 설정을 추가했습니다.

**Before:**
```python
from .providers import call_claude_api, call_gpt_api
__all__ = ["call_claude_api", "call_gpt_api"]
```

**After:**
```python
from .providers import call_claude_api, call_gpt_api
from .agent import handle_aws_request
__all__ = ["call_claude_api", "call_gpt_api", "handle_aws_request"]
```

---

### moto/core/responses.py
가장 많은 LLM 호출 로직이 있던 핵심 파일입니다. 중복된 프롬프트와 `if/else` 분기 처리가 제거되었습니다.

**Before (3개 지점 공통):**
```python
prompt = f"""service={self.service_name}...""" # 매번 하드코딩
if os.getenv("MOTO_LLM_PROVIDER", "").lower() == "claude":
    fallback_text = call_claude_api(prompt)
else:
    fallback_text = call_gpt_api(prompt)
```

**After:**
```python
fallback_text = handle_aws_request(
    service=self.service_name,
    action=action, # 또는 None
    url=self.uri,
    headers=dict(self.headers),
    body=self.body,
    reason=reason,
    source="responses.call_action..."
)
```

---

### moto/core/botocore_stubber.py
SDK 가로채기(Stubbing) 과정에서 발생하는 Fallback 처리 부분입니다.

**Before:**
```python
prompt = f"service=None... reason=No moto backend matched..."
if os.getenv("MOTO_LLM_PROVIDER", "").lower() == "claude":
    fallback_text = call_claude_api(prompt)
else:
    fallback_text = call_gpt_api(prompt)
```

**After:**
```python
fallback_text = handle_aws_request(
    service=None,
    action=None,
    url=request.url,
    headers=dict(request.headers),
    body=getattr(request, "body", None),
    reason="No moto backend matched this AWS URL",
    source="botocore_stubber.process_request.no_backend_match"
)
```

---

### moto/core/custom_responses_mock.py
`requests` 라이브러리 모킹 시 마지막 Catch-all 단계입니다.

**Before:**
```python
prompt = f"service={get_service_from_url(request.url)}... reason=responses mock catch-all..."
if os.getenv("MOTO_LLM_PROVIDER", "").lower() == "claude":
    fallback_text = call_claude_api(prompt)
else:
    fallback_text = call_gpt_api(prompt)
```

**After:**
```python
fallback_text = handle_aws_request(
    service=get_service_from_url(request.url),
    action=None,
    url=request.url,
    headers=dict(request.headers),
    body=getattr(request, "body", None),
    reason="responses mock catch-all fallback",
    source="custom_responses_mock.not_implemented_callback"
)
```

---

### moto/core/llm_fallback.py
불필요해진 API 직접 호출 import를 정리했습니다.

**Before:**
```python
from moto.core.llm_agents import call_claude_api, call_gpt_api
```

**After:**
```python
# 해당 import 제거 (순수하게 build_llm_fallback_json 기능만 유지)
```

---

## 3. 결론
이번 리팩토링을 통해 **"프롬프트 관리(Persona)"**와 **"엔진 실행(API Call)"**이 완벽하게 분리되었습니다. 이를 통해 허니팟 시스템의 핵심인 "진짜 같은 AWS 응답"을 생성하는 로직을 한 곳에서 고도화할 수 있는 기반이 마련되었습니다.
