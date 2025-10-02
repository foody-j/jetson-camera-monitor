"""
Camera Monitor 사용 예시
"""

import camera_monitor


def example1_quick_start():
    """가장 간단한 사용법"""
    print("=== 예시 1: 빠른 시작 ===")
    
    # 한 줄로 시작
    camera_monitor.start_monitoring()


def example2_full_control():
    """모든 기능을 제어하는 방법"""
    print("=== 예시 2: 전체 제어 ===")
    
    # 모니터 생성
    monitor = camera_monitor.CameraMonitor(camera_index=0, resolution=(640, 480))
    
    # 초기화
    if monitor.initialize():
        # 움직임 감지 활성화
        monitor.motion_detector.enable()
        
        # 자동 녹화 시작
        monitor.toggle_recording()
        
        # 모니터링 시작
        monitor.start_monitoring()


def example3_individual_parts():
    """개별 컴포넌트만 사용하기"""
    print("=== 예시 3: 개별 컴포넌트 ===")
    
    # 카메라만 사용
    camera = camera_monitor.CameraBase()
    
    if camera.initialize():
        print("카메라 정보:", camera.get_info())
        
        # 한 장의 사진만 촬영하고 싶을 때
        recorder = camera_monitor.MediaRecorder(camera)
        ret, frame = camera.read_frame()
        if ret:
            recorder.take_screenshot(frame, "test.jpg")
        
        camera.release()


def example4_motion_only():
    """움직임 감지만 사용하기"""
    print("=== 예시 4: 움직임 감지만 ===")
    
    import cv2
    
    camera = camera_monitor.CameraBase()
    detector = camera_monitor.MotionDetector()
    
    def on_motion(frame):
        print("움직임 감지!")
    
    detector.set_callback(on_motion)
    detector.enable()
    
    if camera.initialize():
        print("움직임 감지 시작 (q로 종료)")
        while True:
            ret, frame = camera.read_frame()
            if ret:
                motion_detected, mask = detector.detect(frame)
                display_frame = detector.draw_motion_overlay(frame, motion_detected, mask)
                
                cv2.imshow('Motion Detection', display_frame)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        
        camera.release()
        cv2.destroyAllWindows()


def example5_custom_callback():
    """사용자 정의 콜백 사용"""
    print("=== 예시 5: 사용자 정의 콜백 ===")
    
    def my_frame_processor(frame):
        """매 프레임마다 호출될 함수"""
        # 여기에 원하는 처리 로직 추가
        # 예: 얼굴 인식, 객체 감지 등
        pass
    
    def my_motion_handler(frame):
        """움직임 감지 시 호출될 함수"""
        print("움직임 감지! 알림을 보냅니다.")
        # 여기에 이메일 전송, 알림 등 추가
    
    monitor = camera_monitor.CameraMonitor()
    
    # 콜백 설정
    monitor.set_frame_callback(my_frame_processor)
    monitor.motion_detector.set_callback(my_motion_handler)
    
    # 모니터링 시작
    monitor.start_monitoring()


def show_system_info():
    """시스템 정보 확인"""
    print("=== 시스템 정보 ===")
    info = camera_monitor.get_info()
    print(f"버전: {info['version']}")
    print(f"OpenCV: {info['opencv_version']}")
    print(f"사용 가능한 카메라: {info['available_cameras']}")
    print("==================")


def main():
    """메인 함수"""
    show_system_info()
    
    print("\n실행할 예시를 선택하세요:")
    print("1. 빠른 시작 (가장 간단)")
    print("2. 전체 제어")
    print("3. 개별 컴포넌트") 
    print("4. 움직임 감지만")
    print("5. 사용자 정의 콜백")
    print("0. 종료")
    
    try:
        choice = input("\n선택 (0-5): ").strip()
        
        if choice == '1':
            example1_quick_start()
        elif choice == '2':
            example2_full_control()
        elif choice == '3':
            example3_individual_parts()
        elif choice == '4':
            example4_motion_only()
        elif choice == '5':
            example5_custom_callback()
        elif choice == '0':
            print("종료합니다.")
        else:
            print("잘못된 선택입니다.")
            
    except KeyboardInterrupt:
        print("\n프로그램이 중단되었습니다.")


if __name__ == "__main__":
    main()