#!/usr/bin/env python3
"""
진동 센서 정상 데이터 베이스라인 분석
각 시스템의 정상 범위를 파악하여 이상 감지 임계값 설정
"""

import pandas as pd
import numpy as np
import os
import glob
import json

def load_all_csv_files(directory):
    """디렉토리 내 모든 CSV 파일 로드"""
    csv_files = glob.glob(os.path.join(directory, "*.csv"))
    all_data = []

    for file in csv_files:
        try:
            df = pd.read_csv(file, encoding='utf-8-sig')
            df['source_file'] = os.path.basename(file)
            all_data.append(df)
        except Exception as e:
            print(f"[오류] {file}: {e}")

    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return pd.DataFrame()

def calculate_baseline_stats(df, system_name):
    """정상 데이터 베이스라인 통계 계산"""

    print(f"\n{'='*70}")
    print(f"  {system_name} 정상 데이터 베이스라인")
    print(f"{'='*70}")

    print(f"\n[기본 정보]")
    print(f"  총 샘플 수: {len(df):,}개")
    print(f"  파일 수: {df['source_file'].nunique()}개")

    # 통계 결과를 저장할 딕셔너리
    baseline = {
        "system": system_name,
        "total_samples": len(df),
        "acceleration": {},
        "velocity": {},
        "displacement": {},
        "frequency": {},
        "fft_peak": {},
        "thresholds": {}
    }

    # 1. 가속도 (ACC) 분석
    print(f"\n[1] 가속도 정상 범위 (g)")
    print(f"{'축':<10} {'평균':<12} {'표준편차':<12} {'최소값':<12} {'최대값':<12} {'99% 상한':<12}")
    print("-" * 70)

    for axis in ['X', 'Y', 'Z']:
        col = f'ACC_{axis}(g)'
        mean = df[col].mean()
        std = df[col].std()
        min_val = df[col].min()
        max_val = df[col].max()
        p99 = df[col].quantile(0.99)

        print(f"{axis:<10} {mean:<12.6f} {std:<12.6f} {min_val:<12.6f} {max_val:<12.6f} {p99:<12.6f}")

        baseline["acceleration"][axis] = {
            "mean": float(mean),
            "std": float(std),
            "min": float(min_val),
            "max": float(max_val),
            "p99": float(p99),
            "threshold_3sigma": float(mean + 3 * std)
        }

    # 2. 속도 (VEL) 분석 - 가장 중요!
    print(f"\n[2] 속도 정상 범위 (mm/s) - 주요 지표")
    print(f"{'축':<10} {'평균':<12} {'표준편차':<12} {'중앙값':<12} {'95% 상한':<12} {'99% 상한':<12}")
    print("-" * 70)

    for axis in ['X', 'Y', 'Z']:
        col = f'VEL_{axis}(mm/s)'
        mean = df[col].mean()
        std = df[col].std()
        median = df[col].median()
        p95 = df[col].quantile(0.95)
        p99 = df[col].quantile(0.99)

        print(f"{axis:<10} {mean:<12.1f} {std:<12.1f} {median:<12.1f} {p95:<12.1f} {p99:<12.1f}")

        baseline["velocity"][axis] = {
            "mean": float(mean),
            "std": float(std),
            "median": float(median),
            "p95": float(p95),
            "p99": float(p99),
            "threshold_3sigma": float(mean + 3 * std)
        }

    # 속도 크기 (Magnitude)
    df['VEL_MAG'] = np.sqrt(df['VEL_X(mm/s)']**2 + df['VEL_Y(mm/s)']**2 + df['VEL_Z(mm/s)']**2)
    mag_mean = df['VEL_MAG'].mean()
    mag_std = df['VEL_MAG'].std()
    mag_p95 = df['VEL_MAG'].quantile(0.95)
    mag_p99 = df['VEL_MAG'].quantile(0.99)

    print(f"\n  [속도 크기 (종합)]")
    print(f"    평균: {mag_mean:.1f} mm/s")
    print(f"    표준편차: {mag_std:.1f} mm/s")
    print(f"    95% 상한: {mag_p95:.1f} mm/s")
    print(f"    99% 상한: {mag_p99:.1f} mm/s")

    baseline["velocity"]["MAGNITUDE"] = {
        "mean": float(mag_mean),
        "std": float(mag_std),
        "p95": float(mag_p95),
        "p99": float(mag_p99),
        "threshold_3sigma": float(mag_mean + 3 * mag_std)
    }

    # 3. 변위 (DISP) 분석
    print(f"\n[3] 변위 정상 범위 (μm)")
    print(f"{'축':<10} {'평균':<12} {'표준편차':<12} {'중앙값':<12} {'95% 상한':<12} {'99% 상한':<12}")
    print("-" * 70)

    for axis in ['X', 'Y', 'Z']:
        col = f'DISP_{axis}(um)'
        mean = df[col].mean()
        std = df[col].std()
        median = df[col].median()
        p95 = df[col].quantile(0.95)
        p99 = df[col].quantile(0.99)

        print(f"{axis:<10} {mean:<12.1f} {std:<12.1f} {median:<12.1f} {p95:<12.1f} {p99:<12.1f}")

        baseline["displacement"][axis] = {
            "mean": float(mean),
            "std": float(std),
            "median": float(median),
            "p95": float(p95),
            "p99": float(p99)
        }

    # 4. 주파수 (FREQ) 분석
    print(f"\n[4] 주파수 정상 범위 (Hz)")
    print(f"{'축':<10} {'평균':<12} {'표준편차':<12} {'최빈 범위':<20} {'95% 상한':<12}")
    print("-" * 70)

    for axis in ['X', 'Y', 'Z']:
        col = f'FREQ_{axis}(Hz)'
        mean = df[col].mean()
        std = df[col].std()
        p95 = df[col].quantile(0.95)

        # 주파수 분포 확인 (0 제외)
        freq_nonzero = df[df[col] > 0][col]
        if len(freq_nonzero) > 0:
            mode_range = f"{freq_nonzero.quantile(0.25):.1f}-{freq_nonzero.quantile(0.75):.1f}"
        else:
            mode_range = "N/A"

        print(f"{axis:<10} {mean:<12.1f} {std:<12.1f} {mode_range:<20} {p95:<12.1f}")

        baseline["frequency"][axis] = {
            "mean": float(mean),
            "std": float(std),
            "p95": float(p95)
        }

    # 5. FFT 피크 분석
    print(f"\n[5] FFT 피크 정상 범위 (Hz)")
    print(f"{'축':<10} {'평균 (0 제외)':<15} {'표준편차':<12} {'유효 비율':<12}")
    print("-" * 70)

    for axis in ['X', 'Y', 'Z']:
        col = f'FFT_PEAK_{axis}(Hz)'
        nonzero = df[df[col] > 0][col]

        if len(nonzero) > 0:
            mean = nonzero.mean()
            std = nonzero.std()
            valid_ratio = len(nonzero) / len(df) * 100

            print(f"{axis:<10} {mean:<15.4f} {std:<12.4f} {valid_ratio:<12.1f}%")

            baseline["fft_peak"][axis] = {
                "mean": float(mean),
                "std": float(std),
                "valid_ratio": float(valid_ratio)
            }

    # 6. 이상 감지 임계값 제안
    print(f"\n[6] 이상 감지 임계값 제안")
    print("=" * 70)

    # 속도 기반 임계값 (가장 중요)
    print(f"\n  ★ 추천 임계값 (속도 기반)")
    print(f"  - VEL_MAGNITUDE > {mag_p99:.1f} mm/s (정상의 99% 초과)")
    print(f"  - VEL_MAGNITUDE > {mag_mean + 3*mag_std:.1f} mm/s (평균 + 3σ)")

    baseline["thresholds"]["velocity_magnitude_p99"] = float(mag_p99)
    baseline["thresholds"]["velocity_magnitude_3sigma"] = float(mag_mean + 3*mag_std)

    # 축별 속도 임계값
    print(f"\n  축별 속도 임계값 (mm/s):")
    for axis in ['X', 'Y', 'Z']:
        col = f'VEL_{axis}(mm/s)'
        p99 = df[col].quantile(0.99)
        mean = df[col].mean()
        std = df[col].std()
        print(f"    VEL_{axis} > {p99:.1f} (99%) 또는 > {mean + 3*std:.1f} (평균+3σ)")
        baseline["thresholds"][f"vel_{axis.lower()}_p99"] = float(p99)
        baseline["thresholds"][f"vel_{axis.lower()}_3sigma"] = float(mean + 3*std)

    # 주파수 이상 범위
    print(f"\n  주파수 이상 범위:")
    for axis in ['X', 'Y', 'Z']:
        col = f'FREQ_{axis}(Hz)'
        p95 = df[col].quantile(0.95)
        p5 = df[col].quantile(0.05)
        print(f"    FREQ_{axis}: < {p5:.1f} Hz 또는 > {p95:.1f} Hz")
        baseline["thresholds"][f"freq_{axis.lower()}_low"] = float(p5)
        baseline["thresholds"][f"freq_{axis.lower()}_high"] = float(p95)

    return baseline

def save_baseline(baseline, filename):
    """베이스라인 JSON으로 저장"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(baseline, f, indent=2, ensure_ascii=False)
    print(f"\n✅ 베이스라인 저장: {filename}")

def main():
    # 데이터 디렉토리
    datasets = [
        {
            "name": "Jetson2 (튀김, 젯슨2정상 재학습)",
            "dir": "/home/yjk/jetson-food-ai/jetson2_frying_ai/젯슨2정상",
            "output": "vibration_baseline_jetson2.json"
        }
    ]

    for dataset in datasets:
        print(f"\n{'#'*70}")
        print(f"  {dataset['name']} 분석 시작")
        print(f"{'#'*70}")

        # 데이터 로드
        df = load_all_csv_files(dataset['dir'])

        if df.empty:
            print(f"[오류] {dataset['name']} 데이터를 로드할 수 없습니다.")
            continue

        # 베이스라인 계산
        baseline = calculate_baseline_stats(df, dataset['name'])

        # JSON 저장
        save_baseline(baseline, dataset['output'])

    print(f"\n{'='*70}")
    print("전체 분석 완료!")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    main()
