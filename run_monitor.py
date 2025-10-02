#!/usr/bin/env python3
"""
통합 카메라 모니터링 시스템 (헤드리스 모드)
- 움직임 감지
- 자동 녹화
- 로그 기록
- 백그라운드 실행
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import time
import signal
import datetime
from config import Config
from camera_monitor.camera_base import CameraBase
from camera_monitor.motion_detector import MotionDetector
from camera_monitor.recorder import MediaRecorder

# 전역 변수
is_running = True
stats = {
    'start_time': None,
    'frames_processed': 0,
    'motion_detected': 0,
    'screenshots_saved': 0,
    'recording_count': 0
}

def signal_handler(sig, frame):
    """Ctrl+C 처리"""
    global is_running
    print("\n\n⏸️ 종료 신호 받음... 정리 중...")
    is_running = False

def log(message, level="INFO"):
    """로그 출력"""
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] [{level}] {message}")

def print_stats():
    """통계 출력"""
    if stats['start_time']:
        elapsed = time.time() - stats['start_time']
        fps = stats['frames_processed'] / elapsed if elapsed > 0 else 0
        
        print("\n" + "=" * 60)
        print("📊 현재 통계")
        print("=" * 60)
        print(f"  실행 시간: {elapsed/60:.1f}분 ({elapsed:.0f}초)")
        print(f"  처리 프레임: {stats['frames_processed']:,}개")
        print(f"  평균 FPS: {fps:.1f}")
        print(f"  움직임 감지: {stats['motion_detected']}회")
        print(f"  스크린샷: {stats['screenshots_saved']}개")
        print(f"  녹화 세션: {stats['recording_count']}개")
        print("=" * 60 + "\n")

def main():
    global is_running
    
    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("=" * 60)
    print("🎬 통합 카메라 모니터링 시스템 시작")
    print("=" * 60)
    
    # 1. Config 로드
    log("Config 로드 중...")
    config = Config("camera_config.json")
    
    log(f"카메라: {config.get('camera.name')}")
    log(f"해상도: {config.get('camera.resolution.width')}x{config.get('camera.resolution.height')}")
    log(f"녹화 코덱: {config.get('recording.codec')}")
    
    # 2. 카메라 초기화
    log("카메라 초기화 중...")
    camera = CameraBase(
        camera_index=config.get('camera.index'),
        resolution=(
            config.get('camera.resolution.width'),
            config.get('camera.resolution.height')
        )
    )
    
    if not camera.initialize():
        log("카메라 초기화 실패!", "ERROR")
        return 1
    
    log("✅ 카메라 초기화 성공")
    
    # 3. Recorder 초기화
    log("Recorder 초기화 중...")
    recorder = MediaRecorder(
        camera,
        recording_dir=config.get('recording.output_dir'),
        screenshot_dir=config.get('screenshot.output_dir')
    )
    
    # 4. 움직임 감지기 초기화
    log("움직임 감지기 초기화 중...")
    detector = MotionDetector(
        threshold=config.get('motion_detection.threshold'),
        min_area=config.get('motion_detection.min_area')
    )
    
    # 움직임 감지 콜백
    def on_motion(frame):
        stats['motion_detected'] += 1
        timestamp = datetime.datetime.now().strftime('%H:%M:%S')
        
        # 자동 스크린샷
        if config.get('screenshot.auto_capture_on_motion'):
            filename = f"motion_{stats['motion_detected']:04d}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            recorder.take_screenshot(frame, filename)
            stats['screenshots_saved'] += 1
            log(f"🚨 움직임 감지 #{stats['motion_detected']} → 스크린샷 저장", "MOTION")
    
    detector.set_callback(on_motion)
    
    if config.get('motion_detection.enabled'):
        detector.enable()
        log("✅ 움직임 감지 활성화")
    else:
        log("⏸️ 움직임 감지 비활성화 (config 설정)")
    
    # 5. 자동 녹화 시작 여부
    if config.get('recording.auto_start'):
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"auto_recording_{timestamp}.avi"
        if recorder.start_recording(filename, codec=config.get('recording.codec')):
            stats['recording_count'] += 1
            log(f"🔴 자동 녹화 시작: {filename}", "RECORDING")
    
    # 6. 메인 루프
    log("메인 모니터링 루프 시작...")
    log("Ctrl+C로 종료하세요\n")
    
    stats['start_time'] = time.time()
    last_stats_time = time.time()
    
    try:
        while is_running:
            ret, frame = camera.read_frame()
            
            if not ret:
                log("프레임 읽기 실패", "WARNING")
                time.sleep(0.1)
                continue
            
            stats['frames_processed'] += 1
            
            # 움직임 감지
            if detector.enabled:
                detector.detect(frame)
            
            # 녹화 중이면 프레임 기록
            if recorder.is_recording:
                recorder.write_frame(frame)
            
            # 30초마다 통계 출력
            if time.time() - last_stats_time > 30:
                print_stats()
                last_stats_time = time.time()
            
            # FPS 제어 (약 30fps)
            time.sleep(0.033)
    
    except Exception as e:
        log(f"오류 발생: {e}", "ERROR")
        import traceback
        traceback.print_exc()
    
    finally:
        # 7. 정리
        log("\n정리 작업 중...")
        
        if recorder.is_recording:
            recorder.stop_recording()
            log("녹화 중지됨")
        
        camera.release()
        log("카메라 리소스 해제됨")
        
        # 최종 통계
        print_stats()
        
        log("✅ 모니터링 시스템 종료 완료")
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)