Camera Monitor 📹
실시간 카메라 모니터링, 녹화, 움직임 감지, 스크린샷 기능을 제공하는 Python 모듈
📁 구조 (3개 파일)
camera_monitor/
├── camera_base.py       # 카메라 기본 조작
├── recorder.py          # 녹화 + 스크린샷 
├── motion_detector.py   # 움직임 감지
├── monitor.py          # 메인 모니터링 클래스
├── __init__.py         # 패키지 초기화
└── example.py          # 사용 예시
🚀 설치 및 시작
1. 필수 라이브러리
bashpip install opencv-python numpy
2. 가장 간단한 사용
pythonimport camera_monitor

# 한 줄로 시작!
camera_monitor.start_monitoring()
⌨️ 조작법
키기능Q종료S스크린샷R녹화 시작/중지M움직임 감지 토글I상태 정보H도움말
💡 주요 사용 패턴
전체 기능 사용
pythonimport camera_monitor

monitor = camera_monitor.CameraMonitor()

if monitor.initialize():
    # 움직임 감지 활성화
    monitor.motion_detector.enable()
    
    # 모니터링 시작
    monitor.start_monitoring()
필요한 기능만 사용
python# 카메라 + 녹화만
camera = camera_monitor.CameraBase()
recorder = camera_monitor.MediaRecorder(camera)

# 카메라 + 움직임 감지만  
camera = camera_monitor.CameraBase()
detector = camera_monitor.MotionDetector()
콜백 함수 사용
pythondef on_motion_detected(frame):
    print("움직임 감지!")
    # 알림, 로깅 등 추가 작업

monitor = camera_monitor.CameraMonitor()
monitor.motion_detector.set_callback(on_motion_detected)
monitor.start_monitoring()
🔧 주요 클래스

CameraBase: 카메라 기본 조작
MediaRecorder: 녹화 + 스크린샷
MotionDetector: 움직임 감지
CameraMonitor: 모든 기능 통합

📁 출력 파일
프로젝트_폴더/
├── recordings/          # 녹화 파일들
└── screenshots/         # 스크린샷들
🛠️ 문제 해결
python# 사용 가능한 카메라 확인
cameras = camera_monitor.get_available_cameras()
print("사용 가능한 카메라:", cameras)

# 시스템 정보 확인
info = camera_monitor.get_info()
print(info)
자세한 사용법은 example.py를 참조하세요! 🎯