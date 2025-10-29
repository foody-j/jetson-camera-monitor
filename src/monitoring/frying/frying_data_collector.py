#!/usr/bin/env python3
"""
튀김 조리 자동화 데이터 수집 시스템
- 조리 과정 이미지 자동 수집
- 센서 데이터 로깅 (온도, 시간)
- Ground Truth 라벨링 (탐침온도계)
- 학습용 데이터셋 자동 구성
"""

import os
import sys
import json
import time
import cv2
import numpy as np
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import threading
import queue

# 기존 카메라 시스템 활용
try:
    # Try relative import first (when used as a module)
    from ..camera import CameraBase
except ImportError:
    # Fallback to absolute import (when run as script)
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from monitoring.camera import CameraBase

# Utility function for timestamps
def get_timestamp(fmt: str = "%Y%m%d_%H%M%S") -> str:
    """Get formatted timestamp"""
    return datetime.now().strftime(fmt)


# ================== 데이터 구조 정의 ==================

@dataclass
class SensorData:
    """센서 데이터"""
    timestamp: float
    oil_temp: float      # 튀김유 온도
    fryer_temp: float    # 튀김기 온도  
    elapsed_time: float  # 투입 후 경과시간
    
@dataclass
class FrameData:
    """프레임 데이터"""
    timestamp: float
    image_path: str
    sensor_data: SensorData
    is_complete: bool = False  # 완료 여부
    
@dataclass
class SessionData:
    """조리 세션 데이터"""
    session_id: str
    food_type: str           # 튀김 종류 (치킨, 새우, 감자 등)
    start_time: float
    end_time: Optional[float]
    completion_time: Optional[float]  # 완료 시점
    probe_temp: Optional[float]       # 탐침온도계 온도
    frames: List[FrameData]
    notes: str = ""


# ================== 센서 인터페이스 ==================

class SensorInterface:
    """센서 읽기 인터페이스 (추후 실제 센서로 교체)"""
    
    def __init__(self, simulate: bool = True):
        self.simulate = simulate
        self.base_oil_temp = 170.0
        self.base_fryer_temp = 175.0
        self.start_time = None
        
    def start_cooking(self):
        """조리 시작"""
        self.start_time = time.time()
        
    def read(self) -> SensorData:
        """센서 값 읽기"""
        if self.simulate:
            # 시뮬레이션: 시간에 따라 온도 감소
            elapsed = time.time() - self.start_time if self.start_time else 0
            
            # 온도는 시간에 따라 서서히 감소 (실제와 유사하게)
            oil_temp = self.base_oil_temp - (elapsed * 0.05)  # 1초당 0.05도 감소
            fryer_temp = self.base_fryer_temp - (elapsed * 0.03)
            
            # 노이즈 추가
            oil_temp += np.random.normal(0, 0.5)
            fryer_temp += np.random.normal(0, 0.3)
            
        else:
            # TODO: 실제 센서 읽기 구현
            # oil_temp = self.read_oil_sensor()
            # fryer_temp = self.read_fryer_sensor()
            pass
            
        return SensorData(
            timestamp=time.time(),
            oil_temp=oil_temp,
            fryer_temp=fryer_temp,
            elapsed_time=time.time() - self.start_time if self.start_time else 0
        )


# ================== 데이터 수집기 ==================

class FryingDataCollector:
    """튀김 조리 데이터 수집기"""
    
    def __init__(self, 
                 base_dir: str = "frying_dataset",
                 camera_index: int = 0,
                 resolution: Tuple[int, int] = None,
                 fps: int = 1):  # 1초에 1장 (데이터 수집용)
        """
        Args:
            base_dir: 데이터 저장 기본 디렉토리
            camera_index: 카메라 인덱스
            resolution: 해상도 (None이면 config에서 읽음)
            fps: 초당 수집 프레임 수 (데이터 저장 간격)
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        
        # Config 파일에서 설정 읽기
        config_path = Path(__file__).parent.parent / "camera_config.json"
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
                # resolution이 지정되지 않으면 config에서 읽기
                if resolution is None:
                    cam_config = config.get('camera', {})
                    res = cam_config.get('resolution', {})
                    resolution = (res.get('width', 640), res.get('height', 360))
                    camera_index = cam_config.get('index', camera_index)
                print(f"📷 Config 로드: {resolution[0]}x{resolution[1]}")
        else:
            # Config 없으면 기본값
            if resolution is None:
                resolution = (640, 360)
        
        # 카메라 초기화
        self.camera = CameraBase(camera_index, resolution)
        self.fps = fps  # 데이터 수집 FPS (카메라 FPS와 별개)
        
        # 센서 인터페이스
        self.sensors = SensorInterface(simulate=True)
        
        # 현재 세션
        self.current_session: Optional[SessionData] = None
        self.is_collecting = False
        
        # 수집 스레드
        self.collect_thread = None
        self.stop_event = threading.Event()
        
        # 통계
        self.stats = {
            'total_sessions': 0,
            'total_frames': 0,
            'completed_samples': 0,
            'incomplete_samples': 0
        }
        
    def initialize(self) -> bool:
        """시스템 초기화"""
        if not self.camera.initialize():
            print("❌ 카메라 초기화 실패")
            return False
        print("✅ 카메라 초기화 성공")
        return True
        
    def start_session(self, food_type: str = "unknown", notes: str = "") -> str:
        """
        새로운 조리 세션 시작
        
        Args:
            food_type: 튀김 종류 (chicken, shrimp, potato 등)
            notes: 메모 (온도 설정, 특이사항 등)
            
        Returns:
            session_id: 세션 ID
        """
        if self.is_collecting:
            print("⚠️ 이미 수집 중입니다")
            return ""
            
        # 세션 ID 생성
        session_id = f"{food_type}_{get_timestamp()}"
        
        # 세션 디렉토리 생성
        session_dir = self.base_dir / session_id
        session_dir.mkdir(exist_ok=True)
        (session_dir / "images").mkdir(exist_ok=True)
        
        # 세션 데이터 초기화
        self.current_session = SessionData(
            session_id=session_id,
            food_type=food_type,
            start_time=time.time(),
            end_time=None,
            completion_time=None,
            probe_temp=None,
            frames=[],
            notes=notes
        )
        
        # 센서 초기화
        self.sensors.start_cooking()
        
        # 수집 시작
        self.is_collecting = True
        self.stop_event.clear()
        self.collect_thread = threading.Thread(target=self._collection_loop)
        self.collect_thread.start()
        
        self.stats['total_sessions'] += 1
        
        print(f"🔴 세션 시작: {session_id}")
        print(f"   음식: {food_type}")
        print(f"   메모: {notes}")
        
        return session_id
        
    def _collection_loop(self):
        """데이터 수집 루프 (별도 스레드)"""
        frame_interval = 1.0 / self.fps
        frame_count = 0
        
        while not self.stop_event.is_set():
            start_time = time.time()
            
            # 프레임 캡처
            ret, frame = self.camera.read_frame()
            if ret and frame is not None:
                # 센서 데이터 읽기
                sensor_data = self.sensors.read()
                
                # 이미지 저장
                timestamp_str = f"t{frame_count:04d}"
                image_filename = f"{timestamp_str}.jpg"
                image_path = self.current_session.session_id + f"/images/{image_filename}"
                full_path = self.base_dir / image_path
                
                cv2.imwrite(str(full_path), frame)
                
                # 프레임 데이터 추가
                frame_data = FrameData(
                    timestamp=time.time(),
                    image_path=image_path,
                    sensor_data=sensor_data,
                    is_complete=False  # 나중에 라벨링
                )
                
                self.current_session.frames.append(frame_data)
                frame_count += 1
                self.stats['total_frames'] += 1
                
                # 상태 출력 (5초마다)
                if frame_count % (self.fps * 5) == 0:
                    self._print_status(frame_count, sensor_data)
                    
            # FPS 유지
            elapsed = time.time() - start_time
            if elapsed < frame_interval:
                time.sleep(frame_interval - elapsed)
                
    def _print_status(self, frame_count: int, sensor_data: SensorData):
        """현재 상태 출력"""
        print(f"📊 [{get_timestamp('%H:%M:%S')}] "
              f"프레임: {frame_count} | "
              f"경과: {sensor_data.elapsed_time:.1f}초 | "
              f"유온도: {sensor_data.oil_temp:.1f}°C | "
              f"튀김기: {sensor_data.fryer_temp:.1f}°C")
              
    def mark_completion(self, probe_temp: float, notes: str = "") -> bool:
        """
        완료 시점 마킹 (Ground Truth)
        
        Args:
            probe_temp: 탐침온도계 온도
            notes: 추가 메모
            
        Returns:
            성공 여부
        """
        if not self.current_session:
            print("❌ 진행 중인 세션이 없습니다")
            return False
            
        completion_time = time.time()
        self.current_session.completion_time = completion_time
        self.current_session.probe_temp = probe_temp
        
        if notes:
            self.current_session.notes += f" | 완료: {notes}"
            
        # 완료 시점 이후 프레임들을 '완료'로 라벨링
        for frame in self.current_session.frames:
            if frame.timestamp >= completion_time:
                frame.is_complete = True
                
        self.stats['completed_samples'] += sum(1 for f in self.current_session.frames if f.is_complete)
        self.stats['incomplete_samples'] += sum(1 for f in self.current_session.frames if not f.is_complete)
        
        print(f"✅ 완료 마킹: 탐침온도 {probe_temp}°C")
        print(f"   완료 프레임: {sum(1 for f in self.current_session.frames if f.is_complete)}개")
        print(f"   미완료 프레임: {sum(1 for f in self.current_session.frames if not f.is_complete)}개")
        
        return True
        
    def stop_session(self) -> str:
        """
        세션 종료 및 데이터 저장
        
        Returns:
            저장된 파일 경로
        """
        if not self.is_collecting:
            print("⚠️ 수집 중이 아닙니다")
            return ""
            
        # 수집 중지
        self.is_collecting = False
        self.stop_event.set()
        
        if self.collect_thread:
            self.collect_thread.join()
            
        self.current_session.end_time = time.time()
        
        # 데이터 저장
        save_path = self._save_session_data()
        
        # 통계 출력
        self._print_session_summary()
        
        # 초기화
        self.current_session = None
        
        return save_path
        
    def _save_session_data(self) -> str:
        """세션 데이터를 JSON으로 저장"""
        if not self.current_session:
            return ""
            
        # 데이터 변환 (dataclass -> dict)
        session_dict = asdict(self.current_session)
        
        # 저장
        json_path = self.base_dir / self.current_session.session_id / "session_data.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(session_dict, f, indent=2, ensure_ascii=False)
            
        # CSV로도 저장 (센서 데이터)
        csv_path = self.base_dir / self.current_session.session_id / "sensor_log.csv"
        with open(csv_path, 'w') as f:
            f.write("timestamp,elapsed_time,oil_temp,fryer_temp,is_complete\n")
            for frame in self.current_session.frames:
                f.write(f"{frame.timestamp:.2f},"
                       f"{frame.sensor_data.elapsed_time:.2f},"
                       f"{frame.sensor_data.oil_temp:.2f},"
                       f"{frame.sensor_data.fryer_temp:.2f},"
                       f"{frame.is_complete}\n")
                       
        print(f"💾 데이터 저장: {json_path}")
        print(f"💾 센서 로그: {csv_path}")
        
        return str(json_path)
        
    def _print_session_summary(self):
        """세션 요약 출력"""
        if not self.current_session:
            return
            
        duration = self.current_session.end_time - self.current_session.start_time
        total_frames = len(self.current_session.frames)
        
        print("\n" + "=" * 60)
        print("📊 세션 요약")
        print("=" * 60)
        print(f"세션 ID: {self.current_session.session_id}")
        print(f"음식 종류: {self.current_session.food_type}")
        print(f"총 시간: {duration:.1f}초 ({duration/60:.1f}분)")
        print(f"총 프레임: {total_frames}개")
        
        if self.current_session.completion_time:
            completion_duration = self.current_session.completion_time - self.current_session.start_time
            print(f"완료 시점: {completion_duration:.1f}초")
            print(f"탐침 온도: {self.current_session.probe_temp}°C")
            
        print("=" * 60)
        
    def get_statistics(self) -> Dict:
        """전체 통계 반환"""
        return {
            **self.stats,
            'base_dir': str(self.base_dir),
            'sessions': self._get_session_list()
        }
        
    def _get_session_list(self) -> List[str]:
        """저장된 세션 목록"""
        sessions = []
        for session_dir in self.base_dir.iterdir():
            if session_dir.is_dir() and (session_dir / "session_data.json").exists():
                sessions.append(session_dir.name)
        return sorted(sessions)
        
    def cleanup(self):
        """리소스 정리"""
        if self.is_collecting:
            self.stop_session()
        self.camera.release()
        

# ================== 테스트 및 사용 예시 ==================

def test_data_collection():
    """데이터 수집 테스트"""
    collector = FryingDataCollector(fps=2)  # 초당 2프레임
    
    if not collector.initialize():
        return
        
    try:
        # 치킨 튀김 시뮬레이션
        print("\n🍗 치킨 튀김 데이터 수집 시작")
        session_id = collector.start_session(
            food_type="chicken",
            notes="테스트 수집, 170도 설정"
        )
        
        # 30초간 수집
        print("30초간 데이터 수집 중...")
        time.sleep(30)
        
        # 완료 마킹 (실제로는 탐침온도계로 측정)
        collector.mark_completion(
            probe_temp=75.5,  # 닭고기 안전 온도
            notes="겉은 황금색, 속은 완전히 익음"
        )
        
        # 추가 5초 수집 (완료 후 데이터)
        print("완료 후 5초 추가 수집...")
        time.sleep(5)
        
        # 세션 종료
        collector.stop_session()
        
        # 통계 출력
        stats = collector.get_statistics()
        print(f"\n📈 전체 통계:")
        print(f"   총 세션: {stats['total_sessions']}")
        print(f"   총 프레임: {stats['total_frames']}")
        print(f"   완료 샘플: {stats['completed_samples']}")
        print(f"   미완료 샘플: {stats['incomplete_samples']}")
        
    finally:
        collector.cleanup()
        

def interactive_collection():
    """대화형 데이터 수집"""
    collector = FryingDataCollector()
    
    if not collector.initialize():
        return
        
    print("\n" + "=" * 60)
    print("🍤 튀김 데이터 수집 시스템")
    print("=" * 60)
    print("명령어:")
    print("  s: 새 세션 시작")
    print("  c: 완료 마킹")
    print("  e: 세션 종료")
    print("  q: 프로그램 종료")
    print("=" * 60)
    
    try:
        while True:
            cmd = input("\n명령> ").strip().lower()
            
            if cmd == 's':
                food_type = input("음식 종류 (chicken/shrimp/potato): ")
                notes = input("메모: ")
                collector.start_session(food_type, notes)
                
            elif cmd == 'c':
                if collector.is_collecting:
                    temp = float(input("탐침 온도(°C): "))
                    notes = input("완료 메모: ")
                    collector.mark_completion(temp, notes)
                else:
                    print("⚠️ 세션이 진행 중이 아닙니다")
                    
            elif cmd == 'e':
                if collector.is_collecting:
                    collector.stop_session()
                else:
                    print("⚠️ 세션이 진행 중이 아닙니다")
                    
            elif cmd == 'q':
                break
                
            else:
                print("❌ 알 수 없는 명령어")
                
    except KeyboardInterrupt:
        print("\n\n중단됨")
        
    finally:
        collector.cleanup()
        

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_data_collection()
    else:
        interactive_collection()