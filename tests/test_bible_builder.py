"""
tests/test_bible_builder.py - Verify Bible building logic and schema validation.
"""

import sys
import os
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bible_builder import build_bible, BIBLE_SCHEMA


def test_build_bible_structure(tmp_path):
    os.environ["LLM_PROVIDER"] = "mock"
    os.environ["LLM_OFFLINE_FALLBACK"] = "1"
    
    out_file = tmp_path / "test_bible.json"
    bible = build_bible(meta_path="output/episode_meta.json", out_path=str(out_file))

    assert out_file.exists()
    for req in BIBLE_SCHEMA["required"]:
        assert req in bible, f"Missing required bible key: {req}"

    assert len(bible["main_characters"]) >= 3
    assert len(bible["central_twists"]) >= 3
    assert isinstance(bible["central_twists"][0]["episode"], int)
