#!/usr/bin/env python3
"""
진동 센서 데이터 분석 스크립트
정상/비정상 데이터의 통계 비교
"""
import pandas as pd
import numpy as np
from pathlib import Path

def analyze_folder(folder_path, label):
    """폴더 내 모든 CSV 파일 분석"""
    csv_files = list(Path(folder_path).glob("*_vibration.csv"))

    if not csv_files:
        print(f"❌ {folder_path}에 CSV 파일이 없습니다")
        return None

    all_stats = []

    for csv_file in csv_files:
        try:
            # BOM 제거를 위해 encoding 지정
            df = pd.read_csv(csv_file, encoding='utf-8-sig')

            # 통계 계산
            stats = {
                'file': csv_file.name,
                'label': label,
                'acc_x_mean': df['ACC_X(g)'].mean(),
                'acc_x_std': df['ACC_X(g)'].std(),
                'acc_x_max': df['ACC_X(g)'].max(),
                'acc_y_mean': df['ACC_Y(g)'].mean(),
                'acc_y_std': df['ACC_Y(g)'].std(),
                'acc_y_max': df['ACC_Y(g)'].max(),
                'acc_z_mean': df['ACC_Z(g)'].mean(),
                'acc_z_std': df['ACC_Z(g)'].std(),
                'acc_z_max': df['ACC_Z(g)'].max(),
                'freq_x_mean': df['FREQ_X(Hz)'].mean(),
                'freq_x_std': df['FREQ_X(Hz)'].std(),
                'freq_x_max': df['FREQ_X(Hz)'].max(),
                'freq_y_mean': df['FREQ_Y(Hz)'].mean(),
                'freq_y_std': df['FREQ_Y(Hz)'].std(),
                'freq_y_max': df['FREQ_Y(Hz)'].max(),
                'freq_z_mean': df['FREQ_Z(Hz)'].mean(),
                'freq_z_std': df['FREQ_Z(Hz)'].std(),
                'freq_z_max': df['FREQ_Z(Hz)'].max(),
            }
            all_stats.append(stats)

        except Exception as e:
            print(f"⚠️  {csv_file.name} 읽기 실패: {e}")

    return pd.DataFrame(all_stats)

def main():
    # 폴더 경로
    normal_folder = "jetson2_frying_ai/젯슨2정상"
    abnormal_folder = "jetson2_frying_ai/젯슨2 비정상"

    print("=" * 80)
    print("Jetson2 진동 센서 정상/비정상 데이터 분석")
    print("=" * 80)

    # 데이터 분석
    print("\n📊 정상 데이터 분석 중...")
    normal_df = analyze_folder(normal_folder, "정상")

    print("📊 비정상 데이터 분석 중...")
    abnormal_df = analyze_folder(abnormal_folder, "비정상")

    if normal_df is None or abnormal_df is None:
        print("❌ 데이터 로드 실패")
        return

    print(f"\n✅ 정상 파일: {len(normal_df)}개")
    print(f"✅ 비정상 파일: {len(abnormal_df)}개")

    # 가속도 비교
    print("\n" + "=" * 80)
    print("📈 가속도 (ACC) 통계 비교")
    print("=" * 80)

    for axis in ['x', 'y', 'z']:
        print(f"\n[ACC_{axis.upper()}]")
        n_mean = normal_df[f'acc_{axis}_mean'].mean()
        n_std = normal_df[f'acc_{axis}_std'].mean()
        n_max = normal_df[f'acc_{axis}_max'].max()

        a_mean = abnormal_df[f'acc_{axis}_mean'].mean()
        a_std = abnormal_df[f'acc_{axis}_std'].mean()
        a_max = abnormal_df[f'acc_{axis}_max'].max()

        print(f"  정상   - 평균: {n_mean:.6f}g, 표준편차: {n_std:.6f}g, 최대: {n_max:.6f}g")
        print(f"  비정상 - 평균: {a_mean:.6f}g, 표준편차: {a_std:.6f}g, 최대: {a_max:.6f}g")
        print(f"  차이   - 평균: {abs(a_mean - n_mean):.6f}g ({abs(a_mean - n_mean)/n_mean*100:.1f}%)")

    # 주파수 비교
    print("\n" + "=" * 80)
    print("📈 주파수 (FREQ) 통계 비교 [⭐ 핵심 지표]")
    print("=" * 80)

    for axis in ['x', 'y', 'z']:
        print(f"\n[FREQ_{axis.upper()}]")
        n_mean = normal_df[f'freq_{axis}_mean'].mean()
        n_std = normal_df[f'freq_{axis}_std'].mean()
        n_max = normal_df[f'freq_{axis}_max'].max()

        a_mean = abnormal_df[f'freq_{axis}_mean'].mean()
        a_std = abnormal_df[f'freq_{axis}_std'].mean()
        a_max = abnormal_df[f'freq_{axis}_max'].max()

        print(f"  정상   - 평균: {n_mean:.2f}Hz, 표준편차: {n_std:.2f}Hz, 최대: {n_max:.2f}Hz")
        print(f"  비정상 - 평균: {a_mean:.2f}Hz, 표준편차: {a_std:.2f}Hz, 최대: {a_max:.2f}Hz")
        print(f"  차이   - 평균: {abs(a_mean - n_mean):.2f}Hz, 최대: {abs(a_max - n_max):.2f}Hz")

    # Baseline 검증
    print("\n" + "=" * 80)
    print("🔍 현재 Baseline 검증")
    print("=" * 80)

    print("\n정상 데이터 최대값:")
    print(f"  FREQ_X: {normal_df['freq_x_max'].max():.2f} Hz")
    print(f"  FREQ_Y: {normal_df['freq_y_max'].max():.2f} Hz")
    print(f"  FREQ_Z: {normal_df['freq_z_max'].max():.2f} Hz")

    print("\n비정상 데이터 최대값:")
    print(f"  FREQ_X: {abnormal_df['freq_x_max'].max():.2f} Hz")
    print(f"  FREQ_Y: {abnormal_df['freq_y_max'].max():.2f} Hz")
    print(f"  FREQ_Z: {abnormal_df['freq_z_max'].max():.2f} Hz")

    # 권장 Threshold
    print("\n" + "=" * 80)
    print("💡 권장 Threshold (정상 데이터 기준)")
    print("=" * 80)

    print("\n방법1: 95% 백분위수 + 20% 안전마진")
    for axis in ['x', 'y', 'z']:
        p95 = normal_df[f'freq_{axis}_max'].quantile(0.95)
        recommended = p95 * 1.2
        print(f"  FREQ_{axis.upper()}: {recommended:.1f} Hz")

    print("\n방법2: 99% 백분위수")
    for axis in ['x', 'y', 'z']:
        p99 = normal_df[f'freq_{axis}_max'].quantile(0.99)
        print(f"  FREQ_{axis.upper()}: {p99:.1f} Hz")

    print("\n방법3: 최대값 + 10% 안전마진")
    for axis in ['x', 'y', 'z']:
        max_val = normal_df[f'freq_{axis}_max'].max()
        recommended = max_val * 1.1
        print(f"  FREQ_{axis.upper()}: {recommended:.1f} Hz")

    print("\n" + "=" * 80)
    print("✅ 분석 완료")
    print("=" * 80)

if __name__ == "__main__":
    main()
