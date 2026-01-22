"""
Robot frame detector for frying system.

Detects when the robot arm enters the camera frame.
- pot1 (camera_0): Robot enters from top-right
- pot2 (camera_1): Robot enters from top-left
"""

from enum import Enum
from typing import Dict, Optional, Tuple

import cv2
import numpy as np


class PotType(Enum):
    POT1 = "pot1"  # camera_0, robot from top-right
    POT2 = "pot2"  # camera_1, robot from top-left


class RobotDetector:
    """로봇 프레임 감지기."""

    # pot별 기본 threshold (pot2는 솥 테두리가 보여서 높게 설정)
    DEFAULT_THRESHOLDS = {
        PotType.POT1: 0.005,
        PotType.POT2: 0.05,
    }

    def __init__(
        self,
        pot_type: PotType = PotType.POT1,
        metal_threshold: float = None,  # None이면 pot별 기본값 사용
        # 금속 색상 범위 (HSV): 낮은 채도, 높은 명도
        metal_hsv_lower: Tuple[int, int, int] = (0, 0, 120),
        metal_hsv_upper: Tuple[int, int, int] = (180, 60, 255),
    ):
        self.pot_type = pot_type
        self.metal_threshold = metal_threshold or self.DEFAULT_THRESHOLDS[pot_type]
        self.metal_hsv_lower = np.array(metal_hsv_lower)
        self.metal_hsv_upper = np.array(metal_hsv_upper)

        # 상태 관리
        self.state = "idle"  # idle -> robot_detected -> idle
        self.last_detection = False

    def reset(self):
        """상태 초기화."""
        self.state = "idle"
        self.last_detection = False

    def _get_detection_region(
        self, image: np.ndarray
    ) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
        """pot 타입에 따른 감지 영역 추출."""
        h, w = image.shape[:2]

        if self.pot_type == PotType.POT1:
            # 우측 상단 1/4
            x1, y1 = w // 2, 0
            x2, y2 = w, h // 2
        else:  # POT2
            # 좌측 상단 1/4
            x1, y1 = 0, 0
            x2, y2 = w // 2, h // 2

        region = image[y1:y2, x1:x2]
        return region, (x1, y1, x2, y2)

    def detect(self, image: np.ndarray) -> Dict:
        """
        로봇 프레임 감지.

        Args:
            image: BGR 이미지

        Returns:
            {
                "robot_detected": bool,
                "metal_ratio": float,
                "state": str,
                "region": (x1, y1, x2, y2)
            }
        """
        region, bbox = self._get_detection_region(image)
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)

        # 금속 영역 감지
        metal_mask = cv2.inRange(hsv, self.metal_hsv_lower, self.metal_hsv_upper)

        # 모폴로지로 노이즈 제거
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        metal_mask = cv2.morphologyEx(metal_mask, cv2.MORPH_OPEN, kernel)

        metal_pixels = np.sum(metal_mask > 0)
        total_pixels = region.shape[0] * region.shape[1]
        metal_ratio = metal_pixels / total_pixels

        # 로봇 감지 여부
        robot_detected = metal_ratio > self.metal_threshold

        # 상태 전이
        prev_state = self.state
        if self.state == "idle" and robot_detected:
            self.state = "robot_detected"
        elif self.state == "robot_detected" and not robot_detected:
            self.state = "idle"

        self.last_detection = robot_detected

        return {
            "robot_detected": robot_detected,
            "metal_ratio": round(metal_ratio, 5),
            "state": self.state,
            "state_changed": prev_state != self.state,
            "region": bbox,
        }

    def detect_from_file(self, image_path: str) -> Dict:
        """파일에서 이미지 로드 후 감지."""
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Failed to load image: {image_path}")
        return self.detect(image)


def visualize_detection(
    image: np.ndarray,
    result: Dict,
    save_path: Optional[str] = None
) -> np.ndarray:
    """감지 결과 시각화."""
    vis = image.copy()

    # 감지 영역 표시
    x1, y1, x2, y2 = result["region"]
    color = (0, 255, 0) if result["robot_detected"] else (128, 128, 128)
    cv2.rectangle(vis, (x1, y1), (x2, y2), color, 3)

    # 텍스트 표시
    status = "ROBOT DETECTED" if result["robot_detected"] else "No robot"
    cv2.putText(vis, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
    cv2.putText(vis, f"Metal: {result['metal_ratio']:.4f}", (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    if save_path:
        cv2.imwrite(save_path, vis)

    return vis


if __name__ == "__main__":
    import sys
    from pathlib import Path

    if len(sys.argv) < 2:
        print("Usage: python robot_detector.py <image_path_or_directory> [pot1|pot2]")
        sys.exit(1)

    path = Path(sys.argv[1])
    pot_type = PotType.POT2 if len(sys.argv) > 2 and sys.argv[2] == "pot2" else PotType.POT1

    detector = RobotDetector(pot_type=pot_type)
    print(f"Pot type: {pot_type.value}")

    if path.is_file():
        result = detector.detect_from_file(str(path))
        print(f"Robot detected: {result['robot_detected']}")
        print(f"Metal ratio: {result['metal_ratio']:.5f}")
        print(f"State: {result['state']}")

    elif path.is_dir():
        image_paths = sorted(path.glob("*.jpg"))
        print(f"Found {len(image_paths)} images\n")

        detected_count = 0
        for img_path in image_paths:
            result = detector.detect_from_file(str(img_path))
            if result["robot_detected"]:
                detected_count += 1
                print(f"[ROBOT] {img_path.name} - metal: {result['metal_ratio']:.5f}")

        print(f"\nTotal: {detected_count}/{len(image_paths)} frames with robot")
