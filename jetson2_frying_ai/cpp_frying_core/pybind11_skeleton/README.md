# pybind11 Skeleton (Step3)

이 폴더는 `ctypes -> pybind11` 전환을 위한 최소 스켈레톤이다.
현재 실행 경로는 `ctypes`를 사용하며, 이 스켈레톤은 다음 단계에서 사용한다.

## 목적
- 함수 호출 오버헤드 감소
- Python/C++ 타입 변환 간결화
- 모듈 import 방식 일원화

## 파일
- `lift_core_bindings.cpp`: pybind11 바인딩 예시
- `CMakeLists.txt`: 빌드 스크립트 예시

## 전환 계획
1. pybind11 설치 확인
2. `calc_color_delta`, `check_completion_ready`부터 바인딩
3. `lift_event_tracker.py`에서 ctypes 경로를 pybind 경로로 대체
