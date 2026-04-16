# AWS Honeypot LLM Agent Project Report

이 보고서는 AWS CLI/API를 모방하는 AI 기반 보안 허니팟 개발 과정을 기록합니다.

## 1. 프로젝트 개요
공격자가 AWS CLI 명령을 내렸을 때, 실제 AWS 서버처럼 응답을 생성하여 공격자를 기만하고 활동을 추적하는 시스템입니다. Moto 라이브러리의 Fallback 메커니즘을 활용하여 구현되지 않은 모든 AWS 액션을 LLM이 실시간으로 흉내 냅니다.

## 2. 에이전트 아키텍처 설계

### [정의] 단일 에이전트 (Single Agent)
본 프로젝트에서 정의하는 **단일 에이전트**는 "하나의 중앙 LLM 엔진이 전역적인 AWS 페르소나와 세션 메모리를 통합 관리하며, 별도의 하위 에이전트에게 작업을 위임하지 않고 모든 AWS 서비스 요청을 스스로 판단하여 처리하는 자율 시스템"을 의미합니다.

- **중앙 집중식 추론 (Centralized Reasoning):** 단일 LLM 호출로 요청 분석과 응답 생성을 동시에 수행.
- **범용 페르소나 (Generalist Persona):** 특정 서비스에 국한되지 않고 전체 AWS 생태계를 모방하는 하나의 정체성 유지.
- **도구 및 모듈의 통합:** `Memory`, `Prompt`, `Utils`는 독립적인 에이전트가 아닌, 단일 에이전트가 사용하는 **부속 도구**로 간주함.

### A. Persona (역할 정의)
- **근거:** [OpenAI Persona Prompting Guide](https://platform.openai.com/docs/guides/prompt-engineering/tactic-assign-a-persona)
- **내용:** "AWS API Simulator"라는 강력한 페르소나를 부여하여 응답의 전문성과 포맷(XML/JSON) 정확도를 확보합니다.

### B. Memory (상태 유지)
- **근거:** [Lilian Weng - LLM Powered Autonomous Agents](https://lilianweng.github.io/posts/2023-06-23-agent/)
- **필요성:** 공격자가 `create-bucket` 후 `list-buckets`를 했을 때, 방금 만든 버킷이 목록에 보여야 합니다. 이를 위해 세션 기반 히스토리 관리 기능을 구현합니다.

### C. Engine Switching (모델 비교)
- **내용:** GPT-4o와 Claude-3.5-Sonnet 등 다양한 엔진을 환경변수 하나로 교체하며 성능을 비교할 수 있는 플러그형 구조를 채택했습니다.

---

## 3. 구현 기록 (Timeline)

### [2026-04-09] 모듈형 단일 에이전트 구조 리팩토링 (Stateful & Structured)
- **작업 내용:** 단일 `agent.py` 파일의 기능을 역할별로 분리하여 모듈화 완료.
- **주요 변경 사항:**
    1.  **`prompts.py`:** 페르소나와 서비스별 응답 규칙을 XML/Markdown 구조로 체계화. (응답 신뢰도 향상)
    2.  **`memory.py`:** 세션 기반 히스토리 로직 도입. (공격자의 명령 이력 기억 및 일관성 확보)
    3.  **`utils.py`:** AWS 가짜 데이터 생성 유틸리티 구현. (ARN, 시간 포맷 등)
    4.  **`agent.py`:** 위 모듈들을 조립하여 전체 워크플로우를 제어하는 코디네이터로 리팩토링.
- **성과:** 에이전트의 구성 요소를 독립적으로 실험(프롬프트만 교체, 메모리 끄기 등)할 수 있는 최적의 환경 구축.

---

## 4. 향후 로드맵 (Proposed Design)
1. **[Phase 1] 구조화된 프롬프트:** 시스템 프롬프트를 Markdown/XML 구조로 개선하여 응답 신뢰도 향상.
2. **[Phase 2] 세션 메모리 도입:** 파일 기반 또는 메모리 기반의 세션 히스토리 기능 추가.
3. **[Phase 3] 응답 검증기 (Validator):** LLM 응답이 올바른 JSON/XML인지 체크하고 필요시 재시도하는 로직 추가.
