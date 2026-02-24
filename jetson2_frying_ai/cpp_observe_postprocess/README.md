# Jetson2 Observe C++ Step1 (Postprocess)

이 디렉토리는 `JETSON2_web.py`의 Observe 경로 중, 먼저 C++로 분리하기 쉬운 후처리 파트를 분리한 테스트용 코드다.

## 범위
- 포함:
  - `IN` 클래스 후보 선택
  - cam3(오른쪽)일 때 우측 후보 필터
  - `bbox_pad`, `inner_margin` 적용한 inner box 계산
- 미포함:
  - YOLO `predict()` 자체 추론
  - 이미지 crop/resize/분류 추론

즉, Step1은 "추론 앞뒤의 결정 로직"만 C++로 옮긴 버전이다.

## 디렉토리
- `src/observe_postprocess.cpp`: C++ 구현 (shared lib)
- `build.sh`: 빌드 스크립트
- `python/observe_postprocess.py`: ctypes 래퍼
- `python/benchmark_postprocess.py`: Python 기준 로직과 결과/속도 비교

## 빠른 실행
1. 빌드
```bash
cd /home/yjk/jetson-food-ai/jetson2_frying_ai/cpp_observe_postprocess
bash build.sh
```

2. 벤치마크
```bash
cd /home/yjk/jetson-food-ai/jetson2_frying_ai/cpp_observe_postprocess/python
python3 benchmark_postprocess.py --iters 20000 --boxes 8
```

출력 예시:
- `speedup`: Python 대비 C++ 배수
- `mismatch`: Python 구현과 결과 불일치 횟수 (0이 목표)

## JETSON2_web.py 연동 포인트
Observe 경로의 아래 구간을 대체 대상으로 본다:
- `in_indices` 선택
- cam3 right 후보 처리
- `x1,y1,x2,y2` + inner box 계산

참고 위치:
- `/home/yjk/jetson-food-ai/jetson2_frying_ai/JETSON2_web.py` 의 `ObserveAIWorker.run()` 내부

## 다음 단계 (Step2 권장)
1. `JETSON2_web.py`에 옵션 플래그 추가:
   - `observe_cpp_postprocess_enabled: true/false`
2. enabled일 때만 `ObservePostprocessCpp` 호출
3. 현장 배포 전:
   - 하루 로그 비교
   - mismatch 0 확인
   - FPS/CPU 사용량 측정
