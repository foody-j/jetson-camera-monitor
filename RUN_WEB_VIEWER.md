# 웹 뷰어 실행 가이드

## 1. Flask 설치 (Docker 컨테이너 내부에서)

```bash
# Docker 컨테이너 접속
docker exec -it my-dev-container bash

# Flask 설치
pip3 install flask
# 또는
apt-get update && apt-get install -y python3-flask
```

## 2. 웹 뷰어 실행

```bash
# 컨테이너 내부에서 실행
cd /home/dkutest/my_ai_project
python3 frying_ai/web_viewer.py

# 또는 포트 변경
python3 frying_ai/web_viewer.py 8080
```

## 3. Windows에서 접속

### 방법 A: SSH 포트 포워딩 (추천)

**VSCode SSH 설정에서:**
1. VSCode에서 `F1` → `Remote-SSH: Settings` 선택
2. 또는 `.ssh/config` 파일 직접 수정:

```
Host jetson-nano
    HostName <Jetson-IP>
    User dkutest
    LocalForward 5000 localhost:5000
```

3. SSH 재연결
4. Windows 브라우저에서: `http://localhost:5000`

### 방법 B: 수동 SSH 터널링

```bash
# Windows PowerShell 또는 CMD에서 실행 (VSCode와 별도)
ssh -L 5000:localhost:5000 dkutest@<Jetson-IP>
```

그 다음 Windows 브라우저에서: `http://localhost:5000`

### 방법 C: 직접 접속 (같은 네트워크)

Jetson과 Windows가 같은 네트워크에 있다면:
- `http://<Jetson-IP>:5000`

## 4. 사용 방법

### 웹 인터페이스:
1. **세션 시작**:
   - 음식 종류 선택 (치킨, 새우, 감자 등)
   - 메모 입력 (온도 설정, 특이사항 등)
   - "세션 시작" 버튼 클릭

2. **실시간 모니터링**:
   - 왼쪽: 실시간 카메라 + 세그멘테이션 오버레이 (초록색)
   - 오른쪽: 현재 특징 (음식 영역, 갈색 비율, 황금색 비율 등)

3. **완료 마킹**:
   - 음식이 다 익었을 때
   - 탐침 온도계로 측정한 온도 입력
   - "완료 마킹" 버튼 클릭

4. **세션 종료**:
   - "세션 종료" 버튼 클릭
   - 데이터가 `frying_dataset/` 폴더에 저장됨

## 5. 출력 데이터

```
frying_dataset/
└── chicken_20251027_153045/
    ├── images/           # 타임스탬프 이미지
    │   ├── t0000.jpg
    │   ├── t0001.jpg
    │   └── ...
    ├── session_data.json # 전체 세션 데이터
    └── sensor_log.csv    # 센서 타임라인
```

## 6. 문제 해결

### "카메라를 열 수 없습니다"
```bash
# 카메라 디바이스 확인
ls -l /dev/video*

# 권한 확인
sudo chmod 666 /dev/video0
```

### "포트가 이미 사용 중"
```bash
# 다른 포트로 실행
python3 frying_ai/web_viewer.py 8080
```

### "브라우저에서 접속 안 됨"
- SSH 포트 포워딩 확인
- 방화벽 확인
- Docker 컨테이너 포트 매핑 확인:
  ```bash
  docker ps  # PORTS 열 확인
  ```

## 7. Docker Compose에 포트 추가 (필요시)

`docker-compose.yml`에 포트 매핑 추가:

```yaml
services:
  dev:
    ports:
      - "5000:5000"
```

그 다음:
```bash
docker-compose down
docker-compose up -d
```

## 기능

✅ 실시간 MJPEG 스트리밍
✅ 자동 세그멘테이션 오버레이
✅ 실시간 특징 추출 (색상, 비율 등)
✅ 세션 제어 (시작/완료/종료)
✅ 자동 데이터 저장
✅ 반응형 웹 디자인
✅ SSH/Docker 환경 최적화
