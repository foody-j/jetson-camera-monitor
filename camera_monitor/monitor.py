"""
메인 모니터링 모듈
카메라, 녹화, 움직임 감지 모듈들을 조합한 완전한 모니터링 시스템
"""

import cv2
import time
import datetime
import numpy as np
from typing import Optional, Callable

from camera_monitor.camera_base import CameraBase
from camera_monitor.recorder import MediaRecorder
from camera_monitor.motion_detector import MotionDetector


def draw_text_with_background(img: np.ndarray, text: str, pos: tuple,
                             font_scale: float = 0.6, thickness: int = 1,
                             text_color: tuple = (255, 255, 255),
                             bg_color: tuple = (0, 0, 0)) -> None:
    """배경이 있는 텍스트 그리기"""
    font = cv2.FONT_HERSHEY_SIMPLEX
    
    # 텍스트 크기 계산
    (text_width, text_height), baseline = cv2.getTextSize(
        text, font, font_scale, thickness
    )
    
    # 배경 사각형 그리기
    x, y = pos
    cv2.rectangle(img, (x, y - text_height - baseline),
                  (x + text_width, y + baseline), bg_color, -1)
    
    # 텍스트 그리기
    cv2.putText(img, text, pos, font, font_scale, text_color, thickness)


class CameraMonitor:
    """메인 카메라 모니터링 클래스"""
    
    def __init__(self, camera_index: int = 0, resolution: tuple = (640, 480)):
        """
        모니터링 시스템 초기화
        
        Args:
            camera_index: 카메라 인덱스
            resolution: 해상도
        """
        # 컴포넌트 초기화
        self.camera = CameraBase(camera_index, resolution)
        self.recorder = MediaRecorder(self.camera)
        self.motion_detector = MotionDetector()
        
        # 상태 변수
        self.is_monitoring = False
        self.show_window = True
        self.frame_count = 0
        self.start_time = 0.0
        self.fps = 0.0
        self.show_fps = True
        self.show_timestamp = True
        self.auto_screenshot_on_motion = True
        
        # 콜백 함수
        self.custom_frame_callback: Optional[Callable] = None
        
        # 움직임 감지 콜백 설정
        self.motion_detector.set_callback(self._on_motion_detected)
    
    def initialize(self) -> bool:
        """시스템 초기화"""
        success = self.camera.initialize()
        if success:
            print(f"카메라 모니터링 시스템 초기화 완료")
            print(f"카메라 정보: {self.camera.get_info()}")
        return success
    
    def start_monitoring(self, show_window: bool = True) -> None:
        """
        모니터링 시작
        
        Args:
            show_window: 모니터링 창 표시 여부
        """
        if not self.camera.is_initialized:
            if not self.initialize():
                return
        
        self.is_monitoring = True
        self.show_window = show_window
        self.frame_count = 0
        self.start_time = time.time()
        
        print("=== 카메라 모니터링 시작 ===")
        self._print_controls()
        
        try:
            self._monitoring_loop()
        except KeyboardInterrupt:
            print("\n사용자에 의해 중단됨")
        finally:
            self.stop_monitoring()
    
    def _monitoring_loop(self) -> None:
        """메인 모니터링 루프"""
        fps_counter = 0
        last_fps_time = time.time()
        
        while self.is_monitoring:
            ret, frame = self.camera.read_frame()
            if not ret or frame is None:
                print("프레임을 읽을 수 없습니다.")
                break
            
            # 프레임 처리
            processed_frame = self._process_frame(frame)
            
            # 녹화 중이면 프레임 기록
            if self.recorder.is_recording:
                self.recorder.write_frame(processed_frame)
            
            # 사용자 정의 콜백 호출
            if self.custom_frame_callback:
                self.custom_frame_callback(processed_frame)
            
            # 화면 표시
            if self.show_window:
                cv2.imshow('Camera Monitor', processed_frame)
                
                # 키 입력 처리
                key = cv2.waitKey(1) & 0xFF
                if not self._handle_key_input(key, frame):
                    break
            
            # FPS 계산 (30프레임마다)
            fps_counter += 1
            if fps_counter >= 30:
                current_time = time.time()
                elapsed = current_time - last_fps_time
                if elapsed > 0:
                    self.fps = fps_counter / elapsed
                fps_counter = 0
                last_fps_time = current_time
    
    def _process_frame(self, frame: np.ndarray) -> np.ndarray:
        """프레임 처리 (움직임 감지, 오버레이 등)"""
        processed_frame = frame.copy()
        
        # 움직임 감지
        motion_detected, motion_mask = self.motion_detector.detect(frame)
        
        # 움직임 오버레이 그리기
        if self.motion_detector.enabled:
            processed_frame = self.motion_detector.draw_motion_overlay(
                processed_frame, motion_detected, motion_mask
            )
        
        # 상태 정보 오버레이
        self._draw_status_overlay(processed_frame)
        
        return processed_frame
    
    def _draw_status_overlay(self, frame: np.ndarray) -> None:
        """상태 정보 오버레이 그리기"""
        y_pos = 20
        line_height = 25
        
        # 타임스탬프
        if self.show_timestamp:
            timestamp = get_timestamp("%Y-%m-%d %H:%M:%S")
            draw_text_with_background(frame, timestamp, (10, y_pos))
            y_pos += line_height
        
        # FPS
        if self.show_fps:
            fps_text = f"FPS: {self.fps:.1f}"
            draw_text_with_background(frame, fps_text, (10, y_pos))
        
        # 녹화 상태 (깜빡이는 REC)
        if self.recorder.is_recording:
            if int(time.time() * 2) % 2:  # 0.5초마다 깜빡임
                cv2.circle(frame, (frame.shape[1] - 30, 30), 10, (0, 0, 255), -1)
                draw_text_with_background(
                    frame, "REC", (frame.shape[1] - 80, 35), 
                    text_color=(0, 0, 255)
                )
        
        # 움직임 감지 상태
        if self.motion_detector.enabled:
            status_text = "Motion Detection: ON"
            draw_text_with_background(
                frame, status_text, (10, frame.shape[0] - 30), 
                text_color=(0, 255, 0)
            )
    
    def _handle_key_input(self, key: int, current_frame: np.ndarray) -> bool:
        """
        키보드 입력 처리
        
        Returns:
            bool: 계속 실행할지 여부 (False면 종료)
        """
        if key == ord('q'):  # 종료
            return False
        
        elif key == ord('s'):  # 스크린샷
            self.take_screenshot(current_frame)
        
        elif key == ord('r'):  # 녹화 시작/중지
            self.toggle_recording()
        
        elif key == ord('m'):  # 움직임 감지 토글
            self.motion_detector.toggle()
        
        elif key == ord('i'):  # 정보 표시
            self.print_status()
        
        elif key == ord('h'):  # 도움말
            self._print_controls()
        
        elif key == ord('f'):  # FPS 표시 토글
            self.show_fps = not self.show_fps
            print(f"FPS 표시: {'ON' if self.show_fps else 'OFF'}")
        
        elif key == ord('t'):  # 타임스탬프 표시 토글
            self.show_timestamp = not self.show_timestamp
            print(f"타임스탬프 표시: {'ON' if self.show_timestamp else 'OFF'}")
        
        return True
    
    def _on_motion_detected(self, frame: np.ndarray) -> None:
        """움직임 감지 시 호출되는 콜백"""
        print(f"움직임 감지됨! {get_timestamp('%H:%M:%S')}")
        
        # 자동 스크린샷
        if self.auto_screenshot_on_motion:
            filename = f"motion_{get_timestamp()}.jpg"
            self.recorder.take_screenshot(frame, filename)
    
    def take_screenshot(self, frame: Optional[np.ndarray] = None) -> str:
        """스크린샷 촬영"""
        return self.recorder.take_screenshot(frame)
    
    def toggle_recording(self) -> bool:
        """녹화 토글"""
        if self.recorder.is_recording:
            self.recorder.stop_recording()
            return False
        else:
            success = self.recorder.start_recording()
            return success
    
    def set_frame_callback(self, callback: Callable[[np.ndarray], None]) -> None:
        """프레임 처리 콜백 설정"""
        self.custom_frame_callback = callback
    
    def stop_monitoring(self) -> None:
        """모니터링 중지"""
        self.is_monitoring = False
        
        # 녹화 중이면 중지
        if self.recorder.is_recording:
            self.recorder.stop_recording()
        
        # 리소스 해제
        self.camera.release()
        cv2.destroyAllWindows()
        
        print("카메라 모니터링 종료")
    
    def print_status(self) -> None:
        """현재 상태 출력"""
        print("\n=== 현재 상태 ===")
        print(f"카메라: {self.camera.get_info()}")
        print(f"녹화: {self.recorder.get_recording_info()}")
        print(f"움직임 감지: {self.motion_detector.get_info()}")
        print(f"현재 FPS: {self.fps:.1f}")
        
        files = self.recorder.get_saved_files()
        print(f"저장된 파일: 녹화 {len(files['recordings'])}개, "
              f"스크린샷 {len(files['screenshots'])}개")
        print("================\n")
    
    def _print_controls(self) -> None:
        """조작법 출력"""
        print("\n=== 조작법 ===")
        print("q: 종료")
        print("s: 스크린샷 촬영")
        print("r: 녹화 시작/중지") 
        print("m: 움직임 감지 토글")
        print("i: 상태 정보 표시")
        print("f: FPS 표시 토글")
        print("t: 타임스탬프 표시 토글")
        print("h: 도움말")
        print("===============\n")
    
    def __enter__(self):
        """Context manager 진입"""
        if not self.initialize():
            raise RuntimeError("시스템 초기화 실패")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager 종료"""
        self.stop_monitoring()


def quick_start(camera_index: int = 0, resolution: tuple = (640, 480)) -> None:
    """
    빠른 시작 함수
    
    Args:
        camera_index: 카메라 인덱스
        resolution: 해상도
    """
    monitor = CameraMonitor(camera_index, resolution)
    
    try:
        monitor.start_monitoring()
    except Exception as e:
        print(f"모니터링 실행 중 오류: {e}")
    finally:
        monitor.stop_monitoring()


# 간편한 실행을 위한 메인 함수
if __name__ == "__main__":
    print("Camera Monitor - 간편 실행")
    quick_start()