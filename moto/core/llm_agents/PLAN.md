# 🛡️ Project: LLM-Driven Adaptive AWS Honeypot

이 문서는 Moto를 단순한 Mock 서버에서 **지능형 적응형 기만 시스템(Intelligent Adaptive Deception System)**으로 진화시키기 위한 최종 설계도입니다.

---

## 📖 [Chapter 1] 배경 및 기술적 타당성 (Why this way?)

### **1.1 가로채기 방식의 선택 (Interception Strategy)**
- **기존 방식:** 모든 API를 일일이 구현 (Static Mocking).
- **우리의 방식:** 구현된 것은 Moto가 처리하고, 미구현된 것만 LLM이 실시간 생성 (Dynamic Fallback).
- **이유:** AWS의 1,000개 이상의 서비스를 사람이 모두 코드로 짤 수는 없습니다. LLM은 '설명서(API Reference)'를 학습했으므로 미구현 기능을 즉시 대체할 수 있는 유일한 대안입니다.

### **1.2 참조 모델 및 유사 사례**
- **Cowrie (SSH Honeypot):** 명령어를 가로채어 가짜 결과를 보여주는 방식에서 영감을 얻음.
- **Honeytokens:** 실제 데이터처럼 보이지만 추적용인 데이터를 LLM이 동적으로 생성하여 공격자에게 노출함.

---

## 🛠️ [Chapter 2] 시스템 아키텍처 (Architecture)

### **2.1 데이터 흐름도 (Data Flow)**
1. **User Request:** 공격자가 `aws s3api list-objects` 실행.
2. **Moto Check:** `responses.py`가 해당 액션을 처리할 수 있는지 확인.
3. **Trigger Fallback:** `NotImplementedError` 발생 시, 요청의 7가지 핵심 정보를 추출.
4. **Agent Orchestration:** `agent.py`가 서비스별 프로토콜(XML/JSON)을 결정.
5. **LLM Synthesis:** OpenCode를 통해 GPT-5가 AWS 규격에 맞는 가짜 데이터를 생성.
6. **Deceptive Response:** 공격자에게 실제와 같은 응답 반환.

---

## 📅 [Chapter 3] A-to-Z 실행 단계 (The 26 Steps)

### **[Phase A-E: 전처리 및 환경]**
- **Step A:** `opencode` CLI 인증 체계 분석 (설정 파일 위치 및 토큰 유효성 확인).
- **Step B:** 파이썬 `requests` 라이브러리 대신 내장 `urllib`를 사용하여 의존성 최소화.
- **Step C:** 서비스별 응답 프로토콜(Query-XML, REST-JSON 등) 매핑 테이블 정교화.

### **[Phase F-J: 통신 및 인증]**
- **Step F:** `providers.py`에 재시도 로직(Exponential Backoff) 추가.
- **Step G:** CLI 토큰 만료 시 사용자에게 알림을 주는 모니터링 코드 작성.
- **Step H:** 대량 요청(DDoS 공격 등) 시 LLM 비용 폭증을 막기 위한 Rate Limiting 로직 설계.

### **[Phase K-O: 에이전트 브레인]**
- **Step K:** **Few-shot Prompting** 도입 (각 서비스별 성공 응답 샘플 1개씩 프롬프트에 포함).
- **Step L:** 시간차 공격(Timing Attack) 방지: LLM 응답 대기 시간 동안 가짜 "로딩 지연"을 무작위로 추가하여 인간미 부여.
- **Step M:** 동적 리소스 ID 생성기 구현 (이전 요청에서 생성한 ID를 기억하여 응답의 일관성 유지).

### **[Phase P-T: 코어 통합]**
- **Step P:** `responses.py`의 `call_action` 메서드를 감싸는 **Wrapper Decorator** 방식 검토 (코드 침습 최소화).
- **Step Q:** 모든 Fallback 요청을 로깅하여 나중에 어떤 미구현 기능이 자주 호출되는지 분석.

### **[Phase U-Z: 검증 및 고도화]**
- **Step U:** 주요 10대 AWS 서비스(EC2, S3, IAM, RDS 등)에 대한 유닛 테스트 수행.
- **Step V:** 공격 시나리오 시뮬레이션: 실제 해킹 툴(Metasploit 등)을 사용한 방어력 측정.
- **Step Z:** 최종적으로 이 시스템을 하나의 패키지로 묶어 배포 가능한 상태로 만듦.

---

## 📊 [Chapter 4] 성능 지표 (KPI)
- **응답 일치율:** 실제 AWS 응답과 LLM 응답의 구조적 일치도 95% 이상 목표.
- **생존 시간:** 공격자가 Honeypot임을 눈치채는 데 걸리는 평균 시간(MTTD) 300% 향상.
- **비용 효율성:** 수동 개발 대비 미구현 기능 대응 비용 99% 절감.
