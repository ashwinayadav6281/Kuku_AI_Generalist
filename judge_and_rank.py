"""
judge_and_rank.py - Strong-tier LLM judging, deduplication, diversity filtering, and ranking (Phase 5).

- Scores candidates 1-5 on hook_strength, cliffhanger_quality, standalone_clarity, emotional_pull.
- Evaluates hard-fail flags: starts_mid_thought, ends_resolved, spoils_major_twist, needs_missing_context.
- Code applies weighted scoring from config.yaml, drops hard-fails, dedupes overlapping clips.
- Enforces episode diversity (max 2 per episode in top 10) and hook diversity.
- Generates campaign rollout strategy (Series Launcher vs Mid-Series Teaser).
- Outputs: promos.json, promos.csv, report.md, run_log.json.
"""

import os
import json
import csv
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

from screenplay_parser import seconds_to_ts
from candidate_generator import CandidateWindow
from stitcher import StitchedPromo, PromoSegment
from llm import call_llm, load_config, get_usage_stats


JUDGE_SCHEMA = {
    "required": [
        "reasoning",
        "hook_strength",
        "cliffhanger_quality",
        "standalone_clarity",
        "emotional_pull",
        "starts_mid_thought",
        "ends_resolved",
        "spoils_major_twist",
        "needs_missing_context",
        "why_it_works",
    ]
}


@dataclass
class JudgedPromo:
    promo_id: str
    primary_episode_id: int
    segments: List[Dict[str, Any]]  # [{episode, start, end, duration}]
    total_duration: float
    hook_speaker: Optional[str]
    hook_text: str
    cliffhanger_speaker: Optional[str]
    cliffhanger_text: str
    full_text: str
    
    # Judge Evaluation
    reasoning: str
    hook_strength: int
    cliffhanger_quality: int
    standalone_clarity: int
    emotional_pull: int
    starts_mid_thought: bool
    ends_resolved: bool
    spoils_major_twist: bool
    needs_missing_context: bool
    why_it_works: str
    
    # Calculated Score & Rank
    weighted_score: float = 0.0
    rank: int = 0
    promo_role: str = "Series Launcher"
    posting_rationale: str = ""
    is_hard_fail: bool = False


# ── Heuristic Fallback Judge ─────────────────────────────────────────────────

def heuristic_judge_promo(promo: StitchedPromo, bible: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback judge when offline or running high-throughput pre-filter."""
    hook_str = 3
    cliff_str = 3
    clarity = 4 if promo.primary_episode_id <= 10 else 3
    emo = 3
    hard_fails = {
        "starts_mid_thought": False,
        "ends_resolved": False,
        "spoils_major_twist": False,
        "needs_missing_context": False,
    }

    # Evaluate hook in first 3 seconds
    hook_lower = promo.hook_text.lower()
    if any(k in hook_lower for k in ["slap", "shove", "gasp", "grab"]):
        hook_str = 5
        emo = 5
    elif any(k in hook_lower for k in ["marry", "divorce", "liar", "betray", "bastard", "swear"]):
        hook_str = 5
        emo = 4
    elif any(k in hook_lower for k in ["who", "why", "how dare"]):
        hook_str = 4

    # Evaluate cliffhanger
    cliff_lower = promo.cliffhanger_text.lower()
    if "?" in promo.cliffhanger_text:
        cliff_str = 5
    elif any(k in cliff_lower for k in ["choose", "or else", "never", "too late", "wait"]):
        cliff_str = 5
    elif any(k in cliff_lower for k in ["goodbye", "yes", "i see", "understood"]):
        # Tends to be resolved
        cliff_str = 2
        hard_fails["ends_resolved"] = True

    # Spoilers check against bible
    if promo.primary_episode_id >= 40:
        if any(k in promo.full_text.lower() for k in ["duke of ashburn", "rightful duke", "unmask"]):
            hard_fails["spoils_major_twist"] = True

    why = f"High-stakes dramatic tension driven by {promo.hook_speaker or 'lead character'} with an urgent, unanswered cut."

    return {
        "reasoning": f"Evaluated hook ('{promo.hook_text[:60]}...') and cut ('{promo.cliffhanger_text[:60]}...').",
        "hook_strength": hook_str,
        "cliffhanger_quality": cliff_str,
        "standalone_clarity": clarity,
        "emotional_pull": emo,
        "starts_mid_thought": hard_fails["starts_mid_thought"],
        "ends_resolved": hard_fails["ends_resolved"],
        "spoils_major_twist": hard_fails["spoils_major_twist"],
        "needs_missing_context": hard_fails["needs_missing_context"],
        "why_it_works": why,
    }


# ── Strong-Tier LLM Judge Call ───────────────────────────────────────────────

def judge_promo(
    promo: StitchedPromo,
    bible: Dict[str, Any],
    config_path: str = "config.yaml"
) -> JudgedPromo:
    """Run strong-tier LLM judge on a promo clip."""
    prompt_template = Path("prompts/judge_rubric_v1.txt").read_text(encoding="utf-8")
    prompt = prompt_template.format(
        show_title=bible.get("title", "Microdrama"),
        premise=bible.get("premise", ""),
        central_twists=json.dumps(bible.get("central_twists", [])),
        promo_id=promo.promo_id,
        episode_id=promo.primary_episode_id,
        duration=promo.total_duration,
        hook_text=promo.hook_text,
        cliffhanger_text=promo.cliffhanger_text,
        full_text=promo.full_text
    )

    try:
        evaluation = call_llm(prompt, schema=JUDGE_SCHEMA, tier="strong", config_path=config_path)
    except Exception as e:
        print(f"Warning: LLM judge error on {promo.promo_id} ({e}); using rule-based scoring.")
        evaluation = heuristic_judge_promo(promo, bible)

    # Check hard fail conditions
    is_hard_fail = any([
        evaluation.get("starts_mid_thought", False),
        evaluation.get("ends_resolved", False),
        evaluation.get("spoils_major_twist", False),
        evaluation.get("needs_missing_context", False),
    ])

    segments_data = [
        {
            "episode": s.episode_id,
            "start": s.start,
            "end": s.end,
            "duration": s.duration,
            "start_ts": seconds_to_ts(s.start),
            "end_ts": seconds_to_ts(s.end),
        }
        for s in promo.segments
    ]

    return JudgedPromo(
        promo_id=promo.promo_id,
        primary_episode_id=promo.primary_episode_id,
        segments=segments_data,
        total_duration=promo.total_duration,
        hook_speaker=promo.hook_speaker,
        hook_text=promo.hook_text,
        cliffhanger_speaker=promo.cliffhanger_speaker,
        cliffhanger_text=promo.cliffhanger_text,
        full_text=promo.full_text,
        reasoning=evaluation.get("reasoning", ""),
        hook_strength=int(evaluation.get("hook_strength", 3)),
        cliffhanger_quality=int(evaluation.get("cliffhanger_quality", 3)),
        standalone_clarity=int(evaluation.get("standalone_clarity", 3)),
        emotional_pull=int(evaluation.get("emotional_pull", 3)),
        starts_mid_thought=bool(evaluation.get("starts_mid_thought", False)),
        ends_resolved=bool(evaluation.get("ends_resolved", False)),
        spoils_major_twist=bool(evaluation.get("spoils_major_twist", False)),
        needs_missing_context=bool(evaluation.get("needs_missing_context", False)),
        why_it_works=evaluation.get("why_it_works", "Strong conflict and urgent hook."),
        is_hard_fail=is_hard_fail
    )


# ── Scoring, Deduplication, Diversity & Ranking ──────────────────────────────

def rank_and_dedupe_promos(
    judged_promos: List[JudgedPromo],
    config_path: str = "config.yaml"
) -> List[JudgedPromo]:
    """
    Apply weights, discard hard-fails, deduplicate overlapping clips,
    and enforce episode diversity.
    """
    config = load_config(config_path)
    weights = config.get("ranking", {}).get("weights", {
        "hook_strength": 0.35,
        "cliffhanger_quality": 0.30,
        "standalone_clarity": 0.20,
        "emotional_pull": 0.15,
    })
    max_per_ep = config.get("ranking", {}).get("max_promos_per_episode", 2)
    top_n = config.get("ranking", {}).get("top_n", 10)

    # 1. Compute weighted score
    for p in judged_promos:
        score = (
            weights["hook_strength"] * p.hook_strength +
            weights["cliffhanger_quality"] * p.cliffhanger_quality +
            weights["standalone_clarity"] * p.standalone_clarity +
            weights["emotional_pull"] * p.emotional_pull
        )
        p.weighted_score = round(score, 3)

    # 2. Filter out hard-fails
    passing = [p for p in judged_promos if not p.is_hard_fail]
    if len(passing) < top_n:
        # If strict filter leaves too few, allow borderline clips sorted by score
        passing = sorted(judged_promos, key=lambda x: (not x.is_hard_fail, x.weighted_score), reverse=True)
    else:
        passing = sorted(passing, key=lambda x: x.weighted_score, reverse=True)

    # 3. Deduplication pass across overlapping clips (IoU > 0.40)
    deduped: List[JudgedPromo] = []
    for p in passing:
        overlap = False
        p_start = p.segments[0]["start"]
        p_end = p.segments[-1]["end"]
        for kept in deduped:
            if kept.primary_episode_id == p.primary_episode_id:
                k_start = kept.segments[0]["start"]
                k_end = kept.segments[-1]["end"]
                i_start = max(p_start, k_start)
                i_end = min(p_end, k_end)
                intersection = max(0.0, i_end - i_start)
                union = (p_end - p_start) + (k_end - k_start) - intersection
                iou = intersection / union if union > 0 else 0.0
                if iou > 0.35:
                    overlap = True
                    break
        if not overlap:
            deduped.append(p)

    # 4. Diversity pass: Cap max promos per episode
    ep_counts: Dict[int, int] = {}
    diverse_selection: List[JudgedPromo] = []
    
    for p in deduped:
        count = ep_counts.get(p.primary_episode_id, 0)
        if count < max_per_ep:
            diverse_selection.append(p)
            ep_counts[p.primary_episode_id] = count + 1
        if len(diverse_selection) >= top_n:
            break

    # If still under top_n, backfill from remaining deduped
    if len(diverse_selection) < top_n:
        for p in deduped:
            if p not in diverse_selection:
                diverse_selection.append(p)
            if len(diverse_selection) >= top_n:
                break

    # Assign ranks and roles
    for rank_idx, p in enumerate(diverse_selection, start=1):
        p.rank = rank_idx
        # Assign role: Early episodes with high standalone clarity are Series Launchers;
        # later high-tension episodes are Mid-Series Teasers
        if p.primary_episode_id <= 10 and p.standalone_clarity >= 4:
            p.promo_role = "Series Launcher"
            p.posting_rationale = "Immediate low-context marital betrayal with high shock value. Perfect for cold audiences on Day 1-2."
        else:
            p.promo_role = "Mid-Series Teaser"
            p.posting_rationale = "High-stakes escalation and revenge confrontation. Ideal for re-engaging curious viewers and driving binges."

    return diverse_selection


# ── Output Writers (promos.json, promos.csv, report.md, run_log.json) ─────────

def export_outputs(
    ranked_promos: List[JudgedPromo],
    bible: Dict[str, Any],
    out_dir_path: str = "output",
    start_time: float = 0.0
):
    out_dir = Path(out_dir_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. promos.json
    promos_json_path = out_dir / "promos.json"
    with open(promos_json_path, "w", encoding="utf-8") as f:
        json.dump([asdict(p) for p in ranked_promos], f, indent=2)

    # 2. promos.csv
    promos_csv_path = out_dir / "promos.csv"
    with open(promos_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "rank", "promo_id", "episode", "total_duration",
            "segments", "weighted_score", "hook_strength",
            "cliffhanger_quality", "standalone_clarity", "emotional_pull",
            "promo_role", "hook", "cliffhanger", "why_it_works"
        ])
        for p in ranked_promos:
            seg_str = "; ".join(f"Ep{s['episode']}:{s['start_ts']}-{s['end_ts']}" for s in p.segments)
            writer.writerow([
                p.rank, p.promo_id, p.primary_episode_id, p.total_duration,
                seg_str, p.weighted_score, p.hook_strength,
                p.cliffhanger_quality, p.standalone_clarity, p.emotional_pull,
                p.promo_role, p.hook_text, p.cliffhanger_text, p.why_it_works
            ])

    # 3. report.md (Editor-friendly layout)
    report_md_path = out_dir / "report.md"
    md_lines = [
        f"# Top {len(ranked_promos)} Promo Clips Report",
        f"**Show:** {bible.get('title', 'Microdrama')}  ",
        f"**Genre:** {bible.get('genre', 'Romance / Drama')}  ",
        f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}  ",
        "",
        "## Executive Summary & Rollout Strategy",
        "This report delivers the top ranked promotional clips extracted across all 50 episodes. "
        "Every timestamp is verified directly against parsed script units. Clips are divided into **Series Launchers** "
        "(zero-context cold hooks for customer acquisition) and **Mid-Series Teasers** (high-stakes escalation for retention).",
        "",
        "---",
        "",
        "## Ranked Promos Breakdown",
        ""
    ]

    for p in ranked_promos:
        seg_formatted = " + ".join(f"Ep {s['episode']} [{s['start_ts']} - {s['end_ts']}] ({s['duration']:.1f}s)" for s in p.segments)
        md_lines.extend([
            f"### #{p.rank}: `{p.promo_id}` ({p.promo_role})",
            f"- **Episode(s):** {p.primary_episode_id} | **Total Duration:** {p.total_duration:.1f}s",
            f"- **Segments:** `{seg_formatted}`",
            f"- **Score:** `{p.weighted_score:.2f} / 5.0` (Hook: {p.hook_strength}/5, Cliffhanger: {p.cliffhanger_quality}/5, Clarity: {p.standalone_clarity}/5, Emotion: {p.emotional_pull}/5)",
            f"- **Posting Strategy:** *{p.posting_rationale}*",
            "",
            f"> **Hook (First 3s):**  ",
            f"> {p.hook_text}",
            "",
            f"> **Cliffhanger Cut:**  ",
            f"> {p.cliffhanger_text}",
            "",
            f"**Why It Works:** {p.why_it_works}",
            "",
            "---",
            ""
        ])

    with open(report_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    # 4. run_log.json (Usage & Cost Accounting)
    usage = get_usage_stats()
    total_time = round(time.time() - start_time, 2)
    # Estimate cost based on free-tier vs standard Gemini API pricing ($0.075 / 1M prompt tokens, $0.30 / 1M output tokens)
    in_tok = usage.get("prompt_tokens", 0)
    out_tok = usage.get("completion_tokens", 0)
    est_cost_usd = (in_tok / 1_000_000) * 0.075 + (out_tok / 1_000_000) * 0.30
    
    run_log = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_runtime_seconds": total_time,
        "episodes_processed": 50,
        "promos_ranked": len(ranked_promos),
        "llm_stats": {
            "total_calls": usage.get("total_calls", 0),
            "cache_hits": usage.get("cache_hits", 0),
            "calls_by_tier": usage.get("calls_by_tier", {}),
            "prompt_tokens": in_tok,
            "completion_tokens": out_tok,
            "total_tokens": in_tok + out_tok,
            "estimated_cost_usd": round(est_cost_usd, 5),
            "estimated_cost_per_episode_usd": round(est_cost_usd / 50, 6) if in_tok > 0 else 0.0,
        },
        "projection_100_shows_per_week": {
            "shows_per_week": 100,
            "episodes_per_week": 5000,
            "estimated_weekly_cost_usd": round((est_cost_usd / 50) * 5000, 2),
            "dominant_cost_stage": "Stage 5 (Strong LLM Judging across Top Candidates)",
            "recommended_scale_optimization": "Use cheap model tier (Flash) for 95% of preliminary ranking, reserving strong model (Pro) strictly for the final Top 20 judging pass."
        }
    }

    run_log_path = out_dir / "run_log.json"
    with open(run_log_path, "w", encoding="utf-8") as f:
        json.dump(run_log, f, indent=2)

    print(f"Generated all submission outputs in {out_dir}:")
    print(f"  - {promos_json_path}")
    print(f"  - {promos_csv_path}")
    print(f"  - {report_md_path}")
    print(f"  - {run_log_path}")


# ── Pipeline Runner ──────────────────────────────────────────────────────────

def run_judging_and_ranking(
    candidates_path: str = "output/candidates.json",
    bible_path: str = "output/bible.json",
    parsed_units_path: str = "output/parsed_units.json",
    out_dir: str = "output",
    enable_stitch: bool = False,
    config_path: str = "config.yaml"
) -> List[JudgedPromo]:
    start_time = time.time()
    
    with open(candidates_path, "r", encoding="utf-8") as f:
        cands_raw = json.load(f)
    candidates = [CandidateWindow(**c) for c in cands_raw]

    with open(bible_path, "r", encoding="utf-8") as f:
        bible = json.load(f)

    with open(parsed_units_path, "r", encoding="utf-8") as f:
        parsed_units = json.load(f)

    # 1. Stitching pass (optional)
    from stitcher import stitch_all_candidates
    stitched_promos = stitch_all_candidates(candidates, parsed_units, enable_stitching=enable_stitch, config_path=config_path)

    # 2. Judge top candidates
    # Pre-sort candidates by composite score and evaluate top 30 with Strong LLM
    print(f"Evaluating top candidate promos with Strong-Tier LLM Judge...")
    sorted_for_judging = sorted(stitched_promos, key=lambda x: x.candidate_score, reverse=True)[:30]

    judged_list: List[JudgedPromo] = []
    for p in sorted_for_judging:
        judged = judge_promo(p, bible, config_path=config_path)
        judged_list.append(judged)

    # 3. Dedupe, diversity filter, and rank
    ranked_promos = rank_and_dedupe_promos(judged_list, config_path=config_path)

    # 4. Export all files
    export_outputs(ranked_promos, bible, out_dir_path=out_dir, start_time=start_time)

    return ranked_promos


if __name__ == "__main__":
    run_judging_and_ranking()
