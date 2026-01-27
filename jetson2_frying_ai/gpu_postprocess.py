#!/usr/bin/env python3
"""
Torch 기반 GPU 후처리 유틸리티
- cv2.cuda 대신 PyTorch GPU 사용
- YOLO와 동일한 GPU 컨텍스트 공유
"""

import cv2
import numpy as np
import torch
import torch.nn.functional as F


class GPUPostProcessor:
    """PyTorch 기반 GPU 후처리"""

    def __init__(self, device=None):
        """
        Args:
            device: torch device 또는 문자열 ('cuda', 'cpu')
        """
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        elif isinstance(device, str):
            self.device = torch.device(device)
        else:
            self.device = device

        self.gpu_available = self.device.type == "cuda"
        print(f"[GPUPostProcessor] device={self.device}, gpu_available={self.gpu_available}")

    def resize(self, img: np.ndarray, size: tuple, mode: str = "nearest") -> np.ndarray:
        """
        GPU 리사이즈

        Args:
            img: 입력 이미지 (H, W, C) 또는 (H, W)
            size: (width, height) - OpenCV 스타일
            mode: 'nearest', 'bilinear', 'bicubic'

        Returns:
            리사이즈된 이미지 (numpy)
        """
        if not self.gpu_available:
            interp = cv2.INTER_NEAREST if mode == "nearest" else cv2.INTER_LINEAR
            return cv2.resize(img, size, interpolation=interp)

        try:
            # OpenCV size는 (W, H), torch는 (H, W)
            target_h, target_w = size[1], size[0]

            # numpy -> torch
            is_gray = len(img.shape) == 2
            if is_gray:
                tensor = torch.from_numpy(img).unsqueeze(0).unsqueeze(0).float()
            else:
                # (H, W, C) -> (1, C, H, W)
                tensor = torch.from_numpy(img).permute(2, 0, 1).unsqueeze(0).float()

            tensor = tensor.to(self.device)

            # 리사이즈
            resized = F.interpolate(tensor, size=(target_h, target_w), mode=mode)

            # torch -> numpy
            if is_gray:
                return resized.squeeze().cpu().numpy().astype(img.dtype)
            else:
                return resized.squeeze().permute(1, 2, 0).cpu().numpy().astype(img.dtype)

        except Exception as e:
            print(f"[GPUPostProcessor] resize 실패, CPU 폴백: {e}")
            interp = cv2.INTER_NEAREST if mode == "nearest" else cv2.INTER_LINEAR
            return cv2.resize(img, size, interpolation=interp)

    def overlay_mask(self, frame: np.ndarray, mask: np.ndarray,
                     color: tuple = (0, 255, 0), alpha: float = 0.3) -> np.ndarray:
        """
        GPU 마스크 오버레이

        Args:
            frame: BGR 이미지 (H, W, 3)
            mask: 그레이스케일 마스크 (H, W), 255=마스크 영역
            color: BGR 색상
            alpha: 오버레이 투명도

        Returns:
            오버레이된 이미지
        """
        if mask is None:
            return frame

        if not self.gpu_available:
            return self._overlay_mask_cpu(frame, mask, color, alpha)

        try:
            # numpy -> torch (0~1 범위)
            frame_t = torch.from_numpy(frame).float().to(self.device) / 255.0
            mask_t = torch.from_numpy(mask).float().to(self.device) / 255.0

            # 마스크 확장 (H, W) -> (H, W, 3)
            mask_3ch = mask_t.unsqueeze(-1).expand_as(frame_t)

            # 색상 텐서 (BGR, 0~1)
            color_t = torch.tensor([color[0], color[1], color[2]],
                                   dtype=torch.float32, device=self.device) / 255.0
            color_overlay = color_t.view(1, 1, 3).expand_as(frame_t)

            # 블렌딩: frame * (1 - alpha * mask) + color * alpha * mask
            result = frame_t * (1 - alpha * mask_3ch) + color_overlay * alpha * mask_3ch

            # torch -> numpy (0~255)
            return (result.cpu().numpy() * 255).astype(np.uint8)

        except Exception as e:
            print(f"[GPUPostProcessor] overlay_mask 실패, CPU 폴백: {e}")
            return self._overlay_mask_cpu(frame, mask, color, alpha)

    def _overlay_mask_cpu(self, frame: np.ndarray, mask: np.ndarray,
                          color: tuple, alpha: float) -> np.ndarray:
        """CPU 폴백 오버레이"""
        color_overlay = np.zeros_like(frame)
        color_overlay[:, :] = color
        mask_3ch = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        masked_color = cv2.bitwise_and(color_overlay, mask_3ch)
        return cv2.addWeighted(frame, 1.0 - alpha, masked_color, alpha, 0)

    def resize_mask_from_tensor(self, mask_tensor: torch.Tensor,
                                 target_size: tuple, threshold: float = 0.5) -> np.ndarray:
        """
        YOLO 마스크 텐서를 직접 GPU에서 리사이즈
        - .cpu() 호출 전에 리사이즈하여 GPU→CPU 전송량 최소화

        Args:
            mask_tensor: YOLO r.masks.data[i] (GPU tensor, H, W)
            target_size: (W, H) OpenCV 스타일
            threshold: 이진화 임계값

        Returns:
            리사이즈된 마스크 (numpy, uint8, 0 또는 255)
        """
        try:
            target_h, target_w = target_size[1], target_size[0]

            # (H, W) -> (1, 1, H, W) for interpolate
            if mask_tensor.dim() == 2:
                mask_4d = mask_tensor.unsqueeze(0).unsqueeze(0)
            elif mask_tensor.dim() == 3:
                mask_4d = mask_tensor.unsqueeze(0)
            else:
                mask_4d = mask_tensor

            # GPU에서 리사이즈
            resized = F.interpolate(mask_4d.float(), size=(target_h, target_w), mode='nearest')

            # GPU에서 이진화 후 CPU로 전송
            binary = (resized.squeeze() > threshold).to(torch.uint8) * 255
            return binary.cpu().numpy()

        except Exception as e:
            print(f"[GPUPostProcessor] resize_mask_from_tensor 실패: {e}")
            # 폴백: CPU에서 처리
            m = (mask_tensor.cpu().numpy() > threshold).astype(np.uint8) * 255
            return cv2.resize(m, target_size, interpolation=cv2.INTER_NEAREST)


# 싱글톤 인스턴스 (전역 사용)
_gpu_processor = None

def get_gpu_processor(device=None) -> GPUPostProcessor:
    """싱글톤 GPUPostProcessor 반환"""
    global _gpu_processor
    if _gpu_processor is None:
        _gpu_processor = GPUPostProcessor(device)
    return _gpu_processor
