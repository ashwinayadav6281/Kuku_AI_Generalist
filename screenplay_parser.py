"""
parser.py – Convert microdrama screenplays into structured units.

Reads .txt screenplay files with the Kuku microdrama format and outputs
a list of ParsedUnit dicts per episode.

Format expected (per file):
    EPISODE NUMBER: Episode <N>
    EPISODE LOGLINE: ...
    CONTINUITY NOTES: ...
    --- SCRIPT START ---
    SCENE <NN>
    Scene heading: <heading>
    Scene start: <MM:SS.ff>
    Scene end: <MM:SS.ff>
    Actions and dialogue:
    **<TYPE> (<direction>):**       # TYPE = CAMERA | ACTION | DIALOGUE name | SOUND FX
    Start: (<MM:SS.ff>) | End: (<MM:SS.ff>)
    <text>
    --- SCRIPT END ---
"""

import re
import json
import sys
import os
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict, Any


# ── Timestamp helpers ─────────────────────────────────────────────────────────

_TS_RE = re.compile(r"(\d{1,2}):(\d{2})\.(\d{2})")

def ts_to_seconds(ts: str) -> float:
    """Convert 'MM:SS.ff' to seconds (float, 2-decimal precision)."""
    m = _TS_RE.search(ts)
    if not m:
        raise ValueError(f"Cannot parse timestamp: '{ts}'")
    mins, secs, hundredths = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return round(mins * 60 + secs + hundredths / 100, 2)

def seconds_to_ts(s: float) -> str:
    """Convert seconds back to 'MM:SS.ff'."""
    mins = int(s) // 60
    secs = s - mins * 60
    return f"{mins:02d}:{secs:05.2f}"


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class ParsedUnit:
    episode_id: int
    scene_id: int
    scene_heading: str
    scene_start: float        # seconds
    scene_end: float          # seconds
    unit_index: int           # global index within episode (0-based)
    unit_type: str            # dialogue | action | camera | sound_fx
    speaker: Optional[str]    # for dialogue; None for others
    direction: Optional[str]  # parenthetical direction e.g. "Cold, Commanding"
    text: str
    start: float              # seconds
    end: float                # seconds

    def duration(self) -> float:
        return round(self.end - self.start, 2)


@dataclass
class EpisodeMeta:
    episode_id: int
    filename: str
    logline: str
    continuity_notes: str
    scene_count: int
    unit_count: int
    duration: float           # seconds (from last unit end)
    scenes: List[Dict[str, Any]]  # [{scene_id, heading, start, end}]


@dataclass
class ParseReport:
    total_episodes: int
    total_units: int
    episodes: List[Dict[str, Any]]  # per-episode summary
    warnings: List[str]
    errors: List[str]


# ── Unit-type classification ──────────────────────────────────────────────────

# Matches the **LABEL:** header line
_UNIT_HEADER_RE = re.compile(
    r"^\*\*(.+?):\*\*\s*$"
)

# Known non-dialogue prefixes
# Ordered longest-first so "SOUND FX" matches before "SOUND"
_NON_DIALOGUE_TYPES = ["SOUND FX", "VISUAL FX", "CAMERA", "ACTION", "SFX", "MUSIC", "SOUND"]

# Timestamp line inside a unit block
_TS_LINE_RE = re.compile(
    r"^Start:\s*\(([^)]+)\)\s*\|\s*End:\s*\(([^)]+)\)"
)


def _classify_unit_header(raw_label: str):
    """
    Return (unit_type, speaker, direction) from the raw label between ** **.

    Examples:
        "CAMERA"                              -> ("camera", None, None)
        "ACTION"                              -> ("action", None, None)
        "SOUND FX"                            -> ("sound_fx", None, None)
        "LADY JULIANA (Confused, Breathless)"  -> ("dialogue", "LADY JULIANA", "Confused, Breathless")
        "MATRIARCH (O.S.) (Firm)"             -> ("dialogue", "MATRIARCH", "O.S., Firm")
        "LORD ASHCROFT (O.S. / Continues)"    -> ("dialogue", "LORD ASHCROFT", "O.S. / Continues")
    """
    raw = raw_label.strip()

    # Strip trailing colon if present (shouldn't be with our regex, but safety)
    if raw.endswith(":"):
        raw = raw[:-1].strip()

    # Check for non-dialogue types
    upper = raw.upper()
    for ndt in _NON_DIALOGUE_TYPES:
        if upper == ndt or upper.startswith(ndt + " "):
            return (ndt.lower().replace(" ", "_"), None, None)

    # It's dialogue – split name from direction(s)
    # Pattern: NAME (dir1) (dir2) ...  or  NAME (dir1, dir2)
    paren_parts = []
    name_part = raw
    while True:
        m = re.search(r"\(([^)]*)\)\s*$", name_part)
        if not m:
            break
        paren_parts.insert(0, m.group(1).strip())
        name_part = name_part[:m.start()].strip()

    speaker = name_part.strip()
    direction = ", ".join(paren_parts) if paren_parts else None

    return ("dialogue", speaker, direction)


# ── Main parser ───────────────────────────────────────────────────────────────

class ParseError(Exception):
    """Raised when the screenplay format is unrecognised."""
    pass


def parse_episode(filepath: str) -> tuple:
    """
    Parse one episode file.

    Returns:
        (EpisodeMeta, List[ParsedUnit], List[str] warnings)

    Raises ParseError on unrecognised format.
    """
    path = Path(filepath)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    warnings = []

    # ── Header ──────────────────────────────────────────────────────
    ep_match = re.search(r"EPISODE\s+NUMBER:\s*Episode\s+(\d+)", lines[0] if lines else "")
    if not ep_match:
        raise ParseError(
            f"File '{path.name}': Cannot find 'EPISODE NUMBER: Episode <N>' on line 1. "
            f"Got: '{lines[0][:80] if lines else '(empty)'}'"
        )
    episode_id = int(ep_match.group(1))

    logline = ""
    continuity = ""
    for line in lines[:10]:
        if line.startswith("EPISODE LOGLINE:"):
            logline = line.split(":", 1)[1].strip()
        elif line.startswith("CONTINUITY NOTES:"):
            continuity = line.split(":", 1)[1].strip()

    # Verify script markers
    script_start_idx = None
    script_end_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "--- SCRIPT START ---":
            script_start_idx = i
        elif stripped == "--- SCRIPT END ---":
            script_end_idx = i
    if script_start_idx is None:
        raise ParseError(f"File '{path.name}': Missing '--- SCRIPT START ---' marker.")
    if script_end_idx is None:
        raise ParseError(f"File '{path.name}': Missing '--- SCRIPT END ---' marker.")

    # ── Parse scenes and units ──────────────────────────────────────
    script_lines = lines[script_start_idx + 1 : script_end_idx]

    units: List[ParsedUnit] = []
    scenes: List[Dict[str, Any]] = []
    unit_index = 0

    current_scene_id = None
    current_scene_heading = ""
    current_scene_start = 0.0
    current_scene_end = 0.0

    i = 0
    while i < len(script_lines):
        line = script_lines[i].strip()

        # Scene header: "SCENE 01" or "SCENE 1"
        scene_match = re.match(r"^SCENE\s+(\d+)\s*$", line)
        if scene_match:
            current_scene_id = int(scene_match.group(1))
            # Next lines: Scene heading, Scene start, Scene end
            i += 1
            # Parse scene metadata
            while i < len(script_lines):
                sl = script_lines[i].strip()
                sl_lower = sl.lower()
                if sl_lower.startswith("scene heading:"):
                    current_scene_heading = sl.split(":", 1)[1].strip()
                elif sl_lower.startswith("scene start:"):
                    current_scene_start = ts_to_seconds(sl.split(":", 1)[1].strip())
                elif sl_lower.startswith("scene end:"):
                    current_scene_end = ts_to_seconds(sl.split(":", 1)[1].strip())
                elif sl_lower == "actions and dialogue:":
                    i += 1
                    break
                elif sl == "" or sl.startswith("SCENE ") or re.match(r"^SCENE\s+\d+", sl):
                    break  # no "Actions and dialogue:" line; back up
                else:
                    warnings.append(
                        f"Ep{episode_id} Scene{current_scene_id}: Unexpected scene-header line: '{sl[:60]}'"
                    )
                i += 1

            scenes.append({
                "scene_id": current_scene_id,
                "heading": current_scene_heading,
                "start": current_scene_start,
                "end": current_scene_end,
            })
            continue

        # Unit header: **SOMETHING:**
        header_match = _UNIT_HEADER_RE.match(line)
        if header_match:
            raw_label = header_match.group(1)
            unit_type, speaker, direction = _classify_unit_header(raw_label)

            # Next line should be Start/End timestamps
            i += 1
            if i >= len(script_lines):
                warnings.append(f"Ep{episode_id} unit after '{raw_label}': EOF before timestamps")
                break

            ts_match = _TS_LINE_RE.match(script_lines[i].strip())
            if not ts_match:
                raise ParseError(
                    f"File '{path.name}' Ep{episode_id}: Expected 'Start: (...) | End: (...)' "
                    f"after unit header '{raw_label}', got: '{script_lines[i].strip()[:80]}'"
                )
            start_s = ts_to_seconds(ts_match.group(1))
            end_s = ts_to_seconds(ts_match.group(2))

            # Next line(s) = text content (until next blank line or next unit header)
            i += 1
            text_lines = []
            while i < len(script_lines):
                tl = script_lines[i].strip()
                if tl == "" or _UNIT_HEADER_RE.match(tl) or re.match(r"^SCENE\s+\d+", tl):
                    break
                text_lines.append(tl)
                i += 1

            text = " ".join(text_lines)

            if current_scene_id is None:
                raise ParseError(
                    f"File '{path.name}': Found unit '{raw_label}' before any SCENE header."
                )

            units.append(ParsedUnit(
                episode_id=episode_id,
                scene_id=current_scene_id,
                scene_heading=current_scene_heading,
                scene_start=current_scene_start,
                scene_end=current_scene_end,
                unit_index=unit_index,
                unit_type=unit_type,
                speaker=speaker,
                direction=direction,
                text=text,
                start=start_s,
                end=end_s,
            ))
            unit_index += 1
            continue

        # Skip blank lines and "Actions and dialogue:" if encountered again
        if line == "" or line.lower() == "actions and dialogue:":
            i += 1
            continue

        # Unknown line
        warnings.append(f"Ep{episode_id}: Ignoring unrecognised line: '{line[:80]}'")
        i += 1

    meta = EpisodeMeta(
        episode_id=episode_id,
        filename=path.name,
        logline=logline,
        continuity_notes=continuity,
        scene_count=len(scenes),
        unit_count=len(units),
        duration=max((u.end for u in units), default=0.0),
        scenes=scenes,
    )

    return meta, units, warnings


# ── Validation ────────────────────────────────────────────────────────────────

def validate_episode(meta: EpisodeMeta, units: List[ParsedUnit]) -> tuple:
    """
    Run validation checks on a parsed episode.

    Returns:
        (errors: List[str], warnings: List[str])
    """
    errors = []
    warnings = []
    ep = meta.episode_id

    if not units:
        errors.append(f"Ep{ep}: No units parsed.")
        return errors, warnings

    # 1. No negative durations
    for u in units:
        if u.end < u.start:
            errors.append(
                f"Ep{ep} unit{u.unit_index} ({u.unit_type}): "
                f"Negative duration: start={u.start}s end={u.end}s"
            )

    # 2. Timestamps roughly monotonic (within a scene)
    #    We allow overlapping units (camera + action happen simultaneously)
    #    but the START of units should generally not go backwards significantly.
    prev_start_by_scene: Dict[int, float] = {}
    for u in units:
        prev = prev_start_by_scene.get(u.scene_id, -1.0)
        if u.start < prev - 1.0:  # 1s tolerance for overlapping cuts
            warnings.append(
                f"Ep{ep} scene{u.scene_id} unit{u.unit_index}: "
                f"Start {u.start}s is before previous unit start {prev}s"
            )
        prev_start_by_scene[u.scene_id] = u.start

    # 3. Episode duration plausible (microdrama: ~45s to ~180s)
    if meta.duration < 30:
        warnings.append(f"Ep{ep}: Duration {meta.duration:.1f}s seems very short.")
    if meta.duration > 240:
        warnings.append(f"Ep{ep}: Duration {meta.duration:.1f}s seems very long for microdrama.")

    # 4. Unit counts reasonable
    if meta.unit_count < 5:
        warnings.append(f"Ep{ep}: Only {meta.unit_count} units parsed, seems low.")

    return errors, warnings


# ── Batch parsing ─────────────────────────────────────────────────────────────

def parse_folder(folder_path: str) -> tuple:
    """
    Parse all episode .txt files in a folder.

    Returns:
        (all_metas: List[EpisodeMeta],
         all_units: Dict[int, List[ParsedUnit]],  # keyed by episode_id
         report: ParseReport)
    """
    folder = Path(folder_path)
    if not folder.is_dir():
        raise FileNotFoundError(f"Input folder not found: {folder_path}")

    txt_files = sorted(folder.glob("episode-*.txt"))
    if not txt_files:
        # Try one level deeper
        txt_files = sorted(folder.rglob("episode-*.txt"))
    if not txt_files:
        raise ParseError(
            f"No 'episode-*.txt' files found in '{folder_path}'. "
            f"Expected files like 'episode-001-Episode 1671703.txt'."
        )

    all_metas = []
    all_units = {}
    report_episodes = []
    all_warnings = []
    all_errors = []

    for fp in txt_files:
        try:
            meta, units, parse_warnings = parse_episode(str(fp))
            val_errors, val_warnings = validate_episode(meta, units)

            all_metas.append(meta)
            all_units[meta.episode_id] = units
            all_warnings.extend(parse_warnings)
            all_warnings.extend(val_warnings)
            all_errors.extend(val_errors)

            # Count unit types
            type_counts = {}
            for u in units:
                type_counts[u.unit_type] = type_counts.get(u.unit_type, 0) + 1

            report_episodes.append({
                "episode_id": meta.episode_id,
                "filename": meta.filename,
                "scenes": meta.scene_count,
                "units": meta.unit_count,
                "duration_s": round(meta.duration, 2),
                "unit_types": type_counts,
                "parse_warnings": len(parse_warnings),
                "val_errors": len(val_errors),
                "val_warnings": len(val_warnings),
            })

        except (ParseError, ValueError) as e:
            all_errors.append(f"FATAL: {e}")
            report_episodes.append({
                "episode_id": fp.name,
                "error": str(e),
            })

    report = ParseReport(
        total_episodes=len(all_metas),
        total_units=sum(m.unit_count for m in all_metas),
        episodes=report_episodes,
        warnings=all_warnings,
        errors=all_errors,
    )

    return all_metas, all_units, report


# ── CLI entrypoint ────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Parse microdrama screenplays")
    parser.add_argument("--input", required=True, help="Folder containing episode .txt files")
    parser.add_argument("--out", default="output", help="Output folder for parse results")
    args = parser.parse_args()

    print(f"Parsing episodes from: {args.input}")
    metas, units_by_ep, report = parse_folder(args.input)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save parse report
    report_path = out_dir / "parse_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_episodes": report.total_episodes,
            "total_units": report.total_units,
            "episodes": report.episodes,
            "warnings": report.warnings,
            "errors": report.errors,
        }, f, indent=2)

    # Save parsed units (all episodes)
    parsed_path = out_dir / "parsed_units.json"
    all_unit_dicts = {}
    for ep_id, ep_units in sorted(units_by_ep.items()):
        all_unit_dicts[str(ep_id)] = [asdict(u) for u in ep_units]
    with open(parsed_path, "w", encoding="utf-8") as f:
        json.dump(all_unit_dicts, f, indent=2)

    # Save episode metadata
    meta_path = out_dir / "episode_meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump([asdict(m) for m in metas], f, indent=2)

    # Print summary
    print(f"\n{'='*60}")
    print(f"PARSE REPORT")
    print(f"{'='*60}")
    print(f"Episodes parsed: {report.total_episodes}")
    print(f"Total units:     {report.total_units}")
    print(f"Errors:          {len(report.errors)}")
    print(f"Warnings:        {len(report.warnings)}")
    print()

    for ep in report.episodes:
        if "error" in ep:
            print(f"  [FAIL] {ep['episode_id']}: {ep['error']}")
        else:
            status = "OK" if ep['val_errors'] == 0 else "FAIL"
            print(f"  [{status}] Ep{ep['episode_id']:3d}: "
                  f"{ep['scenes']} scene(s), "
                  f"{ep['units']} units, "
                  f"{ep['duration_s']:.1f}s  "
                  f"{ep['unit_types']}")

    if report.errors:
        print(f"\nERRORS:")
        for e in report.errors:
            print(f"  [ERR] {e}")
    if report.warnings:
        print(f"\nWARNINGS ({len(report.warnings)}):")
        for w in report.warnings[:20]:
            print(f"  [WARN] {w}")
        if len(report.warnings) > 20:
            print(f"  ... and {len(report.warnings)-20} more")

    print(f"\nOutputs: {report_path}, {parsed_path}, {meta_path}")


if __name__ == "__main__":
    main()
