"""
녹화 및 스크린샷 모듈
비디오 녹화, 이미지 저장, 파일 관리 등의 기능 담당
"""

import cv2
import os
import datetime
import numpy as np
from typing import Optional
from camera_monitor.camera_base import CameraBase

def get_timestamp(format_str: str = "%Y%m%d_%H%M%S") -> str:
    """현재 시간 문자열 반환"""
    return datetime.datetime.now().strftime(format_str)


def create_directories(*dirs) -> None:
    """디렉토리들 생성"""
    for directory in dirs:
        os.makedirs(directory, exist_ok=True)


class MediaRecorder:
    """비디오 녹화 및 스크린샷 관리 클래스"""
    
    def __init__(self, camera: CameraBase, 
                 recording_dir: str = "recordings",
                 screenshot_dir: str = "screenshots"):
        """
        미디어 레코더 초기화
        
        Args:
            camera: 카메라 객체
            recording_dir: 녹화 파일 저장 디렉토리
            screenshot_dir: 스크린샷 저장 디렉토리
        """
        self.camera = camera
        self.recording_dir = recording_dir
        self.screenshot_dir = screenshot_dir
        
        # 녹화 관련
        self.video_writer: Optional[cv2.VideoWriter] = None
        self.is_recording = False
        self.current_filename = ""
        
        # 디렉토리 생성
        create_directories(self.recording_dir, self.screenshot_dir)
    
    def start_recording(self, filename: Optional[str] = None, 
                       codec: str = 'MJPG', fps:Optional[int] = None) -> bool:
        """
        녹화 시작
        
        Args:
            filename: 파일명 (없으면 자동 생성)
            codec: 비디오 코덱
            
        Returns:
            bool: 녹화 시작 성공 여부
        """
        if self.is_recording:
            print("이미 녹화 중입니다.")
            return False
        
        if not self.camera.is_initialized:
            print("카메라가 초기화되지 않았습니다.")
            return False
        
        # 파일명 생성
        if not filename:
            timestamp = get_timestamp()
            filename = f"recording_{timestamp}.avi"
        
        self.current_filename = os.path.join(self.recording_dir, filename)
        
        # 비디오 설정
        fourcc = cv2.VideoWriter_fourcc(*codec)
        fps = fps or 30  # ← camera.fps 대신 30 고정
        
        # 실제 카메라 해상도 가져오기
        if self.camera.is_initialized:
            info = self.camera.get_info()
            resolution = (info['width'], info['height'])  # ← 실제 해상도 사용
        else:
            resolution = self.camera.resolution
        # VideoWriter 생성
        fourcc = cv2.VideoWriter_fourcc(*codec)
        fps = self.camera.fps
        resolution = self.camera.resolution
        
        self.video_writer = cv2.VideoWriter(
            self.current_filename, fourcc, fps, resolution
        )
        
        if self.video_writer.isOpened():
            self.is_recording = True
            print(f"녹화 시작: {self.current_filename}")
            return True
        else:
            print("녹화 시작 실패")
            return False
    
    def write_frame(self, frame: np.ndarray) -> bool:
        """프레임을 비디오 파일에 기록"""
        if not self.is_recording or not self.video_writer:
            return False
        
        try:
            self.video_writer.write(frame)
            return True
        except Exception as e:
            print(f"프레임 기록 실패: {e}")
            return False
    
    def stop_recording(self) -> Optional[str]:
        """
        녹화 중지
        
        Returns:
            str: 녹화된 파일 경로 (실패시 None)
        """
        if not self.is_recording:
            return None
        
        filename = self.current_filename
        
        if self.video_writer:
            self.video_writer.release()
            self.video_writer = None
        
        self.is_recording = False
        self.current_filename = ""
        
        print(f"녹화 중지: {filename}")
        return filename
    
    def take_screenshot(self, frame: Optional[np.ndarray] = None, 
                      filename: Optional[str] = None) -> str:
        """
        스크린샷 촬영
        
        Args:
            frame: 저장할 프레임 (없으면 카메라에서 캡처)
            filename: 파일명 (없으면 자동 생성)
            
        Returns:
            str: 저장된 파일 경로
        """
        # 프레임 가져오기
        if frame is None:
            if not self.camera.is_initialized:
                print("카메라가 초기화되지 않았습니다.")
                return ""
            ret, frame = self.camera.read_frame()
            if not ret or frame is None:
                print("프레임을 읽을 수 없습니다.")
                return ""
        
        # 파일명 생성
        if not filename:
            timestamp = get_timestamp()
            filename = f"screenshot_{timestamp}.jpg"
        elif not filename.endswith('.jpg'):
            filename = f"{filename}.jpg"
        
        filepath = os.path.join(self.screenshot_dir, filename)
        
        try:
            success = cv2.imwrite(filepath, frame)
            if success:
                print(f"스크린샷 저장: {filepath}")
                return filepath
            else:
                print(f"스크린샷 저장 실패: {filepath}")
                return ""
        except Exception as e:
            print(f"스크린샷 저장 중 오류: {e}")
            return ""
    
    def get_recording_info(self) -> dict:
        """현재 녹화 정보 반환"""
        return {
            'is_recording': self.is_recording,
            'filename': self.current_filename if self.is_recording else None,
            'recording_dir': self.recording_dir,
            'screenshot_dir': self.screenshot_dir
        }
    
    def get_saved_files(self) -> dict:
        """저장된 파일 목록 반환"""
        recordings = []
        screenshots = []
        
        try:
            # 녹화 파일들
            if os.path.exists(self.recording_dir):
                for filename in os.listdir(self.recording_dir):
                    if filename.lower().endswith(('.avi', '.mp4', '.mov')):
                        recordings.append(os.path.join(self.recording_dir, filename))
            
            # 스크린샷들
            if os.path.exists(self.screenshot_dir):
                for filename in os.listdir(self.screenshot_dir):
                    if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                        screenshots.append(os.path.join(self.screenshot_dir, filename))
        except Exception:
            pass
        
        return {
            'recordings': sorted(recordings),
            'screenshots': sorted(screenshots)
        }
    
    def clean_old_files(self, days: int = 30) -> dict:
        """
        오래된 파일들 정리
        
        Args:
            days: 보관 기간 (일)
            
        Returns:
            dict: 삭제된 파일 수 정보
        """
        import time
        current_time = time.time()
        cutoff_time = current_time - (days * 24 * 60 * 60)
        
        deleted_recordings = 0
        deleted_screenshots = 0
        
        try:
            # 녹화 파일 정리
            if os.path.exists(self.recording_dir):
                for filename in os.listdir(self.recording_dir):
                    filepath = os.path.join(self.recording_dir, filename)
                    if (os.path.isfile(filepath) and 
                        os.path.getctime(filepath) < cutoff_time and
                        filename.lower().endswith(('.avi', '.mp4', '.mov'))):
                        os.remove(filepath)
                        deleted_recordings += 1
            
            # 스크린샷 정리
            if os.path.exists(self.screenshot_dir):
                for filename in os.listdir(self.screenshot_dir):
                    filepath = os.path.join(self.screenshot_dir, filename)
                    if (os.path.isfile(filepath) and 
                        os.path.getctime(filepath) < cutoff_time and
                        filename.lower().endswith(('.jpg', '.jpeg', '.png'))):
                        os.remove(filepath)
                        deleted_screenshots += 1
        
        except Exception as e:
            print(f"파일 정리 중 오류: {e}")
        
        total_deleted = deleted_recordings + deleted_screenshots
        if total_deleted > 0:
            print(f"오래된 파일 {total_deleted}개 삭제됨 "
                  f"(녹화: {deleted_recordings}, 스크린샷: {deleted_screenshots})")
        
        return {
            'recordings_deleted': deleted_recordings,
            'screenshots_deleted': deleted_screenshots,
            'total_deleted': total_deleted
        }
    
    def __del__(self):
        """소멸자 - 녹화 중이면 정리"""
        if self.is_recording:
            self.stop_recording()