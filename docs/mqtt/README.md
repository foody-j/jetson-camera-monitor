# MQTT 통신 문서

**버전**: 2.0 (POT1/POT2 분리)
**최종 업데이트**: 2025-11-24

---

## 목차

- [빠른 시작](#빠른-시작)
- [문서 구조](#문서-구조)
- [시스템 개요](#시스템-개요)
- [주요 기능](#주요-기능)

---

## 빠른 시작

### 처음 사용하시나요?

1. **[빠른 시작 가이드](01_quickstart/QUICK_START_ko.md)** ← 여기서 시작하세요!
   - 10분 안에 MQTT 사용법 익히기
   - 기본 명령어와 사용 예시

### 문제가 발생했나요?

- **[트러블슈팅 가이드](03_guides/TROUBLESHOOTING_ko.md)**
  - 일반적인 문제와 해결 방법
  - 진단 체크리스트
  - 로그 확인 방법

---

## 문서 구조

### 📚 01. 빠른 시작

초보자를 위한 간단한 시작 가이드

| 문서 | 설명 | 대상 |
|------|------|------|
| [QUICK_START_ko.md](01_quickstart/QUICK_START_ko.md) | 10분 빠른 시작 | 운영자, 초보자 |

---

### 📖 02. API 레퍼런스

모든 토픽, 메시지 형식, 설정 정보

| 문서 | 설명 | 대상 |
|------|------|------|
| [API_REFERENCE_ko.md](02_reference/API_REFERENCE_ko.md) | 전체 MQTT API 레퍼런스 | 개발자, 통합 담당자 |

**포함 내용**:
- 젯슨1/젯슨2 토픽 전체 목록
- 메시지 형식 및 예시
- 설정 파일 구조
- 메타데이터 JSON 포맷

---

### 📝 03. 가이드

실무에 필요한 세부 가이드

| 문서 | 설명 | 대상 |
|------|------|------|
| [LOCAL_TESTING_ko.md](03_guides/LOCAL_TESTING_ko.md) | 로컬 환경에서 테스트하기 | 개발자 |
| [VIBRATION_CONTROL_ko.md](03_guides/VIBRATION_CONTROL_ko.md) | 진동 센서 원격 제어 | 운영자, 개발자 |
| [TROUBLESHOOTING_ko.md](03_guides/TROUBLESHOOTING_ko.md) | 문제 해결 가이드 | 모든 사용자 |

---

### 🏗️ 04. 아키텍처

시스템 구조와 설계

| 문서 | 설명 | 대상 |
|------|------|------|
| [SYSTEM_OVERVIEW_ko.md](04_architecture/SYSTEM_OVERVIEW_ko.md) | 전체 시스템 아키텍처 | 개발자, 시스템 관리자 |

**포함 내용**:
- 네트워크 다이어그램
- 데이터 흐름
- POT1/POT2 독립 제어
- 성능 지표
- 보안 고려사항

---

### 💻 05. 코드 예제

실전 코드 예제

| 문서 | 설명 | 대상 |
|------|------|------|
| [CODE_EXAMPLES_ko.md](05_examples/CODE_EXAMPLES_ko.md) | Python, C# 코드 예제 | 개발자 |

**포함 내용**:
- Python (paho-mqtt) 예제
- C# (MQTTnet) 예제
- 멀티 POT 제어
- 에러 처리

---

## 시스템 개요

### 장치 구성

```
로봇 PC (MQTT Broker)
    ↓
    ├── 젯슨1 (볶음 스테이션)
    │   ├── POT1: 왼쪽 볶음솥
    │   └── POT2: 오른쪽 볶음솥
    │
    └── 젯슨2 (튀김 스테이션)
        ├── POT1: 왼쪽 튀김솥
        └── POT2: 오른쪽 튀김솥
```

### 주요 토픽

#### 젯슨1 (볶음)

| 방향 | 토픽 | 설명 |
|------|------|------|
| → 젯슨1 | `stirfry/pot1/food_type` | POT1 조리 시작 |
| → 젯슨1 | `stirfry/pot1/control` | POT1 조리 중지 |
| → 젯슨1 | `stirfry/pot2/food_type` | POT2 조리 시작 |
| → 젯슨1 | `stirfry/pot2/control` | POT2 조리 중지 |
| 젯슨1 → | `jetson1/system/ai_mode` | AI 모드 상태 |
| 젯슨1 → | `frying_ai/jetson1/robot/control` | 사람 감지 |

#### 젯슨2 (튀김)

| 방향 | 토픽 | 설명 |
|------|------|------|
| → 젯슨2 | `frying/pot1/food_type` | POT1 조리 시작 |
| → 젯슨2 | `frying/pot1/control` | POT1 조리 중지 |
| → 젯슨2 | `frying/pot2/food_type` | POT2 조리 시작 |
| → 젯슨2 | `frying/pot2/control` | POT2 조리 중지 |
| → 젯슨2 | `frying/pot1/oil_temp` | POT1 기름 온도 |
| → 젯슨2 | `frying/pot1/probe_temp` | POT1 탐침 온도 |
| 젯슨2 → | `jetson2/system/ai_mode` | AI 모드 상태 |
| 젯슨2 → | `jetson2/observe/status` | 바구니 상태 |

---

## 주요 기능

### 1. 자동 시작/중지

음식 종류를 전송하면 **자동으로 녹화/수집이 시작**되고, stop 명령으로 **자동으로 중지**됩니다.

```bash
# 시작
mosquitto_pub -h localhost -t "stirfry/pot1/food_type" -m "김치볶음"

# 중지
mosquitto_pub -h localhost -t "stirfry/pot1/control" -m "stop"
```

### 2. POT1/POT2 독립 제어

각 솥은 **완전히 독립적**으로 작동합니다.
- 별도의 세션 ID
- 동시 작동 가능
- 간섭 없음

### 3. 온도 기반 자동 완료 (젯슨2)

탐침 온도가 **75°C 이상**이면 자동으로 완료 마킹됩니다.

### 4. 진동 센서 원격 제어

MQTT로 진동 센서를 **원격으로 시작/중지**할 수 있습니다.

```bash
mosquitto_pub -h localhost -t "calibration/vibration/control" -m "START"
mosquitto_pub -h localhost -t "calibration/vibration/control" -m "STOP"
```

### 5. 사람 감지 및 릴레이 제어 (젯슨1)

사람을 감지하면 **로봇 PC 전원을 자동으로 켜고/끕니다**.

---

## 빠른 명령어 참고

### 젯슨1 POT1 제어

```bash
# 시작
mosquitto_pub -h localhost -t "stirfry/pot1/food_type" -m "김치볶음"

# 중지
mosquitto_pub -h localhost -t "stirfry/pot1/control" -m "stop"
```

### 젯슨2 POT1 제어

```bash
# 시작
mosquitto_pub -h localhost -t "frying/pot1/food_type" -m "치킨"

# 온도 전송
mosquitto_pub -h localhost -t "frying/pot1/oil_temp" -m "180.5"
mosquitto_pub -h localhost -t "frying/pot1/probe_temp" -m "75.0"

# 중지
mosquitto_pub -h localhost -t "frying/pot1/control" -m "stop"
```

### 메시지 모니터링

```bash
# 모든 메시지 보기
mosquitto_sub -h localhost -t "#" -v

# 젯슨1 메시지만
mosquitto_sub -h localhost -t "stirfry/#" -v
mosquitto_sub -h localhost -t "jetson1/#" -v

# 젯슨2 메시지만
mosquitto_sub -h localhost -t "frying/#" -v
mosquitto_sub -h localhost -t "jetson2/#" -v
```

---

## 학습 경로

### 초보자

1. [빠른 시작 가이드](01_quickstart/QUICK_START_ko.md) - 기본 사용법
2. [로컬 테스트 가이드](03_guides/LOCAL_TESTING_ko.md) - 로컬에서 실습
3. [트러블슈팅 가이드](03_guides/TROUBLESHOOTING_ko.md) - 문제 해결

### 개발자

1. [API 레퍼런스](02_reference/API_REFERENCE_ko.md) - 전체 API 이해
2. [코드 예제](05_examples/CODE_EXAMPLES_ko.md) - 실전 코드 작성
3. [시스템 아키텍처](04_architecture/SYSTEM_OVERVIEW_ko.md) - 시스템 구조 파악

### 시스템 관리자

1. [시스템 아키텍처](04_architecture/SYSTEM_OVERVIEW_ko.md) - 전체 시스템 이해
2. [API 레퍼런스](02_reference/API_REFERENCE_ko.md) - 설정 및 구성
3. [트러블슈팅 가이드](03_guides/TROUBLESHOOTING_ko.md) - 문제 진단

---

## 버전 정보

### 현재 버전: 2.0

**주요 변경사항** (v2.0):
- POT1/POT2 분리 (독립 제어)
- 젯슨2 관찰 카메라 공유
- 온도 기반 자동 완료
- 진동 센서 MQTT 제어

**호환성**:
- Jetson Software v2.0 이상
- MQTT Broker: mosquitto
- Python: paho-mqtt >= 1.6.1
- C#: MQTTnet

---

## 기여 및 지원

### 문서 개선

문서 개선 제안이나 오류 발견 시:
1. 이슈 등록
2. 수정 제안
3. 예제 추가

### 기술 지원

1. [트러블슈팅 가이드](03_guides/TROUBLESHOOTING_ko.md) 확인
2. 로그 분석
3. 설정 파일 검토

---

## 관련 문서

- `배포가이드.md` - 시스템 배포 가이드
- `GPIO_SSR_연결가이드.md` - 릴레이 하드웨어 설정
- `test_mqtt_publish.py` - MQTT 테스트 도구

---

## 라이선스

© 2025 Jetson Food AI Project

---

**문서 버전**: 1.0
**소프트웨어 버전**: 2.0
**최종 업데이트**: 2025-11-24
