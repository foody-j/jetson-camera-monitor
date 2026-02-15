#!/usr/bin/env python3
"""
GMSL 카메라 Fail-safe 모듈
일부 카메라 실패 시 사용 가능한 카메라만으로 운영
"""

import cv2
import subprocess
import time

def detect_working_cameras(max_cams=4, timeout=5):
    """
    사용 가능한 카메라 자동 감지

    Returns:
        list: 작동하는 카메라 ID 리스트 (예: [0, 3])
    """
    working = []

    for cam_id in range(max_cams):
        device = f"/dev/video{cam_id}"

        # GStreamer 파이프라인으로 빠른 테스트
        pipeline = (
            f"v4l2src device={device} num-buffers=3 ! "
            f"video/x-raw,format=UYVY,width=1920,height=1536,framerate=30/1 ! "
            f"fakesink"
        )

        try:
            print(f"🔍 Testing {device}...", end=" ")
            result = subprocess.run(
                ["gst-launch-1.0"] + pipeline.split(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout
            )

            if result.returncode == 0:
                working.append(cam_id)
                print("✅ OK")
            else:
                print("❌ FAIL")

        except subprocess.TimeoutExpired:
            print("⏱️ TIMEOUT")
        except Exception as e:
            print(f"❌ ERROR: {e}")

    return working


def get_camera_config_fallback():
    """
    Fail-safe 카메라 설정 생성

    Returns:
        dict: 동적 카메라 설정
    """
    working_cams = detect_working_cameras()

    if len(working_cams) == 0:
        raise RuntimeError("❌ 사용 가능한 카메라가 없습니다!")

    # 기본 매핑
    cam_roles = {
        0: "left_frying",
        1: "right_frying",
        2: "left_bucket",
        3: "right_bucket"
    }

    config = {
        "cameras": {},
        "working_count": len(working_cams),
        "fallback_mode": len(working_cams) < 4
    }

    # 작동하는 카메라만 활성화
    for cam_id in range(4):
        role = cam_roles[cam_id]
        config["cameras"][role] = {
            "enabled": cam_id in working_cams,
            "device": f"/dev/video{cam_id}",
            "id": cam_id
        }

    # 요약 출력
    print("\n" + "="*50)
    print("📹 카메라 Fail-safe 설정")
    print("="*50)
    for role, cfg in config["cameras"].items():
        status = "✅ 활성" if cfg["enabled"] else "❌ 비활성"
        print(f"  {role:15s} ({cfg['device']}): {status}")

    if config["fallback_mode"]:
        print(f"\n⚠️  Fail-safe 모드: {len(working_cams)}/4 카메라 운영")
    else:
        print(f"\n✅ 정상 모드: 4/4 카메라 운영")
    print("="*50 + "\n")

    return config


if __name__ == "__main__":
    # 테스트
    try:
        config = get_camera_config_fallback()

        # JSON 형식으로 저장 가능
        import json
        with open("/tmp/camera_fallback_config.json", "w") as f:
            json.dump(config, f, indent=2)

        print(f"설정 파일 저장: /tmp/camera_fallback_config.json")

    except Exception as e:
        print(f"❌ 오류: {e}")
        exit(1)
