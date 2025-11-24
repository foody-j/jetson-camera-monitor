# MQTT 트러블슈팅 가이드

**목적**: MQTT 관련 문제 해결 방법

---

## 목차

- [연결 문제](#연결-문제)
- [메시지 송수신 문제](#메시지-송수신-문제)
- [데이터 저장 문제](#데이터-저장-문제)
- [성능 문제](#성능-문제)
- [진동 센서 문제](#진동-센서-문제)

---

## 연결 문제

### 문제: MQTT 브로커에 연결되지 않음

**증상**:
```
[MQTT] 연결 실패
Connection refused
```

**원인 및 해결**:

#### 1. 브로커가 실행 중이 아님

**확인**:
```bash
sudo systemctl status mosquitto
```

**해결**:
```bash
sudo systemctl start mosquitto
sudo systemctl enable mosquitto
```

#### 2. 포트가 열려있지 않음

**확인**:
```bash
sudo netstat -tulpn | grep 1883
```

**해결**:
- 포트가 보이지 않으면 mosquitto 재시작
- 방화벽 확인 (ufw, iptables)

#### 3. 잘못된 브로커 주소

**확인**:
```bash
cat ~/jetson-food-ai/jetson1_monitoring/config.json | grep mqtt_broker
```

**해결**:
- `mqtt_broker` 값이 올바른지 확인
- 로컬 테스트: `localhost`
- 실제 배포: 로봇 PC IP 주소 (예: `192.168.0.14`)

#### 4. 네트워크 연결 문제

**확인**:
```bash
# 로봇 PC에 ping 테스트
ping 192.168.0.14

# mosquitto 테스트
mosquitto_sub -h 192.168.0.14 -t test -v
```

**해결**:
- 네트워크 케이블 확인
- IP 주소 확인
- 라우터/스위치 확인

#### 5. 이더넷 DHCP 자동 할당 안 됨

**증상**:
- 이더넷 케이블 연결했지만 MQTT 브로커(로봇 PC)와 연결 안 됨
- WiFi는 되지만 이더넷은 안 됨

**원인**:
- 로봇 PC와 젯슨 간 직접 이더넷 연결 시 DHCP 서버 없음
- IP 자동 할당 실패

**해결**: IPv4 수동 설정

1. **네트워크 설정 열기**:
   - Settings → Network → Wired → 톱니바퀴 아이콘

2. **IPv4 탭 선택**:
   - Method: `Manual` 선택

3. **IP 정보 입력**:
   ```
   Address: 192.168.0.15  (젯슨1) 또는 192.168.0.16 (젯슨2)
   Netmask: 255.255.255.0
   Gateway: 192.168.0.100  (로봇 PC IP)
   ```

4. **DNS 설정**:
   ```
   DNS: 192.168.0.100
   ```

5. **적용 및 재연결**:
   - Apply 버튼 클릭
   - 이더넷 연결 끄고 다시 켜기

6. **연결 확인**:
   ```bash
   # IP 확인
   ip addr show eth0  # 또는 해당 인터페이스 이름

   # 로봇 PC에 ping 테스트
   ping 192.168.0.100

   # MQTT 연결 테스트
   mosquitto_sub -h 192.168.0.100 -t test -v
   ```

**참고**:
- 각 젯슨마다 다른 IP 사용 (충돌 방지)
- 젯슨1: `192.168.0.15`
- 젯슨2: `192.168.0.16`
- 로봇 PC: `192.168.0.100`

---

### 문제: MQTT가 자꾸 재연결됨

**증상**:
```
[MQTT] 연결 끊김
[MQTT] 재연결 중...
```

**원인 및 해결**:

#### 1. 네트워크 불안정

**확인**:
```bash
# 패킷 손실 확인
ping -c 100 192.168.0.14
```

**해결**:
- 네트워크 케이블 교체
- 스위치/라우터 재시작
- 무선 연결의 경우 유선으로 변경

#### 2. Keep-Alive 타임아웃

**확인**:
```bash
cat config.json | grep mqtt
```

**해결**:
- QoS 레벨 확인 (권장: QoS 1)
- Keep-Alive 시간 늘리기 (기본: 60초)

#### 3. 브로커 과부하

**확인 (로봇 PC에서)**:
```bash
# CPU/메모리 사용량 확인
top

# mosquitto 로그 확인
sudo journalctl -u mosquitto -n 100
```

**해결**:
- 발행 주기 늘리기 (`mqtt_publish_interval`)
- 불필요한 클라이언트 연결 끊기

---

## 메시지 송수신 문제

### 문제: 메시지를 보내도 반응이 없음

**증상**:
- mosquitto_pub으로 메시지 전송했지만 젯슨에서 반응 없음

**원인 및 해결**:

#### 1. MQTT가 비활성화됨

**확인**:
```bash
cat config.json | grep mqtt_enabled
```

**해결**:
```json
{
  "mqtt_enabled": true
}
```

#### 2. 토픽 이름 오류

**확인**:
- 토픽 이름은 대소문자 구분
- 정확한 토픽명 확인: [API 레퍼런스](../02_reference/API_REFERENCE_ko.md)

**해결**:
```bash
# 올바른 토픽명 사용
mosquitto_pub -h localhost -t "stirfry/pot1/food_type" -m "kimchi"

# 틀린 예시:
# stirfry/pot1/FoodType (X)
# StirFry/pot1/food_type (X)
```

#### 3. 젯슨 프로그램이 실행 중이 아님

**확인**:
```bash
ps aux | grep JETSON1
ps aux | grep JETSON2
```

**해결**:
```bash
# 젯슨1 시작
cd ~/jetson-food-ai/jetson1_monitoring
python3 JETSON1_INTEGRATED.py

# 또는 서비스로 시작
sudo systemctl start jetson1-monitor.service
```

#### 4. MQTT 구독이 안 됨

**확인**:
```bash
# 젯슨 로그에서 구독 메시지 확인
sudo journalctl -u jetson1-monitor -n 50 | grep "구독"
sudo journalctl -u jetson1-monitor -n 50 | grep "subscribe"
```

**해결**:
- 프로그램 재시작
- config.json 설정 확인

---

### 문제: 메시지는 받지만 자동 시작이 안 됨

**증상**:
- 로그에는 메시지 수신이 보이지만 녹화/수집이 시작되지 않음

**원인 및 해결**:

#### 1. 잘못된 메시지 형식

**확인**:
```bash
# 로그에서 수신된 메시지 확인
sudo journalctl -u jetson1-monitor -n 20
```

**해결**:
- 음식 종류는 빈 문자열이 아니어야 함
- control 명령은 정확히 `"stop"`이어야 함

#### 2. 이미 녹화/수집 중

**확인**:
- GUI에서 버튼 상태 확인
- 로그에서 `이미 녹화 중` 메시지 확인

**해결**:
- 먼저 stop 명령으로 중지 후 다시 시작

#### 3. 카메라 문제

**확인**:
```bash
# 카메라 장치 확인
ls -l /dev/video*
```

**해결**:
- 카메라 케이블 확인
- 카메라 권한 확인
- 프로그램 재시작

---

## 데이터 저장 문제

### 문제: 녹화는 되지만 데이터가 저장되지 않음

**증상**:
- 녹화/수집은 시작되지만 폴더에 파일이 없음

**원인 및 해결**:

#### 1. 디렉토리 권한 문제

**확인**:
```bash
ls -la ~/AI_Data/
ls -la ~/AI_Data/StirFryData/
ls -la ~/AI_Data/FryingData/
```

**해결**:
```bash
# 디렉토리 생성 및 권한 설정
mkdir -p ~/AI_Data/StirFryData
mkdir -p ~/AI_Data/FryingData
chmod 755 ~/AI_Data/
chmod 755 ~/AI_Data/StirFryData/
chmod 755 ~/AI_Data/FryingData/
```

#### 2. 디스크 공간 부족

**확인**:
```bash
df -h ~
```

**해결**:
- 불필요한 파일 삭제
- 오래된 세션 데이터 백업 후 삭제

#### 3. 프레임 스킵 설정

**확인**:
```bash
cat config.json | grep frame_skip
cat config.json | grep collection_interval
```

**해결**:
- `frame_skip`이 너무 크면 저장 주기가 길어짐
- 젯슨1: 기본 90 (30fps 기준 3초마다 1장)
- 젯슨2: `collection_interval` 기본 3초

---

### 문제: 메타데이터 파일이 생성되지 않음

**증상**:
- 이미지는 저장되지만 metadata.json 또는 session_info.json이 없음

**원인 및 해결**:

#### 1. stop 명령을 보내지 않음

**해결**:
- 녹화/수집을 정상적으로 중지해야 메타데이터 생성됨
```bash
mosquitto_pub -h localhost -t "stirfry/pot1/control" -m "stop"
```

#### 2. 프로그램 강제 종료

**해결**:
- 프로그램을 강제 종료하지 말고 정상적으로 중지
- GUI "중지" 버튼 사용 또는 MQTT stop 명령 사용

---

## 성능 문제

### 문제: 메시지 전송이 지연됨

**증상**:
- mosquitto_pub으로 전송했지만 몇 초 후에 수신됨

**원인 및 해결**:

#### 1. 네트워크 레이턴시

**확인**:
```bash
ping 192.168.0.14
```

**해결**:
- 네트워크 케이블 교체
- 스위치 교체
- 유선 연결 사용

#### 2. QoS 레벨

**확인**:
```bash
cat config.json | grep mqtt_qos
```

**해결**:
- QoS 0: 최대 1회 전달 (빠르지만 손실 가능)
- QoS 1: 최소 1회 전달 (권장)
- QoS 2: 정확히 1회 전달 (느림)

#### 3. 브로커 과부하

**확인 (로봇 PC)**:
```bash
top
sudo journalctl -u mosquitto -f
```

**해결**:
- 발행 주기 조정
- 불필요한 토픽 구독 해제

---

### 문제: 이미지 저장이 느림

**증상**:
- 프레임 드롭 발생
- 로그에 경고 메시지

**원인 및 해결**:

#### 1. 디스크 I/O 병목

**확인**:
```bash
iostat -x 1
```

**해결**:
- SSD 사용
- JPEG 품질 낮추기 (jpeg_quality: 100 → 85)

#### 2. CPU 과부하

**확인**:
```bash
top
```

**해결**:
- 프레임 스킵 늘리기
- 해상도 낮추기
- 불필요한 프로세스 종료

---

## 진동 센서 문제

### 문제: 진동 센서가 시작되지 않음

**증상**:
- START 명령을 보내도 프로세스가 시작되지 않음

**원인 및 해결**:

#### 1. vibration_sensor_simple.py 파일 없음

**확인**:
```bash
ls -l ~/jetson-food-ai/vibration_sensor_simple.py
```

**해결**:
- 파일 복원 또는 재배포

#### 2. USB-RS485 장치 연결 안 됨

**확인**:
```bash
ls -l /dev/ttyUSB*
```

**해결**:
- USB 케이블 재연결
- USB 포트 변경
- 장치 권한 확인:
```bash
sudo chmod 666 /dev/ttyUSB0
```

#### 3. Python 의존성 문제

**확인**:
```bash
cd ~/jetson-food-ai
python3 vibration_sensor_simple.py
```

**해결**:
```bash
pip3 install -r requirements.txt
```

---

### 문제: 진동 센서 CSV 파일이 생성되지 않음

**증상**:
- 프로세스는 실행되지만 CSV 파일이 없음

**원인 및 해결**:

#### 1. 디렉토리 권한 문제

**확인**:
```bash
ls -la ~/data/vibration_data/
```

**해결**:
```bash
mkdir -p ~/data/vibration_data/
chmod 755 ~/data/vibration_data/
```

#### 2. STOP 명령을 보내지 않음

**해결**:
- 정상적으로 STOP 명령 전송
```bash
mosquitto_pub -h localhost -t "calibration/vibration/control" -m "STOP"
```

---

## 로그 확인 방법

### 실시간 로그 모니터링

```bash
# 젯슨1
sudo journalctl -u jetson1-monitor -f

# 젯슨2
sudo journalctl -u jetson2-frying-ai -f

# MQTT 관련만 필터링
sudo journalctl -u jetson1-monitor -f | grep MQTT

# 에러만 필터링
sudo journalctl -u jetson1-monitor -f | grep -i error
```

### 최근 로그 확인

```bash
# 최근 100줄
sudo journalctl -u jetson1-monitor -n 100

# 특정 시간대
sudo journalctl -u jetson1-monitor --since "2025-11-24 14:00:00"
```

---

## 진단 체크리스트

### MQTT 기본 체크리스트

- [ ] mosquitto 서비스 실행 중
- [ ] 포트 1883 열림
- [ ] config.json에서 mqtt_enabled: true
- [ ] 브로커 주소가 올바름
- [ ] 젯슨 프로그램 실행 중
- [ ] 토픽 이름이 정확함
- [ ] 네트워크 연결 정상

### 자동 시작/종료 체크리스트

- [ ] 올바른 토픽으로 메시지 전송
- [ ] 음식 종류가 빈 문자열이 아님
- [ ] 카메라가 정상 작동
- [ ] 디스크 공간 충분
- [ ] 디렉토리 권한 정상

### 진동 센서 체크리스트

- [ ] vibration_sensor_simple.py 파일 존재
- [ ] USB-RS485 장치 연결 (/dev/ttyUSB0)
- [ ] 진동 센서 3개 연결 (UID 0x50, 0x51, 0x52)
- [ ] 데이터 폴더 권한 정상
- [ ] STOP 명령으로 정상 종료

---

## 추가 지원

### 문제가 해결되지 않을 때

1. 로그 전체 확인
```bash
sudo journalctl -u jetson1-monitor --no-pager > ~/jetson1_log.txt
sudo journalctl -u jetson2-frying-ai --no-pager > ~/jetson2_log.txt
```

2. 설정 파일 확인
```bash
cat ~/jetson-food-ai/jetson1_monitoring/config.json
cat ~/jetson-food-ai/jetson2_frying_ai/config_jetson2.json
```

3. 시스템 정보 확인
```bash
uname -a
df -h
free -h
ps aux | grep python
```

---

**버전**: 1.0
**최종 업데이트**: 2025-11-24
