# 빠른 시작 가이드

## 🚀 3단계로 시작하기

### 1단계: 의존성 설치
```bash
pip install flask pyserial numpy
```

### 2단계: RS485 구성 (필요한 경우)
```bash
# RS485 장치 확인
ls -l /dev/ttyUSB*

# 장치가 다른 경우 설정 파일 편집
vim config/system_config.json
# "port": "/dev/ttyUSB0"를 해당 장치로 변경
```

### 3단계: 대시보드 실행
```bash
python scripts/run_monitoring_dashboard.py
```

### 4단계: 대시보드 접속
브라우저에서 열기: **http://localhost:5000**

---

## 🎛️ 대시보드 사용하기

### 서비스 시작
1. http://localhost:5000 열기
2. 서비스 카드의 **"시작"** 버튼 클릭
3. 또는 **"모든 서비스 시작"** 클릭

### 진동 데이터 보기
- **진동 모니터링** 패널 확인
- 실시간 X, Y, Z축 데이터 확인
- 경고 알림 모니터링

### 스케줄 설정
1. 기본값: **오전 8:30 - 오후 7:00**
2. 변경하려면 **"스케줄 편집"** 클릭
3. 필요에 따라 **"수동 재정의"** 활성화/비활성화

---

## ⚙️ 구성 파일

`config/system_config.json` 편집:

```json
{
  "vibration": {
    "sensor": {
      "port": "/dev/ttyUSB0",     ← RS485 장치 경로
      "baudrate": 9600,            ← 센서 보드레이트와 일치
      "protocol": "modbus"         ← 또는 "ascii"
    }
  },
  "scheduler": {
    "work_hours": {
      "start": "08:30",            ← 시작 시간
      "end": "19:00"               ← 종료 시간
    }
  }
}
```

---

## 🐳 Docker (선택사항)

```bash
# 빌드
docker build -t monitoring-system .

# 실행
docker run -p 5000:5000 \
  --device=/dev/ttyUSB0 \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/data:/app/data \
  monitoring-system
```

---

## 🔧 문제 해결

### RS485 센서에 접근할 수 없나요?
```bash
sudo chmod 666 /dev/ttyUSB0
```

### 포트 5000이 이미 사용 중인가요?
`config/system_config.json` 편집:
```json
"web_server": {
  "port": 5001  ← 다른 포트로 변경
}
```

### 서비스가 시작되지 않나요?
- 카메라 존재 확인: `ls /dev/video0`
- RS485 연결 확인: `ls /dev/ttyUSB0`
- 대시보드 서비스 카드에서 오류 확인

---

## 📖 전체 문서

- **전체 가이드**: `docs/MONITORING_SYSTEM_GUIDE.md`
- **메인 README**: `README_MONITORING.md`
- **요약**: `IMPLEMENTATION_SUMMARY.md`

---

## ✨ 기능

- ✅ **진동 모니터링** - RS485 센서
- ✅ **작업 스케줄러** - 자동 오전 8:30 - 오후 7:00
- ✅ **웹 대시보드** - 실시간 모니터링
- ✅ **경고** - 4단계 임계값
- ✅ **데이터 로깅** - CSV 및 JSON
- ✅ **Docker 지원** - X11 불필요

---

**완료! 이제 모니터링을 시작할 준비가 되었습니다! 🎉**
