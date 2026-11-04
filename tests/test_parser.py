"""
tests/test_parser.py – Unit tests for the screenplay parser.
"""
import sys
import os
import tempfile
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from screenplay_parser import (
    ts_to_seconds, seconds_to_ts, _classify_unit_header,
    parse_episode, validate_episode, ParseError
)


# ── Timestamp conversion ─────────────────────────────────────────────────────

def test_ts_to_seconds_basic():
    assert ts_to_seconds("00:00.00") == 0.0
    assert ts_to_seconds("01:30.50") == 90.5
    assert ts_to_seconds("02:18.00") == 138.0
    assert ts_to_seconds("00:04.80") == 4.8

def test_ts_to_seconds_from_parens():
    """Should handle timestamp embedded in parentheses."""
    assert ts_to_seconds("(01:03.40)") == 63.4

def test_seconds_to_ts():
    assert seconds_to_ts(0.0) == "00:00.00"
    assert seconds_to_ts(90.5) == "01:30.50"
    assert seconds_to_ts(138.0) == "02:18.00"

def test_ts_roundtrip():
    for val in [0.0, 4.8, 63.4, 90.5, 138.0, 170.5]:
        assert abs(ts_to_seconds(seconds_to_ts(val)) - val) < 0.01


# ── Unit-type classification ─────────────────────────────────────────────────

def test_classify_camera():
    assert _classify_unit_header("CAMERA") == ("camera", None, None)

def test_classify_action():
    assert _classify_unit_header("ACTION") == ("action", None, None)

def test_classify_sound_fx():
    assert _classify_unit_header("SOUND FX") == ("sound_fx", None, None)

def test_classify_dialogue_simple():
    t, s, d = _classify_unit_header("LADY JULIANA (Confused, Breathless)")
    assert t == "dialogue"
    assert s == "LADY JULIANA"
    assert d == "Confused, Breathless"

def test_classify_dialogue_os():
    t, s, d = _classify_unit_header("LORD ASHCROFT (O.S. / Continues)")
    assert t == "dialogue"
    assert s == "LORD ASHCROFT"
    assert d == "O.S. / Continues"

def test_classify_dialogue_multiple_parens():
    t, s, d = _classify_unit_header("MATRIARCH (O.S.) (Firm)")
    assert t == "dialogue"
    assert s == "MATRIARCH"
    assert d == "O.S., Firm"

def test_classify_dialogue_no_direction():
    """Some dialogue headers might have no parenthetical."""
    t, s, d = _classify_unit_header("ALEXANDER")
    assert t == "dialogue"
    assert s == "ALEXANDER"
    assert d is None


# ── Full episode parse ────────────────────────────────────────────────────────

MINI_EPISODE = """EPISODE NUMBER: Episode 99
EPISODE LOGLINE: Test episode.
CONTINUITY NOTES: None.

--- SCRIPT START ---

SCENE 01
Scene heading: INT. ROOM – DAY
Scene start: 00:00.00
Scene end: 00:30.00

Actions and dialogue:

**CAMERA:**
Start: (00:00.00) | End: (00:03.50)
Wide shot of the room.

**ALICE (Angry):**
Start: (00:03.50) | End: (00:06.00)
"How dare you!"

**ACTION:**
Start: (00:06.00) | End: (00:08.00)
Bob stumbles backward.

**BOB (Shocked):**
Start: (00:08.00) | End: (00:10.00)
"I didn't mean to."

**SOUND FX:**
Start: (00:10.00) | End: (00:11.00)
A door slams.

SCENE 02
Scene heading: EXT. GARDEN – DAY
Scene start: 00:11.00
Scene end: 00:30.00

Actions and dialogue:

**CAMERA:**
Start: (00:11.00) | End: (00:13.00)
Wide shot of the garden.

**ALICE (Crying):**
Start: (00:13.00) | End: (00:16.00)
"You ruined everything."

--- SCRIPT END ---
"""


def test_parse_mini_episode():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False,
                                      encoding="utf-8") as f:
        f.write(MINI_EPISODE)
        f.flush()
        meta, units, warnings = parse_episode(f.name)

    assert meta.episode_id == 99
    assert meta.scene_count == 2
    assert meta.unit_count == 7
    assert meta.duration == 16.0  # last unit ends at 16.0

    # Check unit types
    types = [u.unit_type for u in units]
    assert types == ["camera", "dialogue", "action", "dialogue", "sound_fx",
                     "camera", "dialogue"]

    # Check speakers
    assert units[1].speaker == "ALICE"
    assert units[3].speaker == "BOB"
    assert units[6].speaker == "ALICE"

    # Check scene assignment
    assert units[0].scene_id == 1
    assert units[5].scene_id == 2
    assert units[6].scene_id == 2

    # Validate
    errors, val_warnings = validate_episode(meta, units)
    assert len(errors) == 0

    os.unlink(f.name)


def test_parse_bad_format():
    bad = "This is not a screenplay.\nJust random text.\n"
    tmp_path = None
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False,
                                      encoding="utf-8") as f:
        tmp_path = f.name
        f.write(bad)
    try:
        parse_episode(tmp_path)
        assert False, "Should have raised ParseError"
    except ParseError as e:
        assert "EPISODE NUMBER" in str(e)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_validate_negative_duration():
    """Manually create a unit with end < start to test validation."""
    from screenplay_parser import ParsedUnit, EpisodeMeta
    bad_unit = ParsedUnit(
        episode_id=1, scene_id=1, scene_heading="X", scene_start=0,
        scene_end=10, unit_index=0, unit_type="dialogue", speaker="A",
        direction=None, text="Hi", start=5.0, end=3.0
    )
    meta = EpisodeMeta(
        episode_id=1, filename="test.txt", logline="", continuity_notes="",
        scene_count=1, unit_count=1, duration=5.0, scenes=[]
    )
    errors, warnings = validate_episode(meta, [bad_unit])
    assert any("Negative duration" in e for e in errors)


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
