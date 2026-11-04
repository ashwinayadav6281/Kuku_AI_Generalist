"""
checks.py - Automated quality and integrity checks for generated promos.

Verifies:
1. Duration constraint: 20.0s <= total_duration <= 60.0s.
2. Boundary constraint: Every start and end timestamp aligns with parsed unit boundaries.
3. Authenticity: Every timestamp exists in the parsed screenplay (zero hallucinated timestamps).
4. No overlaps: Multiple segments within a promo do not overlap each other.
5. Chronological order: Segments progress in valid narrative/chronological order.
6. Schema completeness: All required fields present and valid.

Outputs pass rate and writes audit report.
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List


REQUIRED_PROMO_FIELDS = [
    "rank",
    "promo_id",
    "primary_episode_id",
    "segments",
    "total_duration",
    "hook_text",
    "cliffhanger_text",
    "weighted_score",
    "hook_strength",
    "cliffhanger_quality",
    "standalone_clarity",
    "emotional_pull",
    "why_it_works",
]


def run_checks(promos_path: str = "output/promos.json", parsed_units_path: str = "output/parsed_units.json") -> Dict[str, Any]:
    with open(promos_path, "r", encoding="utf-8") as f:
        promos = json.load(f)

    with open(parsed_units_path, "r", encoding="utf-8") as f:
        parsed_units = json.load(f)

    # Build lookup table of valid unit boundaries per episode: {ep_id: set(starts), set(ends)}
    valid_starts = {}
    valid_ends = {}
    for ep_str, u_list in parsed_units.items():
        ep_id = int(ep_str)
        valid_starts[ep_id] = {round(u["start"], 2) for u in u_list}
        valid_ends[ep_id] = {round(u["end"], 2) for u in u_list}

    results = []
    failed_checks = []

    for p in promos:
        p_id = p.get("promo_id", "unknown")
        checks = {
            "promo_id": p_id,
            "rank": p.get("rank", 0),
            "duration_valid": False,
            "boundaries_valid": True,
            "timestamps_exist_in_parse": True,
            "no_internal_overlaps": True,
            "chronological_order": True,
            "schema_valid": True,
        }

        # 1. Schema check
        for field in REQUIRED_PROMO_FIELDS:
            if field not in p:
                checks["schema_valid"] = False
                failed_checks.append(f"{p_id}: Missing required schema field '{field}'")

        # 2. Duration check (20-60s)
        dur = p.get("total_duration", 0.0)
        if 20.0 <= dur <= 60.0:
            checks["duration_valid"] = True
        else:
            failed_checks.append(f"{p_id}: Duration {dur:.2f}s outside valid 20.0s-60.0s range")

        # 3. Segments verification
        segments = p.get("segments", [])
        if not segments:
            checks["schema_valid"] = False
            failed_checks.append(f"{p_id}: No segments defined")
        
        prev_ep = -1
        prev_end = -1.0
        calculated_total_dur = 0.0

        for seg_idx, seg in enumerate(segments):
            ep = seg.get("episode")
            start = round(seg.get("start", 0.0), 2)
            end = round(seg.get("end", 0.0), 2)
            seg_dur = round(end - start, 2)
            calculated_total_dur += seg_dur

            # Authenticity check
            if ep not in valid_starts or start not in valid_starts[ep]:
                checks["timestamps_exist_in_parse"] = False
                checks["boundaries_valid"] = False
                failed_checks.append(f"{p_id} seg{seg_idx}: Start time {start}s does not match any parsed unit in Ep{ep}")

            if ep not in valid_ends or end not in valid_ends[ep]:
                checks["timestamps_exist_in_parse"] = False
                checks["boundaries_valid"] = False
                failed_checks.append(f"{p_id} seg{seg_idx}: End time {end}s does not match any parsed unit in Ep{ep}")

            # Ordering and overlap checks
            if ep < prev_ep:
                checks["chronological_order"] = False
                failed_checks.append(f"{p_id} seg{seg_idx}: Regresses to earlier episode {ep} from {prev_ep}")
            elif ep == prev_ep:
                if start < prev_end:
                    checks["no_internal_overlaps"] = False
                    failed_checks.append(f"{p_id} seg{seg_idx}: Start {start}s overlaps previous segment end {prev_end}s")
                if start <= prev_end:
                    checks["chronological_order"] = False

            prev_ep = ep
            prev_end = end

        # Verify sum of segment durations matches total_duration
        if abs(calculated_total_dur - dur) > 0.05:
            checks["duration_valid"] = False
            failed_checks.append(f"{p_id}: Stated total duration ({dur}s) != sum of segments ({calculated_total_dur}s)")

        # Overall pass for this promo
        checks["all_passed"] = all([
            checks["duration_valid"],
            checks["boundaries_valid"],
            checks["timestamps_exist_in_parse"],
            checks["no_internal_overlaps"],
            checks["chronological_order"],
            checks["schema_valid"],
        ])
        results.append(checks)

    total_promos = len(promos)
    passed_promos = sum(1 for r in results if r["all_passed"])
    pass_rate = (passed_promos / total_promos * 100) if total_promos > 0 else 0.0

    report = {
        "total_promos_checked": total_promos,
        "promos_passed": passed_promos,
        "promos_failed": total_promos - passed_promos,
        "pass_rate_percent": round(pass_rate, 2),
        "failures": failed_checks,
        "check_details": results
    }

    return report


def main():
    parser = argparse.ArgumentParser(description="Automated quality checks for promo clips.")
    parser.add_argument("--promos", default="output/promos.json", help="Path to promos.json")
    parser.add_argument("--parsed", default="output/parsed_units.json", help="Path to parsed_units.json")
    parser.add_argument("--out", default="output/checks_report.json", help="Path to write checks report")
    args = parser.parse_args()

    print(f"Running automated quality checks on {args.promos}...")
    report = run_checks(args.promos, args.parsed)

    out_file = Path(args.out)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n============================================================")
    print(f"AUTOMATED QUALITY CHECK RESULTS")
    print(f"============================================================")
    print(f"Total Promos Checked: {report['total_promos_checked']}")
    print(f"Passed All Checks:    {report['promos_passed']} / {report['total_promos_checked']}")
    print(f"Pass Rate:            {report['pass_rate_percent']:.1f}%")
    
    if report["failures"]:
        print(f"\nFAILED CHECKS ({len(report['failures'])}):")
        for f in report["failures"]:
            print(f"  ❌ {f}")
    else:
        print("\nAll quality checks PASSED with 0 errors!")
    print(f"Report written to: {out_file}\n")


if __name__ == "__main__":
    main()
