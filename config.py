"""
설정 관리 모듈
"""
import json
import os

class Config:
    """설정 관리 클래스"""
    
    def __init__(self, config_file: str = "camera_config.json"):
        self.config_file = config_file
        self.config = self._load_default()
        self.load()
    
    def _load_default(self):
        """기본 설정"""
        return {
            "system": {
                "timezone": "Asia/Seoul",
                "log_timezone": True
            },
            "camera": {
                "index": 0,
                "resolution": {"width": 640, "height": 360},
                "fps": 30,
                "name": "Default Camera"
            },
            "recording": {
                "codec": "MJPG",
                "output_dir": "recordings",
                "auto_start": False
            },
            "motion_detection": {
                "enabled": False,
                "threshold": 1000,
                "min_area": 500
            },
            "screenshot": {
                "output_dir": "screenshots",
                "format": "jpg",
                "auto_capture_on_motion": True
            }
        }
    
    def load(self):
        """설정 파일 로드"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    loaded = json.load(f)
                    # 기본 설정과 병합
                    self._merge(self.config, loaded)
                print(f"✅ 설정 로드: {self.config_file}")
            except Exception as e:
                print(f"⚠️ 설정 로드 실패: {e}, 기본값 사용")
        else:
            print(f"⚠️ 설정 파일 없음, 기본값 사용")
            self.save()  # 기본 설정 파일 생성
    
    def save(self):
        """설정 저장"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            print(f"✅ 설정 저장: {self.config_file}")
            return True
        except Exception as e:
            print(f"❌ 설정 저장 실패: {e}")
            return False
    
    def get(self, key_path: str, default=None):
        """설정 값 가져오기 (예: 'camera.resolution.width')"""
        keys = key_path.split('.')
        value = self.config
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key_path: str, value):
        """설정 값 변경"""
        keys = key_path.split('.')
        config = self.config
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        config[keys[-1]] = value
    
    def _merge(self, base, update):
        """딕셔너리 병합"""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge(base[key], value)
            else:
                base[key] = value
    def get_timezone(self):
        """현재 설정된 timezone 반환"""
        return self.get('system.timezone', 'Asia/Seoul')
    
    def set_timezone(self, timezone):
        """timezone 설정"""
        self.set('system.timezone', timezone)
        return self.save()