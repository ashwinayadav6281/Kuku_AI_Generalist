"""
tests/test_quality_checks.py - Unit tests for quality checks, gold evaluation, and failure analysis.
"""

import sys
import os
import json
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from checks import run_checks
from evaluate import compute_iou, evaluate_gold_set


def test_iou_calculation():
    # Exact overlap
    assert compute_iou(10.0, 30.0, 10.0, 30.0)[0] == 1.0
    # No overlap
    assert compute_iou(0.0, 10.0, 20.0, 30.0)[0] == 0.0
    # Partial overlap
    iou, overlap = compute_iou(0.0, 30.0, 15.0, 45.0)
    assert iou == 0.333  # 15s intersection / 45s union
    assert overlap == 15.0


def test_checks_detects_invalid_duration(tmp_path):
    bad_promos = [
        {
            "rank": 1,
            "promo_id": "bad_01",
            "primary_episode_id": 1,
            "segments": [{"episode": 1, "start": 0.0, "end": 10.0}],
            "total_duration": 10.0,  # Below 20s
            "hook_text": "Hook",
            "cliffhanger_text": "Cliff",
            "weighted_score": 4.0,
            "hook_strength": 4,
            "cliffhanger_quality": 4,
            "standalone_clarity": 4,
            "emotional_pull": 4,
            "why_it_works": "Test",
        }
    ]
    p_file = tmp_path / "bad_promos.json"
    with open(p_file, "w", encoding="utf-8") as f:
        json.dump(bad_promos, f)

    report = run_checks(str(p_file), "output/parsed_units.json")
    assert report["pass_rate_percent"] == 0.0
    assert any("Duration" in f for f in report["failures"])


def test_checks_detects_hallucinated_timestamp(tmp_path):
    bad_promos = [
        {
            "rank": 1,
            "promo_id": "hallucinated_01",
            "primary_episode_id": 1,
            "segments": [{"episode": 1, "start": 999.99, "end": 1025.00}],  # Does not exist
            "total_duration": 25.01,
            "hook_text": "Hook",
            "cliffhanger_text": "Cliff",
            "weighted_score": 4.0,
            "hook_strength": 4,
            "cliffhanger_quality": 4,
            "standalone_clarity": 4,
            "emotional_pull": 4,
            "why_it_works": "Test",
        }
    ]
    p_file = tmp_path / "hallucinated_promos.json"
    with open(p_file, "w", encoding="utf-8") as f:
        json.dump(bad_promos, f)

    report = run_checks(str(p_file), "output/parsed_units.json")
    assert report["pass_rate_percent"] == 0.0
    assert any("does not match any parsed unit" in f for f in report["failures"])


def test_gold_evaluation_pipeline():
    report = evaluate_gold_set("gold_template.csv", "output/promos.json", "output/candidates.json")
    assert report["gold_picks_count"] == 5
    assert report["recall_in_candidate_pool_percent"] == 100.0
    assert report["recall_in_top_10_percent"] >= 60.0
    assert report["mean_iou_of_matches"] >= 0.50
