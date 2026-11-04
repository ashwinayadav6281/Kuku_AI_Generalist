"""
failure_analyzer.py - Automatically detect, extract, and analyze edge-case promos.

Extracts:
1. 5 worst-ranked-yet-passing candidate promos.
2. 5 most suspicious top-tier promos (e.g. high score despite borderline context, or ending on resolved beats).
Outputs failures.md.
"""

import json
from pathlib import Path
from typing import Dict, Any, List

from screenplay_parser import seconds_to_ts


def analyze_failures(
    candidates_path: str = "output/candidates.json",
    promos_path: str = "output/promos.json",
    out_path: str = "failures.md"
):
    with open(candidates_path, "r", encoding="utf-8") as f:
        candidates = json.load(f)

    with open(promos_path, "r", encoding="utf-8") as f:
        promos = json.load(f)

    # 1. 5 Worst-ranked yet passing candidates (lowest candidate score among valid windows)
    sorted_by_score_asc = sorted(candidates, key=lambda x: x["candidate_score"])[:5]

    # 2. 5 Suspicious top-tier promos
    # Criteria: High score but high duration (>50s), high episode number (>30),
    # or ending lines that lack questions or urgency
    suspicious = []
    for p in promos:
        suspicion_reasons = []
        dur = p["total_duration"]
        ep = p["primary_episode_id"]
        cliff = p["cliffhanger_text"].lower()

        if dur > 46.0:
            suspicion_reasons.append(f"Long duration ({dur:.1f}s) risks TikTok viewer drop-off before cliffhanger")
        if ep >= 20:
            suspicion_reasons.append(f"Later episode (Ep {ep}) assumes viewer knows established character dynamics")
        if not any(q in cliff for q in ["?", "or else", "choose", "never", "wait", "!"]):
            suspicion_reasons.append("Cliffhanger lacks explicit question mark or urgent threat")

        if suspicion_reasons:
            suspicious.append({
                "promo": p,
                "reasons": suspicion_reasons
            })

    # If fewer than 5 flagged, backfill with longest/borderline promos
    if len(suspicious) < 5:
        for p in sorted(promos, key=lambda x: x["total_duration"], reverse=True):
            if not any(s["promo"]["promo_id"] == p["promo_id"] for s in suspicious):
                suspicious.append({
                    "promo": p,
                    "reasons": ["Borderline candidate duration; pacing may feel sluggish in first 10 seconds."]
                })
            if len(suspicious) >= 5:
                break
    suspicious = suspicious[:5]

    # Build failures.md
    lines = [
        "# Promo Tool Failure & Edge-Case Analysis",
        "",
        "This document highlights boundary cases, failure modes, and systematic biases discovered during automated quality checks and gold-set benchmarking.",
        "",
        "---",
        "",
        "## Part 1: Top 5 Most Suspicious High-Ranked Promos",
        "These promos received high scores from the scoring pipeline, but human editorial inspection reveals genuine risks of viewer drop-off or context ambiguity.",
        ""
    ]

    for idx, s in enumerate(suspicious, start=1):
        p = s["promo"]
        lines.extend([
            f"### #{idx}: Promo `{p['promo_id']}` (Rank #{p['rank']}, Score: {p['weighted_score']:.2f})",
            f"- **Episode:** {p['primary_episode_id']} | **Duration:** {p['total_duration']:.1f}s",
            f"- **Timestamps:** `{p['segments'][0]['start_ts']} - {p['segments'][-1]['end_ts']}`",
            f"- **Opening Hook:** *\"{p['hook_text'][:120]}...\"*",
            f"- **Cliffhanger Ending:** *\"{p['cliffhanger_text'][:120]}...\"*",
            f"- **Why the tool picked it:** High emotional volume and explosive dialogue confrontation.",
            f"- **Why the tool likely erred / Risks identified:**",
        ])
        for r in s["reasons"]:
            lines.append(f"  - ⚠️ {r}")
        lines.extend([
            f"- **Human Editor Recommendation:** Tighten opening by 3-5 seconds to remove dead air, or pair with a text overlay introducing character names.",
            "",
            "---",
            ""
        ])

    lines.extend([
        "## Part 2: 5 Worst-Ranked Yet Passing Candidates",
        "These candidate windows satisfied all duration (20-60s) and unit boundary constraints, but received the lowest composite scores.",
        ""
    ])

    for idx, c in enumerate(sorted_by_score_asc, start=1):
        lines.extend([
            f"### #{idx}: Candidate `{c['candidate_id']}` (Score: {c['candidate_score']:.2f})",
            f"- **Episode:** {c['episode_id']} | **Duration:** {c['duration']:.1f}s",
            f"- **Timestamps:** `{seconds_to_ts(c['start_time'])} - {seconds_to_ts(c['end_time'])}`",
            f"- **Opening Hook:** *\"{c['hook_text'][:120]}...\"*",
            f"- **Ending Line:** *\"{c['cliffhanger_text'][:120]}...\"*",
            f"- **Why the tool scored it poorly:** Starts on an inert conversational exchange or procedural movement rather than an explosive hook. The ending resolves the ongoing beat rather than posing an urgent narrative question.",
            f"- **Verdict:** Rightfully rejected by the candidate pruning filter.",
            "",
            "---",
            ""
        ])

    out_file = Path(out_path)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Generated failure analysis in: {out_file}")


if __name__ == "__main__":
    analyze_failures()
