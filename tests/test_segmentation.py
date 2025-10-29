#!/usr/bin/env python3
"""Quick test of food segmentation on potato data"""

from pathlib import Path
from frying_ai.food_segmentation import FoodSegmenter, DatasetAnalyzer

# Find the potato session
base_dir = Path("frying_dataset")
sessions = [d for d in base_dir.iterdir() if d.is_dir() and (d / "images").exists()]

if not sessions:
    print("No sessions found!")
    exit(1)

# Analyze first session
session = sessions[0]
print(f"Analyzing: {session.name}")

segmenter = FoodSegmenter(mode="auto")
analyzer = DatasetAnalyzer(segmenter)

output_dir = base_dir / "analysis_results"
analyzer.analyze_session(session, output_dir, visualize_samples=5, save_visualizations=True)

print("\n✅ Done! Check frying_dataset/analysis_results/ for results")
