# MQTT 빠른 시작 가이드

**대상**: 운영자 및 초보 사용자
**소요 시간**: 10분

## 개요

이 시스템은 로봇 PC가 MQTT를 통해 젯슨1(볶음)과 젯슨2(튀김)를 제어합니다.

```
로봇 PC (MQTT Broker) ↔ 젯슨1 (볶음) + 젯슨2 (튀김)
```

---

## 기본 개념

### 젯슨1 (볶음 스테이션)
- 2개 조리솥: POT1 (왼쪽), POT2 (오른쪽)
- 각 솥은 독립적으로 작동
- 사람 감지 → 로봇 PC 자동 켜기/끄기

### 젯슨2 (튀김 스테이션)
- 2개 튀김솥: POT1 (왼쪽), POT2 (오른쪽)
- 각 솥은 독립적으로 작동
- 온도 센서 데이터 수신 (기름 온도, 탐침 온도)
- 바구니 감지 (음식 들어옴/나감)

---

## 시작하기

### 1. 조리 시작 (자동)

로봇 PC에서 음식 종류를 보내면 자동으로 녹화/수집이 시작됩니다.

#### 젯슨1 POT1 볶음 시작
```bash
mosquitto_pub -h localhost -t "stirfry/pot1/food_type" -m "kimchi"
```

#### 젯슨2 POT1 튀김 시작
```bash
mosquitto_pub -h localhost -t "frying/pot1/food_type" -m "chicken"
```

**음식 종류는 아무 문자열이나 가능합니다**: `"김치"`, `"치킨"`, `"볶음밥"` 등

---

### 2. 조리 중지 (자동)

stop 명령을 보내면 자동으로 녹화/수집이 중지됩니다.

#### 젯슨1 POT1 볶음 중지
```bash
mosquitto_pub -h localhost -t "stirfry/pot1/control" -m "stop"
```

#### 젯슨2 POT1 튀김 중지
```bash
mosquitto_pub -h localhost -t "frying/pot1/control" -m "stop"
```

---

### 3. 온도 데이터 전송 (젯슨2만 해당)

젯슨2는 로봇 PC로부터 온도 데이터를 수신합니다.

```bash
# POT1 기름 온도
mosquitto_pub -h localhost -t "frying/pot1/oil_temp" -m "180.5"

# POT1 탐침 온도 (음식 중심부)
mosquitto_pub -h localhost -t "frying/pot1/probe_temp" -m "75.0"
```

**자동 완료**: 탐침 온도가 75°C 이상이면 자동으로 완료 마킹됩니다.

---

## 토픽 요약

### 조리 시작 (음식 종류 전송)

| 장치 | 솥 | 토픽 | 예시 |
|------|-----|-------|------|
| 젯슨1 | POT1 | `stirfry/pot1/food_type` | `"kimchi"` |
| 젯슨1 | POT2 | `stirfry/pot2/food_type` | `"bacon"` |
| 젯슨2 | POT1 | `frying/pot1/food_type` | `"chicken"` |
| 젯슨2 | POT2 | `frying/pot2/food_type` | `"shrimp"` |

### 조리 중지

| 장치 | 솥 | 토픽 | 명령 |
|------|-----|-------|------|
| 젯슨1 | POT1 | `stirfry/pot1/control` | `"stop"` |
| 젯슨1 | POT2 | `stirfry/pot2/control` | `"stop"` |
| 젯슨2 | POT1 | `frying/pot1/control` | `"stop"` |
| 젯슨2 | POT2 | `frying/pot2/control` | `"stop"` |

### 온도 데이터 (젯슨2만)

| 토픽 | 설명 | 형식 |
|------|------|------|
| `frying/pot1/oil_temp` | POT1 기름 온도 | `"180.5"` |
| `frying/pot1/probe_temp` | POT1 탐침 온도 | `"75.0"` |
| `frying/pot2/oil_temp` | POT2 기름 온도 | `"182.0"` |
| `frying/pot2/probe_temp` | POT2 탐침 온도 | `"76.5"` |

---

## 전체 시나리오 예제

### 시나리오: POT1에서 김치볶음 조리

```bash
# 1. 조리 시작
mosquitto_pub -h localhost -t "stirfry/pot1/food_type" -m "김치볶음"

# 2. 5분간 조리...

# 3. 조리 완료, 중지
mosquitto_pub -h localhost -t "stirfry/pot1/control" -m "stop"
```

### 시나리오: POT1에서 치킨 튀김 조리

```bash
# 1. 조리 시작
mosquitto_pub -h localhost -t "frying/pot1/food_type" -m "치킨"

# 2. 온도 데이터 전송 (1초마다)
mosquitto_pub -h localhost -t "frying/pot1/oil_temp" -m "165.0"
mosquitto_pub -h localhost -t "frying/pot1/probe_temp" -m "45.0"

# 3. 온도 상승 중...
mosquitto_pub -h localhost -t "frying/pot1/probe_temp" -m "75.5"
# → 75°C 도달, 자동 완료 마킹!

# 4. 조리 완료, 중지
mosquitto_pub -h localhost -t "frying/pot1/control" -m "stop"
```

---

## 메시지 모니터링

모든 MQTT 메시지를 실시간으로 보려면:

```bash
# 모든 메시지 구독
mosquitto_sub -h localhost -t "#" -v

# 젯슨1 관련 메시지만
mosquitto_sub -h localhost -t "stirfry/#" -v

# 젯슨2 관련 메시지만
mosquitto_sub -h localhost -t "frying/#" -v
mosquitto_sub -h localhost -t "jetson2/#" -v
```

---

## 문제 해결

### MQTT 브로커가 실행 중인지 확인

```bash
sudo systemctl status mosquitto
```

**브로커가 꺼져 있다면:**
```bash
sudo systemctl start mosquitto
sudo systemctl enable mosquitto
```

### 젯슨 프로그램이 실행 중인지 확인

```bash
# 젯슨1
ps aux | grep JETSON1

# 젯슨2
ps aux | grep JETSON2
```

### 로그 확인

```bash
# 젯슨1 로그
sudo journalctl -u jetson1-monitor.service -f

# 젯슨2 로그
sudo journalctl -u jetson2-frying-ai.service -f
```

---

## 다음 단계

- [API 레퍼런스](../02_reference/API_REFERENCE_ko.md) - 모든 토픽과 메시지 형식
- [로컬 테스트 가이드](../03_guides/LOCAL_TESTING_ko.md) - 로컬에서 테스트하기
- [시스템 아키텍처](../04_architecture/SYSTEM_OVERVIEW_ko.md) - 전체 시스템 이해하기

---

**버전**: 1.0
**최종 업데이트**: 2025-11-24
