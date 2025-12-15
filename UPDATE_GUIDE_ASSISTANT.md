# Jetson 업데이트 지침서 (조수용)

**최종 업데이트:** 2025-12-15

이 문서는 조수가 현장에서 Jetson 1, 2번에 git pull로 코드 업데이트를 할 때 따라할 지침서입니다.

---

## 업데이트 전 확인사항

1. **어떤 Jetson인지 확인**
   - Jetson #1: 볶음 모니터링 (사람 감지)
   - Jetson #2: 튀김 AI (바켓 감지)

---

## 업데이트 절차 (순서대로 따라하기)

### 1단계: 서비스 중지

```bash
# Jetson1인 경우
sudo systemctl stop jetson1-monitor

# Jetson2인 경우
sudo systemctl stop jetson2-monitor
```

**확인:** GUI 창이 닫히면 성공

---

### 2단계: git pull 실행

```bash
cd ~/jetson-food-ai
git pull
```

**정상 출력 예시:**
```
remote: Enumerating objects: 10, done.
...
Fast-forward
 jetson1_monitoring/JETSON1_INTEGRATED.py | 50 ++++++++++++++++++++
 1 file changed, 50 insertions(+)
```

**충돌 발생 시 (에러 메시지 나오면):**
```bash
# 로컬 변경사항 버리고 서버 버전으로 덮어쓰기
git stash
git pull
```

---

### 3단계: 캐시 삭제

```bash
# Jetson1
rm -rf ~/jetson-food-ai/jetson1_monitoring/__pycache__

# Jetson2
rm -rf ~/jetson-food-ai/jetson2_frying_ai/__pycache__

# 공용
rm -rf ~/jetson-food-ai/src/__pycache__
rm -rf ~/jetson-food-ai/src/*/__pycache__
```

---

### 4단계: 서비스 재시작

```bash
# Jetson1인 경우
sudo systemctl start jetson1-monitor

# Jetson2인 경우
sudo systemctl start jetson2-monitor
```

---

### 5단계: 정상 동작 확인

```bash
# Jetson1인 경우
sudo journalctl -u jetson1-monitor -f

# Jetson2인 경우
sudo journalctl -u jetson2-monitor -f
```

**확인할 것:**
- [ ] GUI 창이 뜸
- [ ] 카메라 영상이 보임
- [ ] `[MQTT] 연결 성공` 메시지가 나옴
- [ ] 에러 메시지 없음

**로그 보기 종료:** `Ctrl+C`

---

## 빠른 명령어 (복사용)

### Jetson #1 전체 명령어

```bash
sudo systemctl stop jetson1-monitor
cd ~/jetson-food-ai && git pull
rm -rf ~/jetson-food-ai/jetson1_monitoring/__pycache__
rm -rf ~/jetson-food-ai/src/__pycache__ ~/jetson-food-ai/src/*/__pycache__
sudo systemctl start jetson1-monitor
sudo journalctl -u jetson1-monitor -f
```

### Jetson #2 전체 명령어

```bash
sudo systemctl stop jetson2-monitor
cd ~/jetson-food-ai && git pull
rm -rf ~/jetson-food-ai/jetson2_frying_ai/__pycache__
rm -rf ~/jetson-food-ai/src/__pycache__ ~/jetson-food-ai/src/*/__pycache__
sudo systemctl start jetson2-monitor
sudo journalctl -u jetson2-monitor -f
```

---

## 문제 발생 시

### 문제 1: git pull 에러 (충돌)

```
error: Your local changes to the following files would be overwritten by merge
```

**해결:**
```bash
git stash
git pull
```

---

### 문제 2: 서비스가 시작 안 됨

```bash
# 상태 확인
sudo systemctl status jetson1-monitor  # 또는 jetson2-monitor

# 로그 확인 (최근 50줄)
sudo journalctl -u jetson1-monitor -n 50 --no-pager
```

**담당자에게 로그 내용 전달**

---

### 문제 3: MQTT 연결 안 됨

```bash
# config 파일 확인 (Jetson1)
cat ~/jetson-food-ai/jetson1_monitoring/config.json | grep mqtt

# config 파일 확인 (Jetson2)
cat ~/jetson-food-ai/jetson2_frying_ai/config_jetson2.json | grep mqtt
```

**확인할 것:**
- `mqtt_enabled`: true 인지
- `mqtt_broker`: IP 주소가 맞는지

---

### 문제 4: 카메라가 안 보임

```bash
# 카메라 장치 확인
ls -l /dev/video*

# 카메라 재초기화
sudo ~/jetson-food-ai/init_gmsl_cameras.sh

# 서비스 재시작
sudo systemctl restart jetson1-monitor  # 또는 jetson2-monitor
```

---

## 체크리스트 (인쇄용)

### Jetson #1 업데이트

- [ ] 1. `sudo systemctl stop jetson1-monitor` 실행
- [ ] 2. `cd ~/jetson-food-ai && git pull` 실행
- [ ] 3. 캐시 삭제 실행
- [ ] 4. `sudo systemctl start jetson1-monitor` 실행
- [ ] 5. GUI 창 표시 확인
- [ ] 6. 카메라 영상 확인
- [ ] 7. MQTT 연결 확인

### Jetson #2 업데이트

- [ ] 1. `sudo systemctl stop jetson2-monitor` 실행
- [ ] 2. `cd ~/jetson-food-ai && git pull` 실행
- [ ] 3. 캐시 삭제 실행
- [ ] 4. `sudo systemctl start jetson2-monitor` 실행
- [ ] 5. GUI 창 표시 확인
- [ ] 6. 카메라 영상 확인
- [ ] 7. MQTT 연결 확인

---

## 주의사항

1. **반드시 서비스 중지 후 git pull** (안 그러면 파일 충돌 가능)
2. **git pull 후 캐시 삭제 필수** (안 하면 이전 코드가 실행될 수 있음)
3. **문제 발생 시 담당자에게 연락** (로그 내용 캡처해서 전달)

---

## 진동센서 문제 해결

### 증상: VEL/DISP가 0만 나옴 (ACC는 정상)

**원인:** 센서 전원 리셋 시 검출 주기(0x65)가 0으로 초기화됨

**해결:**
```bash
cd ~/jetson-food-ai
python3 fix_vibration_sensor.py
```

엔터 누르면 검출 주기를 50Hz로 설정하고 저장합니다.

**확인할 것:**
- USB 연결 확인: `ls /dev/ttyUSB*`
- 스크립트 실행 후 VEL/DISP 값이 0이 아닌지 확인

---

## 긴급 연락처

- 담당자: ________________
- 전화: ________________
