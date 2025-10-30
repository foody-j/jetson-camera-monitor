# Jetson Orin용 카메라 배포 가이드

이 가이드는 Jetson Orin 장치에서 Docker를 사용하여 카메라 지원이 있는 AI 모니터링 시스템을 배포하는 방법을 설명합니다.

## 빠른 시작

```bash
# 배포 스크립트 실행 가능하게 만들기
chmod +x deploy_camera.sh

# 배포 스크립트 실행
./deploy_camera.sh
```

스크립트가 수행할 작업:
1. 카메라 사용 가능 여부 확인
2. nvargus-daemon 차단 문제 처리
3. GUI 디스플레이를 위한 X11 설정
4. Docker 이미지 빌드
5. 카메라 액세스로 컨테이너 시작
6. 카메라 작동 확인

## 수동 배포

수동으로 배포하려는 경우:

### 1. 카메라 액세스 수정 (필요한 경우)

```bash
# USB 카메라를 차단하는 nvargus-daemon 중지
sudo systemctl stop nvargus-daemon

# 카메라에 액세스할 수 있는지 확인
v4l2-ctl --device=/dev/video0 --all
```

### 2. GUI를 위한 X11 설정

```bash
# Docker가 X 서버에 액세스하도록 허용
xhost +local:docker

# X11 인증 파일 생성
touch /tmp/.docker.xauth
xauth nlist $DISPLAY | sed -e 's/^..../ffff/' | xauth -f /tmp/.docker.xauth nmerge -
chmod 644 /tmp/.docker.xauth
```

### 3. 빌드 및 실행

```bash
# Docker 이미지 빌드
docker-compose build

# 컨테이너 시작
docker-compose up -d

# 컨테이너 진입
docker-compose exec ai-dev bash
```

### 4. 컨테이너에서 카메라 테스트

```bash
# 컨테이너 내부에서 카메라 테스트
python3 test_camera_simple.py

# 또는 GUI 실행
python3 camera_monitor/monitor.py
```

## 아키텍처

### Docker 구성

**Dockerfile:**
- `nvcr.io/nvidia/l4t-jetpack:r36.4.0` 기반
- OpenCV, V4L2 및 GStreamer 포함
- 카메라 및 GPU 액세스 구성됨

**docker-compose.yml:**
- `/dev/video0` 및 `/dev/video1`을 컨테이너에 매핑
- GUI를 위한 X11 포워딩 활성화
- GPU 액세스를 위한 NVIDIA 런타임
- 호스트 네트워크 모드

### 카메라 액세스

시스템은 **V4L2** (Video4Linux2) 백엔드를 사용하여 USB 카메라에 직접 액세스합니다:

```python
cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
```

## 문제 해결

### 카메라 사용 중 오류

**문제:** `Device '/dev/video0' is busy`

**해결책:**
```bash
# 카메라를 사용하는 프로세스 확인
sudo fuser -v /dev/video0

# nvargus-daemon 중지
sudo systemctl stop nvargus-daemon
```

### 컨테이너에서 카메라가 감지되지 않음

**문제:** 컨테이너가 `/dev/video0`을 볼 수 없음

**해결책:**
`docker-compose.yml`에 다음이 있는지 확인:
```yaml
devices:
  - /dev/video0:/dev/video0
  - /dev/video1:/dev/video1
group_add:
  - video
```

### GUI가 표시되지 않음

**문제:** `cv2.imshow()`가 창을 표시하지 않음

**해결책:**
```bash
# 호스트에서 Docker X11 액세스 허용
xhost +local:docker

# 컨테이너에서 DISPLAY 변수 확인
docker-compose exec ai-dev echo $DISPLAY
# :0 또는 :1과 같은 것을 표시해야 함
```

### 권한 거부됨

**문제:** 카메라에 액세스할 때 `Permission denied`

**해결책:**
```bash
# 사용자를 video 그룹에 추가 (호스트에서)
sudo usermod -aG video $USER

# 로그아웃 후 다시 로그인하거나 재부팅
```

## 다른 Jetson 장치로 배포

### 1. Docker 이미지 내보내기

개발 Jetson에서:
```bash
# 이미지 빌드 및 저장
docker-compose build
docker save jp6:jp6 | gzip > jetson-camera-ai.tar.gz
```

### 2. 대상 Jetson으로 전송

```bash
# 대상 장치로 복사
scp jetson-camera-ai.tar.gz user@target-jetson:/tmp/

# 또는 USB 드라이브, 네트워크 공유 등 사용
```

### 3. 대상 Jetson에 로드

대상 Jetson에서:
```bash
# 이미지 로드
gunzip -c jetson-camera-ai.tar.gz | docker load

# 프로젝트 파일 복사
git clone <your-repo> my_ai_project
cd my_ai_project

# 배포 실행
chmod +x deploy_camera.sh
./deploy_camera.sh
```

### 대안: Docker 레지스트리 사용

```bash
# 레지스트리에 태그 및 푸시
docker tag jp6:jp6 your-registry.com/jetson-camera-ai:latest
docker push your-registry.com/jetson-camera-ai:latest

# 대상 Jetson에서 풀 및 실행
docker pull your-registry.com/jetson-camera-ai:latest
docker-compose up -d
```

## 애플리케이션 실행

### 대화형 모드

```bash
# 컨테이너 시작 및 bash 진입
docker-compose exec ai-dev bash

# 컨테이너 내부
cd /project
python3 camera_monitor/monitor.py
```

### 백그라운드 모드

```bash
# 백그라운드에서 애플리케이션 실행
docker-compose exec -d ai-dev python3 src/monitoring/frying/run_monitor.py

# 로그 보기
docker-compose logs -f
```

### 자동 시작

`docker-compose.yml` 편집:
```yaml
services:
  ai-dev:
    command: python3 /project/src/monitoring/frying/run_monitor.py
    restart: unless-stopped
```

## 중요 참고사항

### nvargus-daemon

- **목적:** CSI 카메라용 NVIDIA 카메라 데몬
- **문제:** USB 카메라 액세스를 차단할 수 있음
- **해결책:** USB 카메라 사용 시 중지: `sudo systemctl stop nvargus-daemon`
- **복원:** 나중에 다시 시작: `sudo systemctl start nvargus-daemon`

### 카메라 장치 번호

- `/dev/video0` - 일반적으로 메인 카메라 스트림
- `/dev/video1` - 일반적으로 카메라 메타데이터/제어
- 둘 다 Docker에 매핑되어야 함

### GPU 액세스

컨테이너에 NVIDIA GPU 액세스가 구성되어 있습니다:
- CUDA, cuDNN 사용 가능
- TensorRT 사용 가능
- 컨테이너에서 `nvidia-smi` 사용하여 확인

## 지원

문제가 있는 경우:
1. 로그 확인: `docker-compose logs`
2. 먼저 호스트에서 카메라 테스트: `v4l2-ctl --list-devices`
3. 컨테이너가 장치에 액세스할 수 있는지 확인: `docker-compose exec ai-dev ls -l /dev/video0`
