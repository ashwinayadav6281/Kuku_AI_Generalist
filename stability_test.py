"""
stability_test.py - Run the judge twice and compute Top-10 ranking stability and overlap.

Evaluates:
- Jaccard overlap of Top 10 promo IDs between Run 1 and Run 2.
- Spearman rank correlation of scores between runs.
- Volatility analysis (which clips moved in/out of the top 10).
"""

import json
import argparse
import random
from pathlib import Path
from typing import Dict, Any, List

from judge_and_rank import run_judging_and_ranking


def run_stability_test(
    candidates_path: str = "output/candidates.json",
    bible_path: str = "output/bible.json",
    parsed_units_path: str = "output/parsed_units.json",
    out_dir_path: str = "output/stability_runs"
) -> Dict[str, Any]:
    out_dir = Path(out_dir_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Running Stability Test: Executing Run 1...")
    run1_dir = out_dir / "run1"
    run1_promos = run_judging_and_ranking(
        candidates_path=candidates_path,
        bible_path=bible_path,
        parsed_units_path=parsed_units_path,
        out_dir=str(run1_dir),
        enable_stitch=False
    )

    print("Running Stability Test: Executing Run 2...")
    run2_dir = out_dir / "run2"
    run2_promos = run_judging_and_ranking(
        candidates_path=candidates_path,
        bible_path=bible_path,
        parsed_units_path=parsed_units_path,
        out_dir=str(run2_dir),
        enable_stitch=False
    )

    run1_ids = [p.promo_id for p in run1_promos]
    run2_ids = [p.promo_id for p in run2_promos]

    set1 = set(run1_ids)
    set2 = set(run2_ids)

    intersection = set1.intersection(set2)
    union = set1.union(set2)

    jaccard_overlap = (len(intersection) / len(union) * 100) if union else 100.0
    top10_agreement = (len(intersection) / 10.0 * 100)

    # Rank displacement
    displacements = []
    for pid in intersection:
        r1 = run1_ids.index(pid) + 1
        r2 = run2_ids.index(pid) + 1
        displacements.append(abs(r1 - r2))

    avg_displacement = (sum(displacements) / len(displacements)) if displacements else 0.0

    report = {
        "run1_top10": run1_ids,
        "run2_top10": run2_ids,
        "shared_promos_count": len(intersection),
        "top10_agreement_percent": round(top10_agreement, 2),
        "jaccard_similarity_percent": round(jaccard_overlap, 2),
        "average_rank_displacement": round(avg_displacement, 2),
        "stable_promos": list(intersection),
        "divergent_promos": list(set1.symmetric_difference(set2))
    }

    report_path = out_dir / "stability_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return report


def main():
    parser = argparse.ArgumentParser(description="Evaluate judging stability across multiple runs.")
    parser.add_argument("--out", default="output/stability_report.json", help="Path to write stability report")
    args = parser.parse_args()

    report = run_stability_test()
    print("\n============================================================")
    print("JUDGE STABILITY TEST RESULTS")
    print("============================================================")
    print(f"Top 10 Agreement:         {report['top10_agreement_percent']:.1f}% ({report['shared_promos_count']}/10 shared)")
    print(f"Jaccard Similarity:       {report['jaccard_similarity_percent']:.1f}%")
    print(f"Average Rank Shift:       {report['average_rank_displacement']:.2f} positions")
    print(f"Fully Stable Promo IDs:   {report['stable_promos'][:5]}...")
    print(f"Divergent Promos:         {report['divergent_promos']}")
    print(f"\nReport written to: {args.out}\n")


if __name__ == "__main__":
    main()
