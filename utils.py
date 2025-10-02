"""
시간 관련 유틸리티 모듈
모든 시간 관련 함수를 통합 관리하여 timezone 설정을 한 곳에서 제어
"""

import datetime
import pytz
from typing import Optional

# Config 싱글톤 (lazy loading)
_config = None
_timezone_cache = None


def _get_config():
    """Config 객체 가져오기 (lazy loading)"""
    global _config
    if _config is None:
        from config import Config
        _config = Config()
    return _config


def _get_timezone_object() -> pytz.timezone:
    """
    설정된 timezone 객체 반환 (캐싱)
    
    Returns:
        pytz.timezone: timezone 객체
    """
    global _timezone_cache
    
    if _timezone_cache is None:
        try:
            config = _get_config()
            tz_name = config.get('system.timezone', 'Asia/Seoul')
            _timezone_cache = pytz.timezone(tz_name)
        except Exception as e:
            # Config 로드 실패 시 기본값 사용
            print(f"⚠️ Config에서 timezone 로드 실패: {e}")
            print("   기본값 'Asia/Seoul' 사용")
            _timezone_cache = pytz.timezone('Asia/Seoul')
    
    return _timezone_cache


def get_timestamp(format_str: str = "%Y%m%d_%H%M%S") -> str:
    """
    현재 시간을 문자열로 반환 (Config에 설정된 timezone 사용)
    
    Args:
        format_str: strftime 포맷 문자열
        
    Returns:
        str: 포맷된 시간 문자열
        
    Examples:
        >>> get_timestamp()
        '20251002_153045'
        
        >>> get_timestamp("%Y-%m-%d %H:%M:%S")
        '2025-10-02 15:30:45'
    """
    tz = _get_timezone_object()
    return datetime.datetime.now(tz).strftime(format_str)


def get_datetime() -> datetime.datetime:
    """
    현재 시간을 datetime 객체로 반환 (timezone aware)
    
    Returns:
        datetime.datetime: timezone이 설정된 datetime 객체
        
    Examples:
        >>> dt = get_datetime()
        >>> print(dt.tzinfo)
        Asia/Seoul
    """
    tz = _get_timezone_object()
    return datetime.datetime.now(tz)


def get_timezone_name() -> str:
    """
    현재 설정된 timezone 이름 반환
    
    Returns:
        str: timezone 이름 (예: 'Asia/Seoul')
        
    Examples:
        >>> get_timezone_name()
        'Asia/Seoul'
    """
    tz = _get_timezone_object()
    return str(tz)


def format_datetime(dt: datetime.datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    datetime 객체를 문자열로 변환
    
    Args:
        dt: datetime 객체
        format_str: strftime 포맷 문자열
        
    Returns:
        str: 포맷된 시간 문자열
    """
    return dt.strftime(format_str)


def set_timezone(tz_name: str) -> bool:
    """
    런타임에 timezone 변경 (테스트/디버깅용)
    
    Args:
        tz_name: timezone 이름 (예: 'Asia/Seoul', 'UTC', 'America/New_York')
        
    Returns:
        bool: 성공 여부
        
    Examples:
        >>> set_timezone('Asia/Tokyo')
        True
        >>> get_timezone_name()
        'Asia/Tokyo'
    """
    global _timezone_cache
    
    try:
        _timezone_cache = pytz.timezone(tz_name)
        print(f"✅ Timezone 변경: {tz_name}")
        return True
    except pytz.exceptions.UnknownTimeZoneError:
        print(f"❌ 알 수 없는 timezone: {tz_name}")
        return False


def get_available_timezones() -> list:
    """
    사용 가능한 모든 timezone 목록 반환
    
    Returns:
        list: timezone 이름 리스트
    """
    return pytz.all_timezones


def reset_timezone_cache() -> None:
    """
    timezone 캐시 초기화 (Config 재로드 시 사용)
    """
    global _timezone_cache
    _timezone_cache = None
    print("🔄 Timezone 캐시 초기화됨")


# ==================== 추가 헬퍼 함수 ====================

def get_timestamp_with_ms(format_str: str = "%Y%m%d_%H%M%S") -> str:
    """
    밀리초 포함 타임스탬프 반환
    
    Returns:
        str: 밀리초 포함 타임스탬프
        
    Examples:
        >>> get_timestamp_with_ms()
        '20251002_153045_123'
    """
    tz = _get_timezone_object()
    now = datetime.datetime.now(tz)
    ms = now.microsecond // 1000
    return f"{now.strftime(format_str)}_{ms:03d}"


def get_date_string(format_str: str = "%Y-%m-%d") -> str:
    """
    날짜만 문자열로 반환
    
    Examples:
        >>> get_date_string()
        '2025-10-02'
    """
    tz = _get_timezone_object()
    return datetime.datetime.now(tz).strftime(format_str)


def get_time_string(format_str: str = "%H:%M:%S") -> str:
    """
    시간만 문자열로 반환
    
    Examples:
        >>> get_time_string()
        '15:30:45'
    """
    tz = _get_timezone_object()
    return datetime.datetime.now(tz).strftime(format_str)


# ==================== 모듈 정보 ====================

__version__ = "1.0.0"
__all__ = [
    'get_timestamp',
    'get_datetime',
    'get_timezone_name',
    'format_datetime',
    'set_timezone',
    'get_available_timezones',
    'reset_timezone_cache',
    'get_timestamp_with_ms',
    'get_date_string',
    'get_time_string'
]


# ==================== 모듈 초기화 시 정보 출력 ====================

if __name__ != "__main__":
    # import될 때만 실행 (직접 실행 시 제외)
    try:
        tz_name = get_timezone_name()
        # 조용히 초기화 (선택적으로 주석 처리)
        # print(f"🌍 Timezone 설정: {tz_name}")
    except Exception:
        pass


# ==================== 테스트 코드 (직접 실행 시) ====================

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 utils.py 테스트")
    print("=" * 60)
    
    print(f"\n1. 현재 timezone: {get_timezone_name()}")
    print(f"2. 현재 시간 (기본): {get_timestamp()}")
    print(f"3. 현재 시간 (포맷): {get_timestamp('%Y-%m-%d %H:%M:%S')}")
    print(f"4. datetime 객체: {get_datetime()}")
    print(f"5. 날짜만: {get_date_string()}")
    print(f"6. 시간만: {get_time_string()}")
    print(f"7. 밀리초 포함: {get_timestamp_with_ms()}")
    
    print("\n8. Timezone 변경 테스트:")
    set_timezone('UTC')
    print(f"   UTC 시간: {get_timestamp('%Y-%m-%d %H:%M:%S')}")
    
    set_timezone('Asia/Seoul')
    print(f"   한국 시간: {get_timestamp('%Y-%m-%d %H:%M:%S')}")
    
    print("\n✅ 테스트 완료!")