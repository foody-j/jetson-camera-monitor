# Jetson2 Frying C++ Step1 (Color Postprocess)

이 디렉토리는 Frying 경로에서 `mask + HSV/LAB` 기반 색상 통계를 C++로 분리한 1단계다.

## 포함 범위
- `food_area_ratio`
- `mean/std HSV`
- `mean LAB`
- `dominant_hue`
- `brown_ratio`, `golden_ratio`

YOLO 추론 자체는 포함하지 않는다.

## 파일
- `src/frying_postprocess.cpp`: C++ 계산 코어
- `python/frying_postprocess.py`: ctypes 래퍼
- `python/benchmark_frying_postprocess.py`: Python 대비 벤치
- `build.sh`: 빌드 스크립트

## 빌드
```bash
cd /home/yjk/jetson-food-ai/jetson2_frying_ai/cpp_frying_core
bash build.sh
```

## 벤치
```bash
cd /home/yjk/jetson-food-ai/jetson2_frying_ai/cpp_frying_core/python
python3 benchmark_frying_postprocess.py --iters 1000 --h 448 --w 640
```

## 연동 설정 (frying_segmenter.py)
- `frying_cpp_postprocess_enabled`: true/false
- `frying_cpp_postprocess_lib`: so 경로

문제 시 자동 Python 경로로 폴백되도록 구현한다.
