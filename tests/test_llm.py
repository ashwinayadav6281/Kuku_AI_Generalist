"""
tests/test_llm.py - Unit tests for LLM client, caching, and schema validation.
"""

import sys
import os
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm import (
    call_llm,
    extract_json,
    validate_json,
    reset_usage_stats,
    get_usage_stats,
)


def test_extract_json_clean():
    raw = '{"name": "test", "val": 123}'
    assert extract_json(raw) == raw


def test_extract_json_markdown_fences():
    raw = '```json\n{"name": "test", "val": 123}\n```'
    assert extract_json(raw) == '{"name": "test", "val": 123}'


def test_extract_json_surrounding_text():
    raw = 'Here is the result:\n```json\n{"key": "value"}\n```\nHope that helps!'
    assert extract_json(raw) == '{"key": "value"}'


def test_validate_json_valid_schema():
    schema = {"required": ["title", "genre"]}
    res = validate_json('{"title": "Show A", "genre": "Drama"}', schema)
    assert res["title"] == "Show A"
    assert res["genre"] == "Drama"


def test_validate_json_missing_field():
    schema = {"required": ["title", "secret"]}
    try:
        validate_json('{"title": "Show A"}', schema)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Missing required fields" in str(e)


def test_mock_llm_call_and_caching(tmp_path):
    os.environ["LLM_PROVIDER"] = "mock"
    reset_usage_stats()

    import uuid
    unique_id = str(uuid.uuid4())
    test_prompt = f"Unique prompt {unique_id}: Generate test show premise"
    schema = {"required": ["title", "premise"]}

    # Call 1: cold call (generates response)
    res1 = call_llm(test_prompt, schema=schema, tier="strong")
    assert "title" in res1
    assert "premise" in res1
    stats1 = get_usage_stats()
    assert stats1["total_calls"] == 1
    assert stats1["cache_hits"] == 0

    # Call 2: cache hit
    res2 = call_llm(test_prompt, schema=schema, tier="strong")
    assert res2 == res1
    stats2 = get_usage_stats()
    assert stats2["total_calls"] == 2
    assert stats2["cache_hits"] == 1
