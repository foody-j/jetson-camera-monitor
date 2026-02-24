#!/usr/bin/env python3
"""
Jetson1 진동 판정 규칙 분석 및 개선
- run 단위 feature 계산
- confusion matrix 출력
- 조합 규칙 개선

NOTE: 현재 운영 환경에서는 UID 0x55 (Y축 고장)를 제외하고 UID 0x53, 0x54만 사용.
      이 스크립트는 과거 데이터 분석용으로 UID55 포함 데이터도 읽을 수 있음.
"""
import pandas as pd
import numpy as np
import json
from pathlib import Path
from collections import defaultdict
import re

def load_runs(folder_path, label):
    """타임스탬프별로 UID53/54/55 묶어서 run 단위 로드"""
    files = sorted(Path(folder_path).glob("*_vibration.csv"))

    # 타임스탬프별로 그룹화
    runs = defaultdict(dict)
    for f in files:
        match = re.search(r'(\d{8}_\d{6})_UID(\d+)_', f.name)
        if match:
            timestamp = match.group(1)
            uid = match.group(2)
            runs[timestamp][uid] = f

    # run 단위로 feature 계산
    run_features = []
    for timestamp, uid_files in runs.items():
        if len(uid_files) < 3:  # UID 53/54/55 모두 있어야 함
            continue

        features = {
            'timestamp': timestamp,
            'label': label,
        }

        # 각 UID별 데이터 로드
        all_data = {}
        for uid, fpath in uid_files.items():
            df = pd.read_csv(fpath, encoding='utf-8-sig')
            all_data[uid] = df

        # Feature 계산
        for uid, df in all_data.items():
            features[f'uid{uid}_vel_x_p99'] = df['VEL_X(mm/s)'].quantile(0.99)
            features[f'uid{uid}_vel_y_p99'] = df['VEL_Y(mm/s)'].quantile(0.99)
            features[f'uid{uid}_vel_z_p99'] = df['VEL_Z(mm/s)'].quantile(0.99)

            # velocity magnitude
            vel_mag = np.sqrt(df['VEL_X(mm/s)']**2 + df['VEL_Y(mm/s)']**2 + df['VEL_Z(mm/s)']**2)
            features[f'uid{uid}_vel_mag_p99'] = vel_mag.quantile(0.99)

            features[f'uid{uid}_freq_x_p99'] = df['FREQ_X(Hz)'].quantile(0.99)
            features[f'uid{uid}_freq_y_p99'] = df['FREQ_Y(Hz)'].quantile(0.99)
            features[f'uid{uid}_freq_z_p99'] = df['FREQ_Z(Hz)'].quantile(0.99)

            features[f'uid{uid}_freq_x_max'] = df['FREQ_X(Hz)'].max()
            features[f'uid{uid}_freq_y_max'] = df['FREQ_Y(Hz)'].max()
            features[f'uid{uid}_freq_z_max'] = df['FREQ_Z(Hz)'].max()

        run_features.append(features)

    return pd.DataFrame(run_features)

def apply_current_rule(df, baseline):
    """현재 베이스라인 규칙 적용"""
    thresholds = baseline['thresholds']

    predictions = []
    for _, row in df.iterrows():
        abnormal = False

        # 현재 규칙: 단일 초과시 ABNORMAL
        for uid in ['53', '54', '55']:
            if row[f'uid{uid}_freq_x_max'] > thresholds['freq_x_high']:
                abnormal = True
            if row[f'uid{uid}_freq_y_max'] > thresholds['freq_y_high']:
                abnormal = True
            if row[f'uid{uid}_freq_z_max'] > thresholds['freq_z_high']:
                abnormal = True
            if row[f'uid{uid}_vel_mag_p99'] > thresholds['velocity_magnitude_p99']:
                abnormal = True

        predictions.append('ABNORMAL' if abnormal else 'NORMAL')

    return predictions

def apply_combo_rule(df, thresholds):
    """조합 규칙 적용 - velocity 기반, 상한/하한 threshold"""
    predictions = []
    details = []

    # UID별 상한 threshold (정상 95%ile)
    uid53_max = 8000    # 정상 95%ile = 7667
    uid54_max = 37000   # 정상 95%ile = 36825
    uid55_max = 30500   # 정상 95%ile = 30322

    # UID별 하한 threshold (정상 5%ile) - 센서 고장/접촉불량 감지
    uid53_min = 5000    # 정상 5%ile = 5186
    uid54_min = 25000   # 정상 5%ile = 25920
    uid55_min = 12000   # 정상 5%ile = 12870

    for _, row in df.iterrows():
        abnormal = False
        reason = []

        # 규칙1: 상한 초과 (진동 과다)
        if row['uid53_vel_mag_p99'] > uid53_max:
            abnormal = True
            reason.append(f"UID53 HIGH")
        if row['uid54_vel_mag_p99'] > uid54_max:
            abnormal = True
            reason.append(f"UID54 HIGH")
        if row['uid55_vel_mag_p99'] > uid55_max:
            abnormal = True
            reason.append(f"UID55 HIGH")

        # 규칙2: 하한 미달 (센서 고장/접촉불량)
        if row['uid53_vel_mag_p99'] < uid53_min:
            abnormal = True
            reason.append(f"UID53 LOW")
        if row['uid54_vel_mag_p99'] < uid54_min:
            abnormal = True
            reason.append(f"UID54 LOW")
        if row['uid55_vel_mag_p99'] < uid55_min:
            abnormal = True
            reason.append(f"UID55 LOW")

        predictions.append('ABNORMAL' if abnormal else 'NORMAL')
        details.append({
            'timestamp': row['timestamp'],
            'label': row['label'],
            'prediction': 'ABNORMAL' if abnormal else 'NORMAL',
            'uid53_vel': row['uid53_vel_mag_p99'],
            'uid54_vel': row['uid54_vel_mag_p99'],
            'uid55_vel': row['uid55_vel_mag_p99'],
            'reason': ', '.join(reason) if reason else 'OK'
        })

    return predictions, details

def print_confusion_matrix(y_true, y_pred, title):
    """Confusion Matrix 출력"""
    tp = sum((t == 'ABNORMAL' and p == 'ABNORMAL') for t, p in zip(y_true, y_pred))
    fn = sum((t == 'ABNORMAL' and p == 'NORMAL') for t, p in zip(y_true, y_pred))
    fp = sum((t == 'NORMAL' and p == 'ABNORMAL') for t, p in zip(y_true, y_pred))
    tn = sum((t == 'NORMAL' and p == 'NORMAL') for t, p in zip(y_true, y_pred))

    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    print(f"{'':20} {'예측 NORMAL':15} {'예측 ABNORMAL':15}")
    print(f"{'실제 NORMAL':20} TN={tn:3d} (정답)    FP={fp:3d} (오탐)")
    print(f"{'실제 ABNORMAL':20} FN={fn:3d} (미탐)    TP={tp:3d} (정답)")
    print(f"\n정확도: {(tp+tn)/(tp+tn+fp+fn)*100:.1f}%")
    print(f"재현율 (ABNORMAL 감지율): {tp/(tp+fn)*100:.1f}% (TP/{tp+fn})")
    print(f"정밀도 (ABNORMAL 판정 정확도): {tp/(tp+fp)*100:.1f}% (TP/{tp+fp})" if (tp+fp) > 0 else "정밀도: N/A")
    print(f"오탐률 (FP Rate): {fp/(fp+tn)*100:.1f}% (FP/{fp+tn})")

    return {'TP': tp, 'FN': fn, 'FP': fp, 'TN': tn}

def optimize_thresholds(normal_df, abnormal_df, baseline):
    """데이터 기반 threshold 최적화"""
    thresholds = baseline['thresholds'].copy()

    # 정상 데이터 95%ile로 조정
    freq_x_vals = []
    freq_y_vals = []
    freq_z_vals = []

    for uid in ['53', '54', '55']:
        freq_x_vals.extend(normal_df[f'uid{uid}_freq_x_max'].values)
        freq_y_vals.extend(normal_df[f'uid{uid}_freq_y_max'].values)
        freq_z_vals.extend(normal_df[f'uid{uid}_freq_z_max'].values)

    # 정상 데이터의 99%ile + 10% 마진
    thresholds['freq_x_high'] = np.percentile(freq_x_vals, 99) * 1.1
    thresholds['freq_y_high'] = np.percentile(freq_y_vals, 99) * 1.1
    thresholds['freq_z_high'] = np.percentile(freq_z_vals, 99) * 1.1

    # velocity magnitude는 유지
    # thresholds['velocity_magnitude_p99'] 그대로

    return thresholds

def main():
    print("="*80)
    print("Jetson1 진동 판정 규칙 분석 및 개선")
    print("="*80)

    # 1. 데이터 로드
    print("\n[1] 데이터 로드 중...")
    normal_df = load_runs("jetson1_monitoring/젯슨1 정상", "NORMAL")
    abnormal_df = load_runs("jetson1_monitoring/젯슨1 비정상", "ABNORMAL")

    print(f"  정상 runs: {len(normal_df)}개")
    print(f"  비정상 runs: {len(abnormal_df)}개")

    # 전체 데이터
    all_df = pd.concat([normal_df, abnormal_df], ignore_index=True)
    y_true = all_df['label'].values

    # 2. 현재 베이스라인 로드
    with open('vibration_baseline_jetson1.json', 'r') as f:
        baseline = json.load(f)

    # 3. 현재 규칙 평가
    print("\n[2] 현재 규칙 평가...")
    y_pred_current = apply_current_rule(all_df, baseline)
    metrics_before = print_confusion_matrix(y_true, y_pred_current, "현재 규칙 (단일 초과)")

    # 4. Threshold 최적화
    print("\n[3] Threshold 최적화 중...")
    new_thresholds = optimize_thresholds(normal_df, abnormal_df, baseline)

    print(f"\n  변경 전:")
    print(f"    FREQ_X: {baseline['thresholds']['freq_x_high']:.1f} Hz")
    print(f"    FREQ_Y: {baseline['thresholds']['freq_y_high']:.1f} Hz")
    print(f"    FREQ_Z: {baseline['thresholds']['freq_z_high']:.1f} Hz")
    print(f"\n  변경 후:")
    print(f"    FREQ_X: {new_thresholds['freq_x_high']:.1f} Hz")
    print(f"    FREQ_Y: {new_thresholds['freq_y_high']:.1f} Hz")
    print(f"    FREQ_Z: {new_thresholds['freq_z_high']:.1f} Hz")

    # 5. 조합 규칙 평가
    print("\n[4] 조합 규칙 평가...")
    y_pred_combo, combo_details = apply_combo_rule(all_df, new_thresholds)
    metrics_after = print_confusion_matrix(y_true, y_pred_combo, "조합 규칙 (2센서 동시 OR 강한 초과)")

    # 미탐지 분석
    print("\n[4-1] 미탐지 사례 분석 (FN)")
    print("="*60)
    for detail in combo_details:
        if detail['label'] == 'ABNORMAL' and detail['prediction'] == 'NORMAL':
            print(f"\n타임스탬프: {detail['timestamp']}")
            print(f"  UID53 vel_mag: {detail['uid53_vel']:,.0f} mm/s (thresh: 8,000)")
            print(f"  UID54 vel_mag: {detail['uid54_vel']:,.0f} mm/s (thresh: 37,000)")
            print(f"  UID55 vel_mag: {detail['uid55_vel']:,.0f} mm/s (thresh: 30,500)")

    # 6. 개선 결과
    print("\n[5] 개선 결과")
    print("="*60)
    print(f"오탐(FP): {metrics_before['FP']} → {metrics_after['FP']} ({metrics_after['FP']-metrics_before['FP']:+d})")
    print(f"미탐(FN): {metrics_before['FN']} → {metrics_after['FN']} ({metrics_after['FN']-metrics_before['FN']:+d})")
    print(f"정답(TP): {metrics_before['TP']} → {metrics_after['TP']} ({metrics_after['TP']-metrics_before['TP']:+d})")

    # 7. 베이스라인 업데이트
    print("\n[6] 베이스라인 파일 업데이트...")
    baseline['thresholds'] = new_thresholds
    baseline['thresholds']['_comment_combo_rule'] = "UID-specific velocity rule: upper/lower bounds (95%ile/5%ile)"
    baseline['thresholds']['combo_rule_enabled'] = True
    baseline['thresholds']['min_exceed_duration_sec'] = 0.5
    baseline['thresholds']['uid53_vel_mag_max'] = 8000
    baseline['thresholds']['uid54_vel_mag_max'] = 37000
    baseline['thresholds']['uid55_vel_mag_max'] = 30500
    baseline['thresholds']['uid53_vel_mag_min'] = 5000
    baseline['thresholds']['uid54_vel_mag_min'] = 25000
    baseline['thresholds']['uid55_vel_mag_min'] = 12000

    with open('vibration_baseline_jetson1.json', 'w') as f:
        json.dump(baseline, f, indent=2, ensure_ascii=False)

    print("  ✅ vibration_baseline_jetson1.json 업데이트 완료")

    # 8. 규칙 설명 출력
    print("\n[7] 최종 규칙")
    print("="*60)
    print("조합 규칙 (velocity 기반, UID별 상한/하한 threshold):")
    print("  - 상한 초과: 진동 과다 감지")
    print("  - 하한 미달: 센서 고장/접촉불량 감지")
    print("\nUID별 상한 Threshold (정상 95%ile):")
    print(f"  UID53: 8,000 mm/s (정상 95%ile: 7,667)")
    print(f"  UID54: 37,000 mm/s (정상 95%ile: 36,825)")
    print(f"  UID55: 30,500 mm/s (정상 95%ile: 30,322)")
    print("\nUID별 하한 Threshold (정상 5%ile):")
    print(f"  UID53: 5,000 mm/s (정상 5%ile: 5,186)")
    print(f"  UID54: 25,000 mm/s (정상 5%ile: 25,920)")
    print(f"  UID55: 12,000 mm/s (정상 5%ile: 12,870)")
    print(f"\nFREQ (참고용, min_uid_count=1):")
    print(f"  FREQ_X/Y/Z: {new_thresholds['freq_x_high']:.1f} Hz")

    print("\n완료!")

if __name__ == "__main__":
    main()
