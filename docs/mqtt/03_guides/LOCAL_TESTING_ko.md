# MQTT 로컬 테스트 가이드

**목적**: 젯슨에서 MQTT 기능을 로컬로 테스트하기

---

## 개요

### 실제 환경 vs 테스트 환경

#### 실제 환경 (배포):
```
로봇 PC (MQTT Broker - mosquitto)
    ↕
젯슨1, 젯슨2 (MQTT Client - paho-mqtt)
```

#### 테스트 환경 (개발):
```
젯슨 (MQTT Broker + Client 둘 다)
  ↕ localhost 통신
젯슨 (자기 자신과 통신)
```

---

## 설치 과정

### 1단계: mosquitto 설치

```bash
# apt 업데이트
sudo apt update

# mosquitto 서버 + CLI 도구 설치
sudo apt install -y mosquitto mosquitto-clients

# 설치 확인
mosquitto -h
mosquitto_pub --help
```

---

### 2단계: mosquitto 서비스 시작

```bash
# 서비스 시작
sudo systemctl start mosquitto

# 부팅 시 자동 시작 설정
sudo systemctl enable mosquitto

# 상태 확인
sudo systemctl status mosquitto
```

**정상 출력**:
```
● mosquitto.service - Mosquitto MQTT Broker
   Loaded: loaded (/lib/systemd/system/mosquitto.service; enabled)
   Active: active (running) since ...
```

---

### 3단계: 포트 확인

```bash
# MQTT 기본 포트(1883) 확인
sudo netstat -tulpn | grep 1883
```

**정상 출력**:
```
tcp        0      0 0.0.0.0:1883            0.0.0.0:*               LISTEN      12345/mosquitto
```

---

## Config 설정 (로컬 테스트용)

### 젯슨1 설정

```bash
nano ~/jetson-food-ai/jetson1_monitoring/config.json
```

**수정**:
```json
{
  "mqtt_enabled": true,
  "mqtt_broker": "localhost",
  "mqtt_port": 1883
}
```

---

### 젯슨2 설정

```bash
nano ~/jetson-food-ai/jetson2_frying_ai/config_jetson2.json
```

**수정**:
```json
{
  "mqtt_enabled": true,
  "mqtt_broker": "localhost",
  "mqtt_port": 1883
}
```

**저장**: `Ctrl+O` → `Enter` → `Ctrl+X`

---

## 테스트 시나리오

### 시나리오 1: 젯슨1 POT1 볶음 자동 시작/종료

#### 준비:
```bash
# 터미널 1: 젯슨1 프로그램 실행
cd ~/jetson-food-ai/jetson1_monitoring
python3 JETSON1_INTEGRATED.py
```

#### 테스트:
```bash
# 터미널 2: 볶음 시작
mosquitto_pub -h localhost -t "stirfry/pot1/food_type" -m "테스트볶음밥"

# 5초 대기 후...

# 볶음 중지
mosquitto_pub -h localhost -t "stirfry/pot1/control" -m "stop"
```

**확인 사항**:
- ✅ 터미널 1에서 `[MQTT POT1] 음식 종류 수신: 테스트볶음밥` 출력
- ✅ `[볶음 POT1] 녹화 시작` 출력
- ✅ GUI에서 POT1 녹화 버튼 상태 변경
- ✅ 3초마다 이미지 저장
- ✅ `[볶음 POT1] 녹화 중지` 출력
- ✅ `~/AI_Data/StirFryData/pot1/` 폴더에 데이터 저장

---

### 시나리오 2: 젯슨2 POT1 튀김 자동 시작/종료

#### 준비:
```bash
# 터미널 1: 젯슨2 프로그램 실행
cd ~/jetson-food-ai/jetson2_frying_ai
python3 JETSON2_INTEGRATED.py
```

#### 테스트:
```bash
# 터미널 2: 튀김 시작
mosquitto_pub -h localhost -t "frying/pot1/food_type" -m "테스트치킨"

# 온도 데이터 전송
mosquitto_pub -h localhost -t "frying/pot1/oil_temp" -m "165.5"
mosquitto_pub -h localhost -t "frying/pot1/probe_temp" -m "45.0"

# 잠시 대기 후 온도 상승
mosquitto_pub -h localhost -t "frying/pot1/probe_temp" -m "75.5"
# → 자동 완료 마킹!

# 튀김 중지
mosquitto_pub -h localhost -t "frying/pot1/control" -m "stop"
```

**확인 사항**:
- ✅ `[MQTT POT1] 음식 종류 수신: 테스트치킨` 출력
- ✅ `[튀김 POT1] 수집 시작` 출력
- ✅ GUI에서 온도 데이터 표시
- ✅ 탐침 온도 75°C 도달 시 완료 마킹
- ✅ `~/AI_Data/FryingData/pot1/` 폴더에 데이터 저장

---

### 시나리오 3: 멀티 POT 동시 작업

```bash
# 젯슨1 POT1, POT2 동시 시작
mosquitto_pub -h localhost -t "stirfry/pot1/food_type" -m "김치볶음"
mosquitto_pub -h localhost -t "stirfry/pot2/food_type" -m "야채볶음"

# 5분 후 POT1만 중지
mosquitto_pub -h localhost -t "stirfry/pot1/control" -m "stop"

# POT2는 계속 조리...
# 10분 후 POT2 중지
mosquitto_pub -h localhost -t "stirfry/pot2/control" -m "stop"
```

**확인 사항**:
- ✅ POT1, POT2 독립적으로 작동
- ✅ 각각 별도의 세션 ID 생성
- ✅ 간섭 없이 정상 동작

---

## MQTT 메시지 모니터링

### 방법 1: mosquitto_sub로 모든 메시지 보기

```bash
# 모든 메시지 구독 (디버깅용)
mosquitto_sub -h localhost -t "#" -v

# 특정 토픽만 구독
mosquitto_sub -h localhost -t "stirfry/#" -v
mosquitto_sub -h localhost -t "frying/#" -v
```

**출력 예시**:
```
stirfry/pot1/food_type 테스트볶음밥
stirfry/pot1/control stop
frying/pot1/food_type 테스트치킨
frying/pot1/oil_temp 180.5
```

---

### 방법 2: Python 테스트 도구 사용 (추천)

```bash
cd ~/jetson-food-ai
python3 test_mqtt_publish.py

# 대화형 메뉴:
# 1. Broker IP 입력 (localhost)
# 2. 메시지 타입 선택
# 3. 자동으로 올바른 형식의 메시지 발행
```

---

## 데이터 확인

### 젯슨1 (볶음) 데이터 확인

```bash
# 세션 폴더 확인
ls -lh ~/AI_Data/StirFryData/pot1/
ls -lh ~/AI_Data/StirFryData/pot2/

# 최신 세션 확인
ls -lh ~/AI_Data/StirFryData/pot1/$(ls -t ~/AI_Data/StirFryData/pot1/ | head -n1)/

# 메타데이터 확인
cat ~/AI_Data/StirFryData/pot1/$(ls -t ~/AI_Data/StirFryData/pot1/ | head -n1)/*/metadata.json | python3 -m json.tool
```

**폴더 구조**:
```
~/AI_Data/StirFryData/
├── pot1/
│   └── session_20251124_143000/
│       └── 테스트볶음밥/
│           ├── camera_0/
│           │   └── camera_0_*.jpg
│           └── metadata.json
└── pot2/
    └── session_20251124_143100/
        └── 야채볶음/
            ├── camera_1/
            │   └── camera_1_*.jpg
            └── metadata.json
```

---

### 젯슨2 (튀김) 데이터 확인

```bash
# 세션 폴더 확인
ls -lh ~/AI_Data/FryingData/pot1/
ls -lh ~/AI_Data/FryingData/pot2/

# 메타데이터 확인
find ~/AI_Data/FryingData/ -name "session_info.json" -exec cat {} \; | python3 -m json.tool
```

**폴더 구조**:
```
~/AI_Data/FryingData/
├── pot1/
│   └── session_20251124_143000/
│       └── 테스트치킨/
│           ├── camera_0/  (튀김 왼쪽)
│           ├── camera_2/  (관찰 왼쪽 - 공유)
│           ├── camera_3/  (관찰 오른쪽 - 공유)
│           └── session_info.json
└── pot2/
    └── session_20251124_143100/
        └── 새우/
            ├── camera_1/  (튀김 오른쪽)
            ├── camera_2/  (관찰 왼쪽 - 공유)
            ├── camera_3/  (관찰 오른쪽 - 공유)
            └── session_info.json
```

---

## 실제 배포로 전환

### 테스트 완료 후 실제 배포 시:

```bash
# Config 수정
nano ~/jetson-food-ai/jetson2_frying_ai/config_jetson2.json
```

**변경**:
```json
{
  "mqtt_enabled": true,
  "mqtt_broker": "192.168.x.x",  // ← 로봇 PC의 실제 IP
  "mqtt_port": 1883
}
```

**저장 후 재시작**:
```bash
sudo systemctl restart jetson2-frying-ai.service
```

---

## 문제 해결

### 문제 1: mosquitto 연결 실패

**증상**:
```
[MQTT] 연결 실패
Connection refused
```

**확인**:
```bash
# mosquitto 실행 중인지 확인
sudo systemctl status mosquitto

# 포트 확인
sudo netstat -tulpn | grep 1883
```

**해결**:
```bash
sudo systemctl start mosquitto
sudo systemctl enable mosquitto
```

---

### 문제 2: 메시지 보내도 반응 없음

**확인 순서**:

1. **젯슨 프로그램이 실행 중인지**:
```bash
ps aux | grep JETSON
```

2. **MQTT 연결 성공했는지 (로그 확인)**:
```bash
sudo journalctl -u jetson1-monitor.service -n 50 | grep MQTT
sudo journalctl -u jetson2-frying-ai.service -n 50 | grep MQTT
```

3. **mosquitto_sub로 메시지 수신 확인**:
```bash
# 터미널 1: 모든 메시지 구독
mosquitto_sub -h localhost -t "#" -v

# 터미널 2: 메시지 발행
mosquitto_pub -h localhost -t "test" -m "hello"
```

터미널 1에 `test hello` 출력되어야 함

---

### 문제 3: 데이터가 저장되지 않음

**확인**:
```bash
# 디렉토리 권한 확인
ls -la ~/AI_Data/

# 디스크 공간 확인
df -h ~

# 프레임 스킵 설정 확인
cat ~/jetson-food-ai/jetson1_monitoring/config.json | grep frame_skip
```

---

## 로컬 테스트 체크리스트

**설치**:
- [ ] mosquitto 설치 완료
- [ ] mosquitto 서비스 실행 중
- [ ] 포트 1883 열림 확인
- [ ] paho-mqtt 설치 확인

**설정**:
- [ ] config.json에서 `mqtt_enabled: true`
- [ ] config.json에서 `mqtt_broker: localhost`

**테스트**:
- [ ] 젯슨1 POT1: 자동 시작 작동
- [ ] 젯슨1 POT1: 자동 종료 작동
- [ ] 젯슨1 POT2: 자동 시작 작동
- [ ] 젯슨1 POT2: 자동 종료 작동
- [ ] 젯슨2 POT1: 자동 시작 작동
- [ ] 젯슨2 POT1: 온도 데이터 수신
- [ ] 젯슨2 POT1: 자동 완료 마킹
- [ ] 젯슨2 POT1: 자동 종료 작동
- [ ] 멀티 POT 동시 작동 확인
- [ ] 데이터 저장 확인

**배포 준비**:
- [ ] 로봇 PC IP 확인
- [ ] config.json에 로봇 PC IP 입력
- [ ] 서비스 재시작
- [ ] 로봇 PC에서 메시지 수신 확인

---

## 정리

### 로컬 테스트 (개발 단계):
- 젯슨에 mosquitto 설치
- `mqtt_broker: localhost`
- 자기 자신과 통신
- mosquitto_pub로 메시지 발행

### 실제 배포 (운영 단계):
- 로봇 PC에만 mosquitto 필요
- `mqtt_broker: 로봇PC_IP`
- 로봇 PC와 통신
- 로봇 PC에서 메시지 발행

**로컬 테스트로 MQTT 자동 시작/종료 기능을 완벽하게 검증할 수 있습니다!**

---

**버전**: 1.0
**최종 업데이트**: 2025-11-24
