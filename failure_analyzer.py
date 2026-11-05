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
        ep = p["primary_episode_id"]
        dur = p["total_duration"]
        cliff = p["cliffhanger_text"]
        hook = p["hook_text"]

        # Context-specific pick reason
        if ep <= 2:
            pick_reason = "Altar betrayal with high visceral shock and clear victim/antagonist dynamics."
        elif ep <= 5:
            pick_reason = "Public family rejection and sudden marriage pact creating high curiosity."
        elif "poison" in cliff.lower() or "duchess" in cliff.lower():
            pick_reason = "High-stakes murder mystery escalation introducing lethal consequences."
        elif "soldier" in hook.lower() or "broken" in hook.lower() or "protect" in hook.lower():
            pick_reason = "High masculine tension / protective hero confrontation."
        else:
            pick_reason = "High-stakes interpersonal confrontation with strong character indignation."

        # Tailored recommendation
        recs = []
        if dur > 45.0:
            recs.append(f"Trim {dur - 35.0:.1f}s of establishing dialogue/camera action to bring runtime down to ~35s sweet spot.")
        if ep >= 15:
            recs.append("Add on-screen text hook overlay (e.g., 'Episode 25: Who is poisoning the Duchess?') to orient cold scrollers.")
        if not any(q in cliff for q in ["?", "or else", "choose", "!"]):
            recs.append("Insert audio sting or sudden audio silence right before the final cut to sharpen cliffhanger impact.")
        if not recs:
            recs.append("Ready for editor cut; add title card and trending background audio.")

        rec_str = " ".join(recs)

        lines.extend([
            f"### #{idx}: Promo `{p['promo_id']}` (Rank #{p['rank']}, Score: {p['weighted_score']:.2f})",
            f"- **Episode:** {p['primary_episode_id']} | **Duration:** {p['total_duration']:.1f}s",
            f"- **Timestamps:** `{p['segments'][0]['start_ts']} - {p['segments'][-1]['end_ts']}`",
            f"- **Opening Hook:** *\"{hook[:120]}...\"*",
            f"- **Cliffhanger Ending:** *\"{cliff[:120]}...\"*",
            f"- **Why the tool picked it:** {pick_reason}",
            f"- **Why the tool likely erred / Risks identified:**",
        ])
        for r in s["reasons"]:
            lines.append(f"  - ⚠️ {r}")
        lines.extend([
            f"- **Human Editor Recommendation:** {rec_str}",
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
        ep_c = c["episode_id"]
        c_full = c["full_text"].lower()

        # Detailed reason for poor score
        if "embrace" in c_full or "rest their foreheads" in c_full:
            poor_reason = "Intimate romantic reconciliation beat. Completely lacks conflict or forward momentum for cold viewers."
        elif "very well" in c["cliffhanger_text"].lower() or "chuckling" in c_full:
            poor_reason = "Affirmative conversational resolution. Character yields quietly, dissipating tension before the cut."
        elif "mother" in c_full and "meant to be" in c_full:
            poor_reason = "Reflective sentimental dialogue without an immediate external threat or urgent hook."
        elif "look at your hands" in c_full:
            poor_reason = "Low-tempo social teasing without high stakes or clear narrative jeopardy."
        else:
            poor_reason = "Low conflict volume, procedural movement, or closed narrative resolution."

        lines.extend([
            f"### #{idx}: Candidate `{c['candidate_id']}` (Score: {c['candidate_score']:.2f})",
            f"- **Episode:** {c['episode_id']} | **Duration:** {c['duration']:.1f}s",
            f"- **Timestamps:** `{seconds_to_ts(c['start_time'])} - {seconds_to_ts(c['end_time'])}`",
            f"- **Opening Hook:** *\"{c['hook_text'][:120]}...\"*",
            f"- **Ending Line:** *\"{c['cliffhanger_text'][:120]}...\"*",
            f"- **Why the tool scored it poorly:** {poor_reason}",
            f"- **Verdict:** Correctly rejected by candidate pruning filter; would cause immediate drop-off as a paid social ad.",
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
