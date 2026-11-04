"""
tests/test_judge_and_rank.py - Unit tests for LLM judge, ranking, and output formats.
"""

import sys
import os
import json
import csv
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from judge_and_rank import (
    run_judging_and_ranking,
    rank_and_dedupe_promos,
    JudgedPromo,
)


def test_end_to_end_judging_and_ranking(tmp_path):
    os.environ["LLM_PROVIDER"] = "mock"
    os.environ["LLM_OFFLINE_FALLBACK"] = "1"

    out_dir = tmp_path / "test_out"
    ranked = run_judging_and_ranking(out_dir=str(out_dir))

    assert len(ranked) == 10, "Should output top 10 ranked promos"

    # Verify rank sequence
    ranks = [p.rank for p in ranked]
    assert ranks == list(range(1, 11))

    # Verify duration bounds
    for p in ranked:
        assert 20.0 <= p.total_duration <= 60.0

    # Verify diversity (max 2 per episode)
    ep_counts = {}
    for p in ranked:
        ep_counts[p.primary_episode_id] = ep_counts.get(p.primary_episode_id, 0) + 1
        assert ep_counts[p.primary_episode_id] <= 2

    # Verify output files generated
    assert (out_dir / "promos.json").exists()
    assert (out_dir / "promos.csv").exists()
    assert (out_dir / "report.md").exists()
    assert (out_dir / "run_log.json").exists()

    # Verify CSV format
    with open(out_dir / "promos.csv", "r", encoding="utf-8") as f:
        reader = list(csv.reader(f))
        assert len(reader) == 11  # 1 header + 10 rows
