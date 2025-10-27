#!/usr/bin/env python3
"""
튀김 음식 분할 및 색상 특징 추출
- 음식 영역과 배경(기름/그릇) 분리
- HSV 기반 색상 특징 추출
- 시각화 및 분석
"""

import os
import sys
import cv2
import numpy as np
import json
from pathlib import Path
from typing import Tuple, Dict, List, Optional
import matplotlib
matplotlib.use('Agg')  # Headless backend for SSH/Docker
import matplotlib.pyplot as plt
from dataclasses import dataclass, asdict

# 상위 디렉토리 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class ColorFeatures:
    """색상 특징"""
    mean_hsv: Tuple[float, float, float]
    std_hsv: Tuple[float, float, float]
    mean_lab: Tuple[float, float, float]
    dominant_hue: float
    saturation_mean: float
    value_mean: float
    brown_ratio: float  # 갈색 정도 (튀김 익음 정도)
    golden_ratio: float  # 황금색 정도


@dataclass
class SegmentationResult:
    """분할 결과"""
    food_mask: np.ndarray
    food_area_ratio: float  # 전체 대비 음식 영역 비율
    color_features: ColorFeatures
    image_path: str


class FoodSegmenter:
    """음식 영역 분할기"""

    def __init__(self, mode: str = "auto"):
        """
        Args:
            mode: "auto" (자동), "brown" (갈색 음식), "light" (밝은 음식)
        """
        self.mode = mode

        # HSV 임계값 (튀김 음식 - 갈색~황금색 범위)
        # 여러 범위를 사용하여 다양한 색상 포착
        self.food_ranges = {
            "golden": {  # 황금색 (완벽한 튀김)
                "lower": np.array([15, 50, 80]),
                "upper": np.array([35, 255, 255])
            },
            "brown": {  # 갈색 (익은 튀김)
                "lower": np.array([5, 40, 40]),
                "upper": np.array([25, 255, 200])
            },
            "light": {  # 밝은 색 (덜 익은 음식)
                "lower": np.array([20, 30, 120]),
                "upper": np.array([40, 200, 255])
            }
        }

    def segment(self, image: np.ndarray, visualize: bool = False,
                save_path: Optional[str] = None) -> SegmentationResult:
        """
        음식 영역 분할

        Args:
            image: 입력 이미지 (BGR)
            visualize: 시각화 여부
            save_path: 시각화 이미지 저장 경로

        Returns:
            분할 결과
        """
        if image is None or image.size == 0:
            raise ValueError("Invalid image")

        # HSV 변환
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # 여러 색상 범위로 마스크 생성
        masks = []
        for range_name, range_val in self.food_ranges.items():
            mask = cv2.inRange(hsv, range_val["lower"], range_val["upper"])
            masks.append(mask)

        # 모든 마스크 합치기
        food_mask = np.zeros_like(masks[0])
        for mask in masks:
            food_mask = cv2.bitwise_or(food_mask, mask)

        # 노이즈 제거 (morphology)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        food_mask = cv2.morphologyEx(food_mask, cv2.MORPH_CLOSE, kernel)
        food_mask = cv2.morphologyEx(food_mask, cv2.MORPH_OPEN, kernel)

        # 작은 영역 제거 (연결된 컴포넌트)
        food_mask = self._remove_small_regions(food_mask, min_area=500)

        # 색상 특징 추출
        color_features = self._extract_color_features(image, food_mask)

        # 음식 영역 비율
        total_pixels = image.shape[0] * image.shape[1]
        food_pixels = np.sum(food_mask > 0)
        food_area_ratio = food_pixels / total_pixels

        # 시각화
        if visualize or save_path:
            self._visualize_segmentation(image, food_mask, color_features, save_path)

        return SegmentationResult(
            food_mask=food_mask,
            food_area_ratio=food_area_ratio,
            color_features=color_features,
            image_path=""
        )

    def _remove_small_regions(self, mask: np.ndarray, min_area: int = 500) -> np.ndarray:
        """작은 영역 제거"""
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)

        # 배경(0) 제외하고 작은 영역 제거
        cleaned_mask = np.zeros_like(mask)
        for i in range(1, num_labels):
            if stats[i, cv2.CC_STAT_AREA] >= min_area:
                cleaned_mask[labels == i] = 255

        return cleaned_mask

    def _extract_color_features(self, image: np.ndarray, mask: np.ndarray) -> ColorFeatures:
        """색상 특징 추출"""
        # 마스크 영역만 추출
        masked_image = cv2.bitwise_and(image, image, mask=mask)

        # HSV 변환
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        masked_hsv = cv2.bitwise_and(hsv, hsv, mask=mask)

        # LAB 변환 (색 분석에 더 적합)
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        masked_lab = cv2.bitwise_and(lab, lab, mask=mask)

        # 마스크 영역의 픽셀만 추출
        food_pixels_hsv = masked_hsv[mask > 0]
        food_pixels_lab = masked_lab[mask > 0]

        if len(food_pixels_hsv) == 0:
            # 음식이 감지되지 않은 경우
            return ColorFeatures(
                mean_hsv=(0, 0, 0),
                std_hsv=(0, 0, 0),
                mean_lab=(0, 0, 0),
                dominant_hue=0,
                saturation_mean=0,
                value_mean=0,
                brown_ratio=0,
                golden_ratio=0
            )

        # HSV 통계
        mean_hsv = tuple(np.mean(food_pixels_hsv, axis=0).tolist())
        std_hsv = tuple(np.std(food_pixels_hsv, axis=0).tolist())

        # LAB 통계
        mean_lab = tuple(np.mean(food_pixels_lab, axis=0).tolist())

        # 색상(Hue) 히스토그램에서 dominant hue
        hue_hist = cv2.calcHist([masked_hsv], [0], mask, [180], [0, 180])
        dominant_hue = float(np.argmax(hue_hist))

        # 채도와 명도 평균
        saturation_mean = float(np.mean(food_pixels_hsv[:, 1]))
        value_mean = float(np.mean(food_pixels_hsv[:, 2]))

        # 갈색 비율 (Hue 5-25, 튀김 익은 정도)
        brown_pixels = np.sum((food_pixels_hsv[:, 0] >= 5) & (food_pixels_hsv[:, 0] <= 25))
        brown_ratio = float(brown_pixels / len(food_pixels_hsv))

        # 황금색 비율 (Hue 15-35, 완벽한 튀김)
        golden_pixels = np.sum((food_pixels_hsv[:, 0] >= 15) & (food_pixels_hsv[:, 0] <= 35))
        golden_ratio = float(golden_pixels / len(food_pixels_hsv))

        return ColorFeatures(
            mean_hsv=mean_hsv,
            std_hsv=std_hsv,
            mean_lab=mean_lab,
            dominant_hue=dominant_hue,
            saturation_mean=saturation_mean,
            value_mean=value_mean,
            brown_ratio=brown_ratio,
            golden_ratio=golden_ratio
        )

    def _visualize_segmentation(self, image: np.ndarray, mask: np.ndarray,
                                features: ColorFeatures, save_path: Optional[str] = None):
        """분할 결과 시각화"""
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))

        # 원본 이미지
        axes[0, 0].imshow(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        axes[0, 0].set_title('Original Image')
        axes[0, 0].axis('off')

        # 분할 마스크
        axes[0, 1].imshow(mask, cmap='gray')
        axes[0, 1].set_title('Food Mask')
        axes[0, 1].axis('off')

        # 마스크 적용 결과
        masked_result = cv2.bitwise_and(image, image, mask=mask)
        axes[1, 0].imshow(cv2.cvtColor(masked_result, cv2.COLOR_BGR2RGB))
        axes[1, 0].set_title('Segmented Food')
        axes[1, 0].axis('off')

        # 색상 특징 정보
        info_text = f"""Color Features:

HSV Mean: ({features.mean_hsv[0]:.1f}, {features.mean_hsv[1]:.1f}, {features.mean_hsv[2]:.1f})
Dominant Hue: {features.dominant_hue:.1f}°
Saturation: {features.saturation_mean:.1f}
Value: {features.value_mean:.1f}

Brown Ratio: {features.brown_ratio:.2%}
Golden Ratio: {features.golden_ratio:.2%}

LAB Mean: ({features.mean_lab[0]:.1f}, {features.mean_lab[1]:.1f}, {features.mean_lab[2]:.1f})
        """
        axes[1, 1].text(0.1, 0.5, info_text, fontsize=10, family='monospace',
                       verticalalignment='center')
        axes[1, 1].axis('off')
        axes[1, 1].set_title('Feature Summary')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=100, bbox_inches='tight')
            print(f"  💾 Saved visualization: {save_path}")

        plt.close(fig)  # Close to free memory


class DatasetAnalyzer:
    """데이터셋 분석기"""

    def __init__(self, segmenter: FoodSegmenter):
        self.segmenter = segmenter

    def analyze_session(self, session_dir: Path,
                       output_dir: Optional[Path] = None,
                       visualize_samples: int = 5,
                       save_visualizations: bool = True) -> Dict:
        """
        세션 데이터 분석

        Args:
            session_dir: 세션 디렉토리
            output_dir: 결과 저장 디렉토리
            visualize_samples: 시각화할 샘플 수

        Returns:
            분석 결과
        """
        images_dir = session_dir / "images"
        if not images_dir.exists():
            raise ValueError(f"Images directory not found: {images_dir}")

        # 세션 데이터 로드
        session_data_path = session_dir / "session_data.json"
        session_data = None
        if session_data_path.exists():
            with open(session_data_path, 'r') as f:
                session_data = json.load(f)

        # 모든 이미지 분석
        image_files = sorted(images_dir.glob("*.jpg"))
        results = []

        # 시각화 출력 디렉토리
        vis_dir = None
        if save_visualizations and output_dir:
            vis_dir = output_dir / "visualizations" / session_dir.name
            vis_dir.mkdir(exist_ok=True, parents=True)

        print(f"\n🔍 Analyzing {len(image_files)} images from {session_dir.name}...")

        for i, img_path in enumerate(image_files):
            image = cv2.imread(str(img_path))
            if image is None:
                continue

            # 시각화 저장 경로 (샘플만)
            save_path = None
            if save_visualizations and vis_dir and i < visualize_samples:
                save_path = str(vis_dir / f"vis_{img_path.stem}.jpg")

            # 분할 수행
            result = self.segmenter.segment(image, visualize=(i < visualize_samples),
                                           save_path=save_path)
            result.image_path = str(img_path.relative_to(session_dir.parent))
            results.append(result)

            if (i + 1) % 10 == 0:
                print(f"  Processed {i + 1}/{len(image_files)} images...")

        # 결과 저장
        if output_dir:
            output_dir.mkdir(exist_ok=True, parents=True)
            self._save_analysis_results(session_dir, results, output_dir, session_data)

        # 통계 출력
        self._print_statistics(results)

        return {
            'session_id': session_dir.name,
            'total_images': len(results),
            'results': [asdict(r) for r in results]
        }

    def _save_analysis_results(self, session_dir: Path, results: List[SegmentationResult],
                               output_dir: Path, session_data: Optional[Dict]):
        """분석 결과 저장"""
        # JSON으로 저장
        output_file = output_dir / f"{session_dir.name}_analysis.json"

        analysis_data = {
            'session_id': session_dir.name,
            'total_images': len(results),
            'session_data': session_data,
            'results': []
        }

        for result in results:
            analysis_data['results'].append({
                'image_path': result.image_path,
                'food_area_ratio': result.food_area_ratio,
                'color_features': asdict(result.color_features)
            })

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(analysis_data, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Analysis saved: {output_file}")

        # CSV로도 저장 (시계열 분석용)
        csv_file = output_dir / f"{session_dir.name}_features.csv"
        with open(csv_file, 'w') as f:
            f.write("image_path,food_area_ratio,hue_mean,saturation_mean,value_mean,"
                   "brown_ratio,golden_ratio,lab_l,lab_a,lab_b\n")
            for result in results:
                feat = result.color_features
                f.write(f"{result.image_path},"
                       f"{result.food_area_ratio:.4f},"
                       f"{feat.mean_hsv[0]:.2f},"
                       f"{feat.saturation_mean:.2f},"
                       f"{feat.value_mean:.2f},"
                       f"{feat.brown_ratio:.4f},"
                       f"{feat.golden_ratio:.4f},"
                       f"{feat.mean_lab[0]:.2f},"
                       f"{feat.mean_lab[1]:.2f},"
                       f"{feat.mean_lab[2]:.2f}\n")

        print(f"💾 Features CSV saved: {csv_file}")

    def _print_statistics(self, results: List[SegmentationResult]):
        """통계 출력"""
        if not results:
            return

        food_areas = [r.food_area_ratio for r in results]
        brown_ratios = [r.color_features.brown_ratio for r in results]
        golden_ratios = [r.color_features.golden_ratio for r in results]
        hue_means = [r.color_features.mean_hsv[0] for r in results]

        print("\n" + "=" * 60)
        print("📊 Segmentation Statistics")
        print("=" * 60)
        print(f"Total images: {len(results)}")
        print(f"\nFood area ratio:")
        print(f"  Mean: {np.mean(food_areas):.2%}")
        print(f"  Std:  {np.std(food_areas):.2%}")
        print(f"  Min:  {np.min(food_areas):.2%}")
        print(f"  Max:  {np.max(food_areas):.2%}")
        print(f"\nColor progression:")
        print(f"  Brown ratio:  {np.mean(brown_ratios):.2%} ± {np.std(brown_ratios):.2%}")
        print(f"  Golden ratio: {np.mean(golden_ratios):.2%} ± {np.std(golden_ratios):.2%}")
        print(f"  Mean hue:     {np.mean(hue_means):.1f}° ± {np.std(hue_means):.1f}°")
        print("=" * 60)


def analyze_existing_data(base_dir: str = "frying_dataset"):
    """기존 수집 데이터 분석"""
    base_path = Path(base_dir)

    if not base_path.exists():
        print(f"❌ Dataset directory not found: {base_dir}")
        return

    # 세션 디렉토리 찾기
    sessions = [d for d in base_path.iterdir()
                if d.is_dir() and (d / "images").exists()]

    if not sessions:
        print(f"❌ No sessions found in {base_dir}")
        return

    print(f"\n📁 Found {len(sessions)} sessions:")
    for i, session in enumerate(sessions, 1):
        img_count = len(list((session / "images").glob("*.jpg")))
        print(f"  {i}. {session.name} ({img_count} images)")

    # 분석할 세션 선택
    print("\n" + "=" * 60)
    choice = input("Analyze which session? (number or 'all'): ").strip().lower()

    # Segmenter 초기화
    segmenter = FoodSegmenter(mode="auto")
    analyzer = DatasetAnalyzer(segmenter)

    # 출력 디렉토리
    output_dir = base_path / "analysis_results"

    if choice == 'all':
        for session in sessions:
            analyzer.analyze_session(session, output_dir, visualize_samples=2)
    else:
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(sessions):
                analyzer.analyze_session(sessions[idx], output_dir, visualize_samples=3)
            else:
                print("❌ Invalid choice")
        except ValueError:
            print("❌ Invalid input")


def test_single_image(image_path: str):
    """단일 이미지 테스트"""
    image = cv2.imread(image_path)
    if image is None:
        print(f"❌ Failed to load image: {image_path}")
        return

    segmenter = FoodSegmenter(mode="auto")
    result = segmenter.segment(image, visualize=True)

    print(f"\n✅ Segmentation complete:")
    print(f"   Food area: {result.food_area_ratio:.2%}")
    print(f"   Brown ratio: {result.color_features.brown_ratio:.2%}")
    print(f"   Golden ratio: {result.color_features.golden_ratio:.2%}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "test" and len(sys.argv) > 2:
            # 단일 이미지 테스트
            test_single_image(sys.argv[2])
        else:
            # 특정 디렉토리 분석
            analyze_existing_data(sys.argv[1])
    else:
        # 기본 디렉토리 분석
        analyze_existing_data()
