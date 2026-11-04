"""
stitcher.py - Constrained multi-segment stitching for promo candidates (Phase 4).

For candidates with context_needed = med/high:
- Discovers potential short setup segments (5-15s) from earlier in the episode.
- Passes candidate setup segment IDs to the LLM (never free-form timestamps).
- Code strictly verifies:
  1. Total duration (all segments combined) <= 60.0s and >= 20.0s.
  2. Chronological/narrative ordering (seg1.end < seg2.start).
  3. Every timestamp corresponds to parsed screenplay units.
- Fully optional behind `--stitch` flag.
"""

import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

from screenplay_parser import ParsedUnit, seconds_to_ts
from candidate_generator import CandidateWindow
from llm import call_llm


@dataclass
class PromoSegment:
    episode_id: int
    start: float       # seconds
    end: float         # seconds
    duration: float    # seconds
    text_snippet: str


@dataclass
class StitchedPromo:
    promo_id: str
    primary_episode_id: int
    segments: List[PromoSegment]
    total_duration: float
    hook_speaker: Optional[str]
    hook_text: str
    cliffhanger_speaker: Optional[str]
    cliffhanger_text: str
    full_text: str
    context_needed: str
    spoiler_risk: bool
    candidate_score: float = 0.0
    is_stitched: bool = False
    stitching_reason: Optional[str] = None


STITCH_SCHEMA = {
    "required": ["chosen_setup_id", "reasoning"]
}


def find_setup_segments(
    units: List[ParsedUnit],
    before_unit_idx: int,
    max_duration: float = 15.0
) -> List[Dict[str, Any]]:
    """
    Find 2-4 short dramatic setup moments from earlier units in the episode.
    """
    setups = []
    # Search backwards from the main clip's start
    for i in range(max(0, before_unit_idx - 15), before_unit_idx - 2):
        u = units[i]
        if u.unit_type in ("dialogue", "action"):
            # Try to build a short 5-12s beat
            for j in range(i, min(before_unit_idx - 1, i + 5)):
                dur = round(units[j].end - u.start, 2)
                if 5.0 <= dur <= max_duration:
                    snippet = " | ".join(
                        f"{x.speaker or x.unit_type.upper()}: {x.text}"
                        for x in units[i:j+1] if x.text
                    )
                    setups.append({
                        "setup_id": f"SETUP_{len(setups)+1}",
                        "start_idx": i,
                        "end_idx": j,
                        "start": u.start,
                        "end": units[j].end,
                        "duration": dur,
                        "snippet": snippet[:150]
                    })
                    break
        if len(setups) >= 3:
            break
    return setups


def stitch_candidate(
    candidate: CandidateWindow,
    ep_units: List[ParsedUnit],
    enable_llm: bool = True,
    config_path: str = "config.yaml"
) -> StitchedPromo:
    """
    Attempt to stitch a setup segment to a candidate if context is needed.
    """
    primary_seg = PromoSegment(
        episode_id=candidate.episode_id,
        start=candidate.start_time,
        end=candidate.end_time,
        duration=candidate.duration,
        text_snippet=candidate.full_text[:200]
    )

    # If stitching is disabled, context is low, or clip is already >= 48s, return primary segment immediately
    if not enable_llm or candidate.context_needed == "low" or candidate.duration >= 48.0 or candidate.start_unit_index < 4:
        return StitchedPromo(
            promo_id=candidate.candidate_id,
            primary_episode_id=candidate.episode_id,
            segments=[primary_seg],
            total_duration=candidate.duration,
            hook_speaker=candidate.hook_speaker,
            hook_text=candidate.hook_text,
            cliffhanger_speaker=candidate.cliffhanger_speaker,
            cliffhanger_text=candidate.cliffhanger_text,
            full_text=candidate.full_text,
            context_needed=candidate.context_needed,
            spoiler_risk=candidate.spoiler_risk,
            candidate_score=candidate.candidate_score,
            is_stitched=False,
            stitching_reason=None
        )

    # Find setup options
    max_setup_dur = round(60.0 - candidate.duration, 2)
    setups = find_setup_segments(ep_units, candidate.start_unit_index, max_duration=min(14.0, max_setup_dur))

    if not setups or not enable_llm:
        return StitchedPromo(
            promo_id=candidate.candidate_id,
            primary_episode_id=candidate.episode_id,
            segments=[primary_seg],
            total_duration=candidate.duration,
            hook_speaker=candidate.hook_speaker,
            hook_text=candidate.hook_text,
            cliffhanger_speaker=candidate.cliffhanger_speaker,
            cliffhanger_text=candidate.cliffhanger_text,
            full_text=candidate.full_text,
            context_needed=candidate.context_needed,
            spoiler_risk=candidate.spoiler_risk,
            candidate_score=candidate.candidate_score,
            is_stitched=False,
            stitching_reason=None
        )

    # Prompt LLM with setup options
    setup_text = "\n".join(
        f"- ID: {s['setup_id']} | Timestamps: {seconds_to_ts(s['start'])} to {seconds_to_ts(s['end'])} ({s['duration']}s)\n  Dialogue/Action: {s['snippet']}"
        for s in setups
    )

    prompt_template = Path("prompts/stitching_v1.txt").read_text(encoding="utf-8")
    prompt = prompt_template.format(
        episode_id=candidate.episode_id,
        main_start=seconds_to_ts(candidate.start_time),
        main_end=seconds_to_ts(candidate.end_time),
        main_duration=candidate.duration,
        main_text=candidate.full_text[:300],
        setup_options=setup_text
    )

    try:
        res = call_llm(prompt, schema=STITCH_SCHEMA, tier="cheap", config_path=config_path)
        chosen_id = res.get("chosen_setup_id", "NONE")
        reasoning = res.get("reasoning", "")
    except Exception:
        chosen_id = "NONE"
        reasoning = "Stitching skipped due to LLM error"

    if chosen_id != "NONE":
        chosen_setup = next((s for s in setups if s["setup_id"] == chosen_id), None)
        if chosen_setup:
            setup_seg = PromoSegment(
                episode_id=candidate.episode_id,
                start=chosen_setup["start"],
                end=chosen_setup["end"],
                duration=chosen_setup["duration"],
                text_snippet=chosen_setup["snippet"]
            )
            # Code verification:
            # 1. Chronological order
            assert setup_seg.end <= primary_seg.start, "Stitched segments must be chronological"
            # 2. Total duration constraint
            total_dur = round(setup_seg.duration + primary_seg.duration, 2)
            if 20.0 <= total_dur <= 60.0:
                combined_full_text = f"[SETUP SCENE]\n{setup_seg.text_snippet}\n\n[MAIN SCENE]\n{candidate.full_text}"
                return StitchedPromo(
                    promo_id=f"{candidate.candidate_id}_stitched",
                    primary_episode_id=candidate.episode_id,
                    segments=[setup_seg, primary_seg],
                    total_duration=total_dur,
                    hook_speaker=candidate.hook_speaker,
                    hook_text=f"{chosen_setup['snippet'][:80]} ... {candidate.hook_text}",
                    cliffhanger_speaker=candidate.cliffhanger_speaker,
                    cliffhanger_text=candidate.cliffhanger_text,
                    full_text=combined_full_text,
                    context_needed="low",  # Resolved by setup
                    spoiler_risk=candidate.spoiler_risk,
                    candidate_score=candidate.candidate_score,
                    is_stitched=True,
                    stitching_reason=reasoning
                )

    # Fallback to single segment if verification failed or "NONE"
    return StitchedPromo(
        promo_id=candidate.candidate_id,
        primary_episode_id=candidate.episode_id,
        segments=[primary_seg],
        total_duration=candidate.duration,
        hook_speaker=candidate.hook_speaker,
        hook_text=candidate.hook_text,
        cliffhanger_speaker=candidate.cliffhanger_speaker,
        cliffhanger_text=candidate.cliffhanger_text,
        full_text=candidate.full_text,
        context_needed=candidate.context_needed,
        spoiler_risk=candidate.spoiler_risk,
        is_stitched=False,
        stitching_reason=None
    )


def stitch_all_candidates(
    candidates: List[CandidateWindow],
    parsed_units: Dict[str, List[Dict[str, Any]]],
    enable_stitching: bool = False,
    config_path: str = "config.yaml"
) -> List[StitchedPromo]:
    """Process all candidates into StitchedPromo objects."""
    results = []
    print(f"Processing candidate segments (stitching enabled={enable_stitching})...")
    for cand in candidates:
        ep_units = [ParsedUnit(**u) for u in parsed_units[str(cand.episode_id)]]
        promo = stitch_candidate(cand, ep_units, enable_llm=enable_stitching, config_path=config_path)
        results.append(promo)
    return results
