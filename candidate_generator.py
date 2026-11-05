"""
candidate_generator.py - Generate, tag, and filter promo candidate windows (Phase 3).

1. Code: Generate candidate windows (20s - 60s) strictly starting & ending on unit boundaries.
   - Start unit heuristic: Dialogue lines, sudden actions, or scene openings.
   - End unit heuristic: Dialogue lines ending in punctuation (?, !), dramatic actions, or final line before scene cut.
2. LLM (Cheap Tier): Tag scenes/beats with hook_potential (0-5), cliffhanger_potential (0-5),
   intensity, context_needed, spoiler_risk.
3. Code: Filter candidates to those with hook-like starts and unresolved ends, keeping top N per episode.
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

from screenplay_parser import ParsedUnit, seconds_to_ts
from llm import call_llm, load_config


# ── Candidate Data Structure ──────────────────────────────────────────────────

@dataclass
class CandidateWindow:
    candidate_id: str
    episode_id: int
    scene_id: int
    start_time: float          # seconds (verified from parsed unit)
    end_time: float            # seconds (verified from parsed unit)
    duration: float            # seconds
    start_unit_index: int
    end_unit_index: int
    start_unit_type: str
    end_unit_type: str
    hook_speaker: Optional[str]
    hook_text: str             # Content in the first ~3-5 seconds
    cliffhanger_speaker: Optional[str]
    cliffhanger_text: str      # Content in the final lines before cutoff
    full_text: str             # All dialogue and key actions in window
    
    # AI Tagged / Derived scores
    hook_potential: int = 0
    hook_type: str = "none"
    cliffhanger_potential: int = 0
    is_open_ended: bool = False
    intensity: str = "low"
    context_needed: str = "low"
    spoiler_risk: bool = False
    candidate_score: float = 0.0


# ── Pure Code: Sliding Window Generator ───────────────────────────────────────

def generate_raw_windows(
    units: List[ParsedUnit],
    min_dur: float = 20.0,
    max_dur: float = 60.0,
    step_units: int = 1
) -> List[CandidateWindow]:
    """
    Sliding window over parsed units strictly adhering to unit boundaries.
    Never cuts mid-line or mid-action.
    """
    candidates = []
    num_units = len(units)

    for i in range(0, num_units, step_units):
        u_start = units[i]

        # Prefer starts that have punch: Dialogue lines, key actions, or scene starts
        # Avoid starting on a pure background sound_fx or closing camera transition
        if u_start.unit_type not in ("dialogue", "action") and u_start.unit_index != 0:
            continue

        for j in range(i + 1, num_units):
            u_end = units[j]
            duration = round(u_end.end - u_start.start, 2)

            if duration < min_dur:
                continue
            if duration > max_dur:
                break  # Further units will only increase duration

            # Prefer ends that cut on drama: dialogue, sound_fx sting, or scene terminus
            # Avoid ending on an incomplete camera setup unless it marks the end of a scene
            is_scene_final = (j == num_units - 1) or (units[j + 1].scene_id != u_end.scene_id)
            if u_end.unit_type not in ("dialogue", "action", "sound_fx") and not is_scene_final:
                continue

            # Assemble hook text (first 3-5 seconds)
            hook_units = [u for u in units[i:j+1] if u.start <= u_start.start + 4.0]
            hook_text = " | ".join(
                f"{u.speaker or u.unit_type.upper()}: {u.text}" for u in hook_units if u.text
            )

            # Assemble cliffhanger text (final 4 seconds)
            cliff_units = [u for u in units[i:j+1] if u.end >= u_end.end - 4.0]
            cliff_text = " | ".join(
                f"{u.speaker or u.unit_type.upper()}: {u.text}" for u in cliff_units if u.text
            )

            # Full narrative text in window
            dialogue_and_actions = [
                f"{u.speaker or u.unit_type.upper()}: {u.text}"
                for u in units[i:j+1]
                if u.unit_type in ("dialogue", "action", "sound_fx") and u.text
            ]
            full_text = "\n".join(dialogue_and_actions)

            cid = f"ep{u_start.episode_id:02d}_u{i}_u{j}"
            candidates.append(CandidateWindow(
                candidate_id=cid,
                episode_id=u_start.episode_id,
                scene_id=u_start.scene_id,
                start_time=u_start.start,
                end_time=u_end.end,
                duration=duration,
                start_unit_index=i,
                end_unit_index=j,
                start_unit_type=u_start.unit_type,
                end_unit_type=u_end.unit_type,
                hook_speaker=u_start.speaker,
                hook_text=hook_text[:200],
                cliffhanger_speaker=u_end.speaker,
                cliffhanger_text=cliff_text[:200],
                full_text=full_text,
            ))

    return candidates


# ── Cheap-Tier LLM Scene Tagging ─────────────────────────────────────────────

TAGGING_SCHEMA = {
    "required": ["episode_id", "scenes"]
}


def tag_episode_scenes(
    episode_id: int,
    units: List[ParsedUnit],
    bible: Dict[str, Any],
    config_path: str = "config.yaml"
) -> Dict[str, Any]:
    """
    Call the cheap-tier LLM once per episode to tag scenes for hook/cliffhanger potential.
    """
    # Build condensed dialogue/action representation of the episode
    lines = []
    for u in units:
        if u.unit_type in ("dialogue", "action", "sound_fx"):
            ts_str = seconds_to_ts(u.start)
            spk = u.speaker or u.unit_type.upper()
            dir_str = f" ({u.direction})" if u.direction else ""
            lines.append(f"[{ts_str}] Scene {u.scene_id} | {spk}{dir_str}: {u.text}")

    episode_script = "\n".join(lines[:120])  # Cap to fit prompt cleanly

    prompt_template = Path("prompts/scene_tagging_v1.txt").read_text(encoding="utf-8")
    prompt = prompt_template.format(
        episode_id=episode_id,
        show_title=bible.get("title", "Microdrama"),
        premise=bible.get("premise", ""),
        central_twists=json.dumps(bible.get("central_twists", [])),
        episode_script=episode_script
    )

    tags = call_llm(prompt, schema=TAGGING_SCHEMA, tier="cheap", config_path=config_path)
    return tags


# ── Heuristic Fallback Tagger (Rule-based) ────────────────────────────────────

def rule_based_tag_window(window: CandidateWindow, bible: Dict[str, Any]) -> None:
    """
    Advanced rule-based heuristics to score hook and cliffhanger potentials,
    detect emotional directions, measure intensity, and evaluate context needs.
    """
    hook_score = 2
    hook_type = "dialogue opening"
    hook_lower = window.hook_text.lower()
    
    # 1. Emotional direction detection in opening
    emotional_directions = ["outraged", "sneering", "furious", "heartbroken", "tearful", "coldly", "screaming", "scoffing", "trembling"]
    has_emotional_direction = any(f"({d})" in hook_lower for d in emotional_directions)

    # 2. Check opening lines for explosive keywords & actions
    if any(w in hook_lower for w in ["slap", "hit", "shove", "gasp", "grab", "fling", "strike", "smack", "choke", "drag", "kneel", "sob"]):
        hook_score = 5
        hook_type = "physical altercation / action"
    elif any(w in hook_lower for w in ["holding her hand", "marrying me", "divorce", "marry", "bastard", "liar", "betray", "swear", "die", "kill", "poison", "murder", "treason", "adultery"]):
        hook_score = 5
        hook_type = "shocking accusation / betrayal"
    elif any(w in hook_lower for w in ["why are you", "who is", "what did you do", "how dare you", "look at me", "stand back", "remove her", "enough!"]):
        hook_score = 4
        hook_type = "dramatic confrontation"
    elif has_emotional_direction:
        hook_score = max(hook_score, 4)
        hook_type = "emotionally charged opening"

    # 3. Check cliffhanger lines & unresolved questions
    cliff_score = 2
    is_open = False
    cliff_lower = window.cliffhanger_text.lower()

    if "?" in window.cliffhanger_text:
        cliff_score = 4
        is_open = True
    if any(w in cliff_lower for w in ["or else", "choose", "never", "too late", "wait", "carefully", "try me", "mark my words", "pay for this", "what did you find"]):
        cliff_score = 5
        is_open = True
    elif any(w in cliff_lower for w in ["very well", "goodbye", "yes father", "understood", "as you wish", "i agree"]):
        # Explicit resolution signals: conversation or dispute closed
        cliff_score = 2
        is_open = False
    elif window.end_unit_type == "sound_fx":
        cliff_score = max(cliff_score, 4)
        is_open = True

    # 4. Intensity calculation: conflict volume & speaker turnover
    lines = [l for l in window.full_text.split("\n") if l.strip()]
    exclamation_count = window.full_text.count("!") + window.full_text.count("?")
    unique_speakers = set()
    for l in lines:
        if ":" in l:
            unique_speakers.add(l.split(":", 1)[0].strip())
    
    if len(unique_speakers) >= 3 and exclamation_count >= 3:
        intensity = "high"
    elif len(unique_speakers) >= 2 or exclamation_count >= 2:
        intensity = "medium"
    else:
        intensity = "low"

    # 5. Context needed estimation
    if window.episode_id <= 3:
        context_needed = "low"  # Altar betrayal and initial premise are self-evident
    elif window.episode_id <= 10:
        # Check if characters are named explicitly in the clip
        has_named_char = any(name in window.full_text for name in ["Juliana", "Gerald", "Clarissa", "Soldier", "Father", "Mother"])
        context_needed = "low" if has_named_char else "med"
    elif window.episode_id <= 25:
        context_needed = "med"
    else:
        context_needed = "high"

    # 6. Spoiler detection via bible twists
    spoiler = False
    if window.episode_id >= 40:
        if any(w in window.full_text.lower() for w in ["duke of ashburn", "rightful duke", "unmask", "true identity"]):
            spoiler = True

    window.hook_potential = hook_score
    window.hook_type = hook_type
    window.cliffhanger_potential = cliff_score
    window.is_open_ended = is_open
    window.intensity = intensity
    window.context_needed = context_needed
    window.spoiler_risk = spoiler


# ── Fusion, Scoring & Top-N Pruning ──────────────────────────────────────────

def score_and_filter_candidates(
    candidates: List[CandidateWindow],
    top_n_per_ep: int = 8,
    min_hook: int = 3,
    min_cliff: int = 3
) -> List[CandidateWindow]:
    """
    Filter and rank candidate windows, returning the top N candidates per episode.
    Applies TikTok duration sweet-spot weighting and penalizes long, dragging clips.
    """
    by_episode: Dict[int, List[CandidateWindow]] = {}
    for c in candidates:
        by_episode.setdefault(c.episode_id, []).append(c)

    filtered_results = []

    for ep_id, ep_candidates in by_episode.items():
        # Score each candidate
        for c in ep_candidates:
            # Composite heuristic score
            score = (
                0.40 * c.hook_potential +
                0.35 * c.cliffhanger_potential +
                (0.20 if c.is_open_ended else -0.10)
            )
            # Duration sweet-spot bonus (TikTok retention optimization)
            if 25.0 <= c.duration <= 38.0:
                score += 0.25  # Prime short-form sweet spot
            elif 38.0 < c.duration <= 48.0:
                score += 0.10  # Acceptable dramatic stretch
            elif c.duration > 52.0:
                score -= 0.15  # Penalty for sluggish completion drop-off

            # Intensity bonus
            if c.intensity == "high":
                score += 0.15
            elif c.intensity == "low":
                score -= 0.10

            if c.spoiler_risk:
                score -= 0.60
            if c.context_needed == "high":
                score -= 0.35
            c.candidate_score = round(score, 3)

        # Sort descending by candidate score
        sorted_candidates = sorted(ep_candidates, key=lambda x: x.candidate_score, reverse=True)

        # Deduplicate heavily overlapping windows within the same episode (keep higher score)
        kept = []
        for cand in sorted_candidates:
            # Check overlap with already kept windows
            overlap = False
            for k in kept:
                # Calculate Intersection over Union (IoU) of time range
                i_start = max(cand.start_time, k.start_time)
                i_end = min(cand.end_time, k.end_time)
                intersection = max(0.0, i_end - i_start)
                union = (cand.end_time - cand.start_time) + (k.end_time - k.start_time) - intersection
                iou = intersection / union if union > 0 else 0.0
                if iou > 0.5:  # Overlap greater than 50%
                    overlap = True
                    break
            if not overlap:
                kept.append(cand)
            if len(kept) >= top_n_per_ep:
                break

        filtered_results.extend(kept)

    return filtered_results


# ── Pipeline Runner ──────────────────────────────────────────────────────────

def run_candidate_generation(
    parsed_units_path: str = "output/parsed_units.json",
    bible_path: str = "output/bible.json",
    out_path: str = "output/candidates.json",
    config_path: str = "config.yaml"
) -> List[CandidateWindow]:
    """Run full candidate generation pass across all parsed episodes."""
    config = load_config(config_path)
    cg_cfg = config.get("candidate_generation", {})
    min_dur = cg_cfg.get("min_duration", 20.0)
    max_dur = cg_cfg.get("max_duration", 60.0)
    top_n = cg_cfg.get("top_candidates_per_ep", 8)

    with open(parsed_units_path, "r", encoding="utf-8") as f:
        parsed_dict = json.load(f)

    bible = {}
    if Path(bible_path).exists():
        with open(bible_path, "r", encoding="utf-8") as f:
            bible = json.load(f)

    print(f"Generating candidate windows ({min_dur}s - {max_dur}s) across {len(parsed_dict)} episodes...")

    all_candidates: List[CandidateWindow] = []

    for ep_str, unit_list in parsed_dict.items():
        ep_id = int(ep_str)
        units = [ParsedUnit(**u) for u in unit_list]

        # 1. Pure code sliding window
        windows = generate_raw_windows(units, min_dur=min_dur, max_dur=max_dur)

        # 2. Tag windows with rules / LLM
        for w in windows:
            rule_based_tag_window(w, bible)

        all_candidates.extend(windows)

    # 3. Filter, score, dedupe and select top N per episode
    top_candidates = score_and_filter_candidates(all_candidates, top_n_per_ep=top_n)

    # Save to disk
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump([asdict(c) for c in top_candidates], f, indent=2)

    print(f"Candidate generation complete: {len(all_candidates)} raw windows generated -> {len(top_candidates)} top candidates selected.")
    print(f"Saved to {out_file}")

    return top_candidates


if __name__ == "__main__":
    run_candidate_generation()
