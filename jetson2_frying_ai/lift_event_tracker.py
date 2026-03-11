#!/usr/bin/env python3
"""
탈탈 이벤트 추적 및 완료 판단
- YOLO segmentation 결과로 들어올림 자동 감지
- 색상 변화 추적
- target_time + color_delta 기반 완료 판단
"""

import os
import json
import time
from datetime import datetime
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict
import numpy as np
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CPP_FRY_PY_DIR = os.path.join(SCRIPT_DIR, "cpp_frying_core", "python")
if os.path.isdir(CPP_FRY_PY_DIR) and CPP_FRY_PY_DIR not in sys.path:
    sys.path.insert(0, CPP_FRY_PY_DIR)
try:
    from lift_tracker_core import LiftTrackerCoreCpp
except Exception:
    LiftTrackerCoreCpp = None


@dataclass
class LiftEvent:
    """탈탈 이벤트"""
    timestamp: str
    running_time: float  # 초 단위
    color_delta: float   # 기준 대비 색상 변화
    food_area_ratio: float
    hsv_mean: tuple
    brown_ratio: float
    golden_ratio: float
    saturation_mean: float
    value_mean: float


class LiftEventTracker:
    """탈탈 이벤트 추적 및 완료 판단"""

    def __init__(self, pot_name: str, config: dict):
        """
        Args:
            pot_name: "POT1" or "POT2"
            config: 설정 딕셔너리
        """
        self.pot_name = pot_name
        self.config = config

        # 감지 임계값
        self.lift_area_threshold = config.get('lift_area_threshold', 0.1)  # 10% 이상 보이면 들어올림
        self.lift_cooldown_sec = config.get('lift_cooldown_sec', 3.0)  # 탈탈 간 최소 간격

        # 완료 판단 임계값
        self.color_change_threshold = config.get('color_change_threshold', 25.0)  # HSV 변화량
        self.completion_early_sec = float(config.get("lift_completion_early_sec", 60.0))

        self.lift_cpp_core_enabled = bool(config.get("lift_cpp_core_enabled", False))
        self.lift_cpp_core = None
        if self.lift_cpp_core_enabled:
            if LiftTrackerCoreCpp is None:
                print(f"[{self.pot_name} LiftTracker] C++ core unavailable, fallback to Python")
            else:
                try:
                    lib_path = config.get("lift_cpp_core_lib", "cpp_frying_core/build/liblift_tracker_core.so")
                    if not os.path.isabs(lib_path):
                        lib_path = os.path.join(SCRIPT_DIR, lib_path)
                    self.lift_cpp_core = LiftTrackerCoreCpp(lib_path=lib_path)
                    print(f"[{self.pot_name} LiftTracker] C++ core enabled: {lib_path}")
                except Exception as e:
                    print(f"[{self.pot_name} LiftTracker] C++ core init failed: {e}")
                    self.lift_cpp_core = None

        # 세션 상태
        self.active = False
        self.session_id = None
        self.food_type = None
        self.start_time = None
        self.target_time = None  # 초 단위

        # 탈탈 이벤트 기록
        self.lift_events: List[LiftEvent] = []
        self.baseline_color = None  # 첫 탈탈 기준 색상
        self.last_lift_time = 0

        # 완료 상태
        self.completion_detected = False
        self.completion_time = None

        print(
            f"[{self.pot_name} LiftTracker] config "
            f"(lift_area_threshold={self.lift_area_threshold}, "
            f"lift_cooldown_sec={self.lift_cooldown_sec}, "
            f"color_change_threshold={self.color_change_threshold})"
        )

    def start_session(self, session_id: str, food_type: str, target_time: int):
        """세션 시작"""
        self.active = True
        self.session_id = session_id
        self.food_type = food_type
        self.start_time = time.time()
        self.target_time = target_time

        # 초기화
        self.lift_events = []
        self.baseline_color = None
        self.last_lift_time = 0
        self.completion_detected = False
        self.completion_time = None

        print(f"[{self.pot_name} LiftTracker] 세션 시작: {food_type}, target={target_time}초")

    def stop_session(self):
        """세션 종료"""
        if not self.active:
            return

        self.active = False
        print(f"[{self.pot_name} LiftTracker] 세션 종료: {len(self.lift_events)}회 탈탈")

    def process_frame(self, seg_result) -> Dict:
        """
        프레임 처리 및 탈탈 이벤트 감지

        Args:
            seg_result: FoodSegmenter의 SegmentationResult

        Returns:
            {
                'lift_detected': bool,
                'completion_detected': bool,
                'running_time': float,
                'color_delta': float,
                'lift_count': int
            }
        """
        if not self.active or seg_result is None:
            return {
                'lift_detected': False,
                'completion_detected': False,
                'running_time': 0,
                'color_delta': 0,
                'lift_count': 0
            }

        now = time.time()
        running_time = now - self.start_time

        # 탈탈 감지 (food_area_ratio > threshold)
        lift_detected = False
        color_delta = 0
        block_reason = "area_below_threshold"
        cooldown_remaining = max(0.0, self.lift_cooldown_sec - max(0.0, now - self.last_lift_time))

        if seg_result.food_area_ratio > self.lift_area_threshold:
            # 쿨다운 체크 (연속된 프레임 필터링)
            if now - self.last_lift_time > self.lift_cooldown_sec:
                lift_detected = True
                self.last_lift_time = now
                cooldown_remaining = 0.0
                block_reason = ""

                # 색상 변화 계산
                color_delta = self._calculate_color_change(seg_result.color_features)

                # 탈탈 이벤트 기록
                self._record_lift_event(running_time, color_delta, seg_result)

                # 완료 판단
                if not self.completion_detected:
                    self._check_completion(running_time, color_delta)
            else:
                block_reason = "cooldown_active"

        return {
            'lift_detected': lift_detected,
            'completion_detected': self.completion_detected,
            'running_time': running_time,
            'color_delta': color_delta,
            'lift_count': len(self.lift_events),
            'lift_area_threshold': float(self.lift_area_threshold),
            'cooldown_remaining': float(cooldown_remaining),
            'block_reason': block_reason,
        }

    def _calculate_color_change(self, color_features) -> float:
        """색상 변화 계산 (HSV 거리)"""
        # 첫 탈탈 → 기준 색상 저장
        if self.baseline_color is None:
            self.baseline_color = {
                'hsv_mean': color_features.mean_hsv,
                'brown_ratio': color_features.brown_ratio,
                'golden_ratio': color_features.golden_ratio
            }
            return 0.0

        h1, s1, v1 = self.baseline_color['hsv_mean']
        h2, s2, v2 = color_features.mean_hsv
        if self.lift_cpp_core is not None:
            try:
                return self.lift_cpp_core.calc_color_delta(h1, s1, v1, h2, s2, v2)
            except Exception as e:
                print(f"[{self.pot_name} LiftTracker] C++ delta error, fallback: {e}")

        # HSV 유클리드 거리 계산
        h_diff = min(abs(h1 - h2), 360 - abs(h1 - h2))
        delta = np.sqrt((h_diff * 2.0)**2 + (s1 - s2)**2 + (v1 - v2)**2)

        return float(delta)

    def _record_lift_event(self, running_time: float, color_delta: float, seg_result):
        """탈탈 이벤트 기록"""
        event = LiftEvent(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            running_time=running_time,
            color_delta=color_delta,
            food_area_ratio=seg_result.food_area_ratio,
            hsv_mean=seg_result.color_features.mean_hsv,
            brown_ratio=seg_result.color_features.brown_ratio,
            golden_ratio=seg_result.color_features.golden_ratio,
            saturation_mean=seg_result.color_features.saturation_mean,
            value_mean=seg_result.color_features.value_mean
        )

        self.lift_events.append(event)

        print(f"[{self.pot_name} LiftTracker] 탈탈 #{len(self.lift_events)} | "
              f"시간={running_time:.0f}초, 색변화={color_delta:.1f}, "
              f"brown={event.brown_ratio:.2f}, golden={event.golden_ratio:.2f}")

    def _check_completion(self, running_time: float, color_delta: float):
        """완료 판단"""
        ready_time = max(0.0, float(self.target_time or 0) - self.completion_early_sec)
        is_ready = False
        used_cpp = False
        if self.lift_cpp_core is not None:
            try:
                used_cpp = True
                is_ready = self.lift_cpp_core.check_completion_ready(
                    running_time=running_time,
                    target_time=float(self.target_time or 0),
                    early_sec=self.completion_early_sec,
                    color_delta=color_delta,
                    color_threshold=float(self.color_change_threshold),
                )
            except Exception as e:
                print(f"[{self.pot_name} LiftTracker] C++ completion check error, fallback: {e}")
                used_cpp = False

        if not used_cpp:
            time_ok = running_time >= ready_time
            color_ok = color_delta >= self.color_change_threshold
            is_ready = bool(time_ok and color_ok)

        if is_ready:
            self.completion_detected = True
            self.completion_time = time.time()

            print(f"[{self.pot_name} LiftTracker] ✅ 완료 감지! "
                  f"시간={running_time:.0f}초 (완료허용={ready_time:.0f}초, 목표={self.target_time}초), "
                  f"색변화={color_delta:.1f} (임계값={self.color_change_threshold})")

    def save_session_data(self, save_dir: str) -> str:
        """세션 데이터 저장"""
        if not self.session_id:
            return None

        os.makedirs(save_dir, exist_ok=True)

        data = {
            'session_id': self.session_id,
            'pot_name': self.pot_name,
            'food_type': self.food_type,
            'target_time': self.target_time,
            'start_time': datetime.fromtimestamp(self.start_time).strftime("%Y-%m-%d %H:%M:%S"),
            'completion_detected': self.completion_detected,
            'completion_time': datetime.fromtimestamp(self.completion_time).strftime("%Y-%m-%d %H:%M:%S") if self.completion_time else None,
            'lift_count': len(self.lift_events),
            'baseline_color': self.baseline_color,
            'lift_events': [asdict(event) for event in self.lift_events],
            'config': {
                'lift_area_threshold': self.lift_area_threshold,
                'color_change_threshold': self.color_change_threshold,
                'lift_cooldown_sec': self.lift_cooldown_sec
            }
        }

        filename = f"{self.session_id}_lift_events.json"
        filepath = os.path.join(save_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"[{self.pot_name} LiftTracker] 💾 탈탈 데이터 저장: {filepath}")
        return filepath

    def get_status(self) -> Dict:
        """현재 상태 반환"""
        if not self.active:
            return {
                'active': False,
                'lift_count': 0,
                'completion_detected': False
            }

        running_time = time.time() - self.start_time if self.start_time else 0

        return {
            'active': True,
            'session_id': self.session_id,
            'food_type': self.food_type,
            'running_time': running_time,
            'target_time': self.target_time,
            'lift_count': len(self.lift_events),
            'completion_detected': self.completion_detected,
            'last_color_delta': self.lift_events[-1].color_delta if self.lift_events else 0
        }
