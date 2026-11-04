"""
tests/test_candidate_generator.py - Verify candidate window constraints and timestamp authenticity.
"""

import sys
import os
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from candidate_generator import (
    generate_raw_windows,
    score_and_filter_candidates,
    CandidateWindow,
)
from screenplay_parser import ParsedUnit


def test_candidate_boundaries_and_duration():
    # Load parsed units
    with open("output/parsed_units.json", "r", encoding="utf-8") as f:
        parsed_dict = json.load(f)

    ep1_units = [ParsedUnit(**u) for u in parsed_dict["1"]]
    windows = generate_raw_windows(ep1_units, min_dur=20.0, max_dur=60.0)

    assert len(windows) > 0, "Should generate candidate windows for Episode 1"

    for w in windows:
        # Strictly verify duration
        assert 20.0 <= w.duration <= 60.0, f"Duration {w.duration} outside 20-60s range"
        # Strictly verify that start_time matches unit start
        assert w.start_time == ep1_units[w.start_unit_index].start
        # Strictly verify that end_time matches unit end
        assert w.end_time == ep1_units[w.end_unit_index].end
        # Verify timestamps are chronological
        assert w.end_time > w.start_time


def test_top_n_filtering():
    with open("output/parsed_units.json", "r", encoding="utf-8") as f:
        parsed_dict = json.load(f)

    ep1_units = [ParsedUnit(**u) for u in parsed_dict["1"]]
    windows = generate_raw_windows(ep1_units, min_dur=20.0, max_dur=60.0)
    top_candidates = score_and_filter_candidates(windows, top_n_per_ep=8)

    assert len(top_candidates) <= 8
    # Ensure they are sorted by candidate_score descending
    scores = [c.candidate_score for c in top_candidates]
    assert scores == sorted(scores, reverse=True)
