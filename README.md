# Jetson Camera Monitor 📹

NVIDIA Jetson을 위한 실시간 카메라 모니터링 시스템

## 🎯 주요 기능

- ✅ 실시간 카메라 스트리밍
- ✅ 비디오 녹화 (자동 해상도 조정)
- ✅ 움직임 감지 + 자동 스크린샷
- ✅ JSON 기반 설정 관리
- ✅ 헤드리스 모드 지원
- ✅ Docker 환경 최적화

## 🚀 빠른 시작

### 환경 요구사항
- NVIDIA Jetson (Orin, Xavier, Nano 등)
- Docker & Docker Compose
- Python 3.8+
- OpenCV

### 실행
```bash
# Docker로 실행
docker-compose -f docker-compose.camera.yml up -d

# 또는 직접 실행
python3 run_monitor.py