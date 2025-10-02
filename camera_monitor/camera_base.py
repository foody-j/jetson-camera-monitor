"""
카메라 기본 조작 모듈
카메라 초기화, 프레임 읽기, 설정 등 기본 기능 담당
"""

import cv2
import numpy as np
from typing import Optional, Tuple, Dict, Any


class CameraBase:
    """카메라 기본 조작 클래스"""
    
    def __init__(self, camera_index: int = 0, resolution: Tuple[int, int] = (640, 360)):
        """
        카메라 기본 설정 초기화
        
        Args:
            camera_index (int): 카메라 인덱스
            resolution (tuple): 해상도 (width, height)
        """
        self.camera_index = camera_index
        self.resolution = resolution
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_initialized = False
    
    def initialize(self) -> bool:
        """
        카메라 초기화
        
        Returns:
            bool: 초기화 성공 여부
        """
        try:
            self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap.isOpened():
                print(f"카메라 {self.camera_index}를 열 수 없습니다.")
                return False
            
            # 해상도 설정
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            
            self.is_initialized = True
            print(f"카메라 초기화 완료 - 해상도: {self.resolution}")
            return True
            
        except Exception as e:
            print(f"카메라 초기화 실패: {e}")
            return False
    
    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        프레임 읽기
        
        Returns:
            tuple: (성공 여부, 프레임 데이터)
        """
        if not self.is_initialized or not self.cap:
            return False, None
        
        ret, frame = self.cap.read()
        return ret, frame if ret else None
    
    def release(self) -> None:
        """카메라 리소스 해제"""
        if self.cap:
            self.cap.release()
            self.cap = None
        self.is_initialized = False
        print("카메라 리소스 해제됨")
    
    def get_info(self) -> Dict[str, Any]:
        """카메라 정보 반환"""
        if not self.is_initialized or not self.cap:
            return {}
        
        return {
            'width': int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'fps': int(self.cap.get(cv2.CAP_PROP_FPS)) or 30
        }
    
    @property
    def fps(self) -> int:
        """FPS 반환"""
        if not self.is_initialized or not self.cap:
            return 30
        return int(self.cap.get(cv2.CAP_PROP_FPS)) or 30
    
    def __enter__(self):
        """Context manager 진입"""
        if not self.initialize():
            raise RuntimeError("카메라 초기화 실패")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager 종료"""
        self.release()
    
    def __del__(self):
        """소멸자"""
        self.release()


def get_available_cameras(max_index: int = 5) -> list:
    """
    사용 가능한 카메라 목록 반환
    
    Args:
        max_index: 확인할 최대 인덱스
        
    Returns:
        list: 사용 가능한 카메라 인덱스 목록
    """
    available_cameras = []
    
    for i in range(max_index):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                available_cameras.append(i)
        cap.release()
    
    return available_cameras