# 🧪 MQTT 로컬 테스트 가이드

**목적**: Jetson에서 MQTT 기능을 로컬로 테스트하기

**작성일**: 2025-11-11

---

## 📋 개요

### 실제 환경 vs 테스트 환경

#### 실제 환경 (배포):
```
로봇 PC (MQTT Broker - mosquitto)
    ↕️
Jetson1, Jetson2 (MQTT Client - paho-mqtt)
```

#### 테스트 환경 (개발):
```
Jetson (MQTT Broker + Client 둘 다)
  ↕️ localhost 통신
Jetson (자기 자신과 통신)
```

---

## 🔧 설치 과정

### 1단계: mosquitto 설치 (5분)

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

## ⚙️ Config 설정 (로컬 테스트용)

### Jetson1 설정

```bash
nano ~/jetson-food-ai/jetson1_monitoring/config.json
```

**수정**:
```json
{
  "mqtt_enabled": true,
  "mqtt_broker": "localhost",
  "mqtt_port": 1883,
  "mqtt_topic_stirfry_food_type": "stirfry/food_type",
  "mqtt_topic_stirfry_control": "stirfry/control"
}
```

---

### Jetson2 설정

```bash
nano ~/jetson-food-ai/jetson2_frying_ai/config_jetson2.json
```

**수정**:
```json
{
  "mqtt_enabled": true,
  "mqtt_broker": "localhost",
  "mqtt_port": 1883,
  "mqtt_topic_food_type": "frying/food_type",
  "mqtt_topic_frying_control": "frying/control"
}
```

**저장**: `Ctrl+O` → `Enter` → `Ctrl+X`

---

## 🧪 테스트 방법

### 테스트 시나리오 1: Jetson1 (볶음) 자동 시작/종료

#### 준비:
```bash
# 터미널 1: Jetson1 프로그램 실행
cd ~/jetson-food-ai/jetson1_monitoring
python3 JETSON1_INTEGRATED.py
```

#### 테스트:
```bash
# 터미널 2: MQTT 테스트 스크립트 실행
cd ~/jetson-food-ai
python3 test_mqtt_publish.py

# Broker IP: localhost (그냥 엔터)
# 선택: 4번 (볶음 음식 종류 - 자동 시작)
# 음식 종류: 테스트볶음밥
```

**확인 사항**:
- ✅ 터미널 1에서 `[MQTT] 볶음 음식 종류 수신: 테스트볶음밥` 출력
- ✅ 터미널 1에서 `[MQTT] 자동 녹화 시작` 출력
- ✅ GUI에서 "녹화 시작" 버튼 비활성화, "녹화 중지" 버튼 활성화
- ✅ 3초마다 이미지 저장 시작

#### 종료 테스트:
```bash
# 터미널 2에서 다시
python3 test_mqtt_publish.py

# 선택: 5번 (볶음 종료 신호)
```

**확인 사항**:
- ✅ 터미널 1에서 `[MQTT] 자동 녹화 중지` 출력
- ✅ `[볶음] 메타데이터 저장 완료` 출력
- ✅ GUI에서 버튼 상태 복구
- ✅ `~/StirFry_Data/` 폴더에 데이터 저장됨

---

### 테스트 시나리오 2: Jetson2 (튀김) 자동 시작/종료

#### 준비:
```bash
# 터미널 1: Jetson2 프로그램 실행
cd ~/jetson-food-ai/jetson2_frying_ai
python3 JETSON2_INTEGRATED.py
```

#### 테스트:
```bash
# 터미널 2: MQTT 테스트
cd ~/jetson-food-ai
python3 test_mqtt_publish.py

# Broker IP: localhost
# 선택: 6번 (튀김 음식 종류 - 자동 시작)
# 음식 종류: 테스트치킨
```

**확인 사항**:
- ✅ 터미널 1에서 `[MQTT] 음식 종류 수신: 테스트치킨` 출력
- ✅ 터미널 1에서 `[MQTT] 자동 수집 시작` 출력
- ✅ GUI에서 "수집 시작" 버튼 비활성화
- ✅ 3초마다 이미지 저장 (4대 카메라 - 튀김솥 2개 + 바스켓 2개)

#### 종료 테스트:
```bash
# 터미널 2
python3 test_mqtt_publish.py

# 선택: 7번 (튀김 종료 신호)
```

**확인 사항**:
- ✅ 터미널 1에서 `[MQTT] 자동 수집 중지` 출력
- ✅ metadata.json 생성
- ✅ `~/AI_Data/FryingData/` 및 `~/AI_Data/BucketData/` 폴더에 데이터 저장

---

## 🔍 MQTT 메시지 모니터링

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
stirfry/food_type 테스트볶음밥
stirfry/control stop
frying/food_type 테스트치킨
frying/control stop
```

---

### 방법 2: mosquitto_pub로 직접 메시지 발행

```bash
# 볶음 시작
mosquitto_pub -h localhost -t "stirfry/food_type" -m "테스트볶음밥"

# 볶음 종료
mosquitto_pub -h localhost -t "stirfry/control" -m "stop"

# 튀김 시작
mosquitto_pub -h localhost -t "frying/food_type" -m "테스트치킨"

# 튀김 종료
mosquitto_pub -h localhost -t "frying/control" -m "stop"
```

---

## 📊 데이터 확인

### Jetson1 (볶음) 데이터 확인

```bash
# 세션 폴더 확인
ls -lh ~/StirFry_Data/

# 최신 세션 확인
ls -lh ~/StirFry_Data/$(ls -t ~/StirFry_Data/ | head -n1)/

# 메타데이터 확인
cat ~/StirFry_Data/$(ls -t ~/StirFry_Data/ | head -n1)/metadata.json | python3 -m json.tool
```

**폴더 구조**:
```
~/StirFry_Data/
  └── 20251111_143000/          # 세션 ID
      ├── metadata.json          # 메타데이터
      └── 테스트볶음밥/          # 음식 종류
          ├── left/              # 왼쪽 카메라
          │   └── left_143010_123.jpg
          └── right/             # 오른쪽 카메라
              └── right_143010_456.jpg
```

---

### Jetson2 (튀김) 데이터 확인

```bash
# 세션 폴더 확인
ls -lh ~/AI_Data/FryingData/
ls -lh ~/AI_Data/BucketData/

# 최신 세션 확인
ls -lh ~/AI_Data/FryingData/$(ls -t ~/AI_Data/FryingData/ | head -n1)/

# 메타데이터 확인
cat ~/AI_Data/FryingData/$(ls -t ~/AI_Data/FryingData/ | head -n1)/metadata.json | python3 -m json.tool
```

**폴더 구조**:
```
~/AI_Data/
  ├── FryingData/
  │   └── session_20251111_143000/  # 세션 ID
  │       ├── metadata.json
  │       ├── camera_0/             # 튀김솥 왼쪽
  │       └── camera_1/             # 튀김솥 오른쪽
  └── BucketData/
      └── session_20251111_143000/
          ├── metadata.json
          ├── camera_2/             # 바스켓 왼쪽
          └── camera_3/             # 바스켓 오른쪽
```

---

## 🔄 실제 배포로 전환

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
sudo systemctl restart jetson2-monitor.service
```

---

## 🛠️ 문제 해결

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

### 문제 2: test_mqtt_publish.py 에러

**증상**:
```
ModuleNotFoundError: No module named 'paho'
```

**해결**:
```bash
pip3 install paho-mqtt
```

---

### 문제 3: 메시지 보내도 반응 없음

**확인 순서**:

1. **Jetson 프로그램이 실행 중인지**:
```bash
ps aux | grep JETSON
```

2. **MQTT 연결 성공했는지 (로그 확인)**:
```bash
sudo journalctl -u jetson2-monitor.service -n 50 | grep MQTT
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

## 📋 로컬 테스트 체크리스트

**설치**:
- [ ] mosquitto 설치 완료
- [ ] mosquitto 서비스 실행 중
- [ ] 포트 1883 열림 확인
- [ ] paho-mqtt 설치 확인

**설정**:
- [ ] config.json에서 `mqtt_enabled: true`
- [ ] config.json에서 `mqtt_broker: localhost`

**테스트**:
- [ ] Jetson1: 볶음 자동 시작 작동
- [ ] Jetson1: 볶음 자동 종료 작동
- [ ] Jetson1: 데이터 저장 확인
- [ ] Jetson2: 튀김 자동 시작 작동
- [ ] Jetson2: 튀김 자동 종료 작동
- [ ] Jetson2: 데이터 저장 확인 (4대 카메라)

**배포 준비**:
- [ ] 로봇 PC IP 확인
- [ ] config.json에 로봇 PC IP 입력
- [ ] 서비스 재시작
- [ ] 로봇 PC에서 메시지 수신 확인

---

## 💡 유용한 명령어 모음

```bash
# mosquitto 서비스 관리
sudo systemctl start mosquitto
sudo systemctl stop mosquitto
sudo systemctl restart mosquitto
sudo systemctl status mosquitto

# MQTT 메시지 구독 (모니터링)
mosquitto_sub -h localhost -t "#" -v

# MQTT 메시지 발행 (테스트)
mosquitto_pub -h localhost -t "test" -m "hello"

# 로그 실시간 확인
sudo journalctl -u jetson2-monitor.service -f

# 데이터 폴더 확인
ls -lh ~/StirFry_Data/
ls -lh ~/AI_Data/FryingData/
ls -lh ~/AI_Data/BucketData/

# 최신 메타데이터 확인
cat ~/StirFry_Data/$(ls -t ~/StirFry_Data/ | head -n1)/metadata.json | python3 -m json.tool
```

---

## 🎯 정리

### 로컬 테스트 (개발 단계):
- Jetson에 mosquitto 설치
- `mqtt_broker: localhost`
- 자기 자신과 통신
- test_mqtt_publish.py로 메시지 발행

### 실제 배포 (운영 단계):
- 로봇 PC에만 mosquitto 필요
- `mqtt_broker: 로봇PC_IP`
- 로봇 PC와 통신
- 로봇 PC에서 메시지 발행

**로컬 테스트로 MQTT 자동 시작/종료 기능을 완벽하게 검증할 수 있습니다!** ✅

---

**작성일**: 2025-11-11
**버전**: 1.0
