"""
움직임 감지 모듈
배경 차분을 이용한 움직임 감지 기능 담당
"""

import cv2
import numpy as np
from typing import Optional, Callable, Tuple


class MotionDetector:
    """움직임 감지 클래스"""
    
    def __init__(self, threshold: int = 1000, min_area: int = 500):
        """
        움직임 감지기 초기화
        
        Args:
            threshold: 움직임 감지 임계값 (픽셀 수)
            min_area: 최소 감지 영역 크기
        """
        self.threshold = threshold
        self.min_area = min_area
        self.enabled = False
        
        # 배경 차분 객체
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2(
            detectShadows=True, varThreshold=50
        )
        
        # 모폴로지 연산용 커널
        self.kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        
        # 콜백 함수
        self.motion_callback: Optional[Callable[[np.ndarray], None]] = None
    
    def enable(self) -> None:
        """움직임 감지 활성화"""
        self.enabled = True
        print("움직임 감지 활성화됨")
    
    def disable(self) -> None:
        """움직임 감지 비활성화"""
        self.enabled = False
        print("움직임 감지 비활성화됨")
    
    def toggle(self) -> bool:
        """움직임 감지 토글"""
        self.enabled = not self.enabled
        status = "활성화" if self.enabled else "비활성화"
        print(f"움직임 감지 {status}")
        return self.enabled
    
    def set_callback(self, callback: Callable[[np.ndarray], None]) -> None:
        """
        움직임 감지 시 호출될 콜백 함수 설정
        
        Args:
            callback: 콜백 함수 (프레임을 인자로 받음)
        """
        self.motion_callback = callback
    
    def detect(self, frame: np.ndarray) -> Tuple[bool, Optional[np.ndarray]]:
        """
        프레임에서 움직임 감지
        
        Args:
            frame: 입력 프레임
            
        Returns:
            tuple: (움직임 감지 여부, 움직임 마스크)
        """
        if not self.enabled:
            return False, None
        
        # 배경 차분 적용
        fg_mask = self.background_subtractor.apply(frame)
        
        # 노이즈 제거
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, self.kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, self.kernel)
        
        # 움직임 픽셀 수 계산
        motion_pixels = cv2.countNonZero(fg_mask)
        
        # 기본 임계값 검사
        if motion_pixels < self.threshold:
            return False, fg_mask
        
        # 윤곽선 기반 정확한 검증
        contours, _ = cv2.findContours(
            fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        # 최소 영역 이상의 윤곽선이 있는지 확인
        valid_motion = any(cv2.contourArea(contour) > self.min_area 
                          for contour in contours)
        
        # 움직임 감지 시 콜백 호출
        if valid_motion and self.motion_callback:
            self.motion_callback(frame)
        
        return valid_motion, fg_mask
    
    def draw_motion_overlay(self, frame: np.ndarray, motion_detected: bool, 
                           mask: Optional[np.ndarray] = None) -> np.ndarray:
        """
        움직임 감지 오버레이 그리기
        
        Args:
            frame: 원본 프레임
            motion_detected: 움직임 감지 여부
            mask: 움직임 마스크 (선택사항)
            
        Returns:
            오버레이가 그려진 프레임
        """
        result = frame.copy()
        
        if not self.enabled:
            return result
        
        if motion_detected:
            # 빨간 테두리 표시
            cv2.rectangle(result, (0, 0), 
                         (frame.shape[1]-1, frame.shape[0]-1), 
                         (0, 0, 255), 3)
            
            # "MOTION DETECTED" 텍스트 표시
            cv2.putText(result, "MOTION DETECTED", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, 
                       (0, 0, 255), 2)
            
            # 윤곽선 그리기 (마스크가 있는 경우)
            if mask is not None:
                contours, _ = cv2.findContours(
                    mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )
                # 최소 영역 이상의 윤곽선만 그리기
                valid_contours = [c for c in contours 
                                if cv2.contourArea(c) > self.min_area]
                cv2.drawContours(result, valid_contours, -1, (0, 255, 0), 2)
        
        return result
    
    def set_threshold(self, threshold: int) -> None:
        """감지 임계값 설정"""
        self.threshold = threshold
        print(f"움직임 감지 임계값 설정: {threshold}")
    
    def set_min_area(self, min_area: int) -> None:
        """최소 감지 영역 설정"""
        self.min_area = min_area
        print(f"최소 감지 영역 설정: {min_area}")
    
    def reset_background(self) -> None:
        """배경 모델 재설정"""
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2(
            detectShadows=True, varThreshold=50
        )
        print("배경 모델 재설정됨")
    
    def get_info(self) -> dict:
        """감지기 정보 반환"""
        return {
            'enabled': self.enabled,
            'threshold': self.threshold,
            'min_area': self.min_area,
            'has_callback': self.motion_callback is not None
        }