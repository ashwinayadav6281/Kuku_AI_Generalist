"""
evaluate.py - Benchmark promo tool output against a hand-labeled Gold Standard set.

Metrics computed:
1. Temporal IoU (Intersection over Union) of segment timestamps.
2. Recall of hand-labeled gold picks in the tool's Top 10.
3. Recall of gold picks in the broader candidate pool.
4. Precision of the tool's Top 10 picks against human expert labels.
5. Mean IoU of matched clips.
"""

import csv
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List

from screenplay_parser import ts_to_seconds, seconds_to_ts


def compute_iou(start_a: float, end_a: float, start_b: float, end_b: float) -> tuple:
    """Compute temporal intersection over union between two intervals."""
    i_start = max(start_a, start_b)
    i_end = min(end_a, end_b)
    intersection = max(0.0, i_end - i_start)
    union = (end_a - start_a) + (end_b - start_b) - intersection
    iou = intersection / union if union > 0 else 0.0
    return round(iou, 3), round(intersection, 2)


def evaluate_gold_set(
    gold_csv_path: str = "gold_template.csv",
    promos_json_path: str = "output/promos.json",
    candidates_json_path: str = "output/candidates.json",
    iou_threshold: float = 0.40
) -> Dict[str, Any]:
    # 1. Load gold set
    gold_picks = []
    with open(gold_csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            gold_picks.append({
                "gold_id": f"GOLD_{idx+1}",
                "episode": int(row["episode"]),
                "start_s": ts_to_seconds(row["start_ts"]),
                "end_s": ts_to_seconds(row["end_ts"]),
                "start_ts": row["start_ts"],
                "end_ts": row["end_ts"],
                "hook_desc": row.get("hook_description", ""),
                "cliff_desc": row.get("cliffhanger_description", ""),
                "notes": row.get("editorial_notes", "")
            })

    # 2. Load tool's top 10 promos
    with open(promos_json_path, "r", encoding="utf-8") as f:
        promos = json.load(f)

    # 3. Load all candidates (if available) for candidate pool recall
    all_candidates = []
    if Path(candidates_json_path).exists():
        with open(candidates_json_path, "r", encoding="utf-8") as f:
            all_candidates = json.load(f)

    # 4. Match Gold Picks against Top 10 Promos
    matches_top10 = []
    gold_matched_in_top10 = set()
    promos_matched = set()

    for g in gold_picks:
        best_match = None
        best_iou = 0.0
        best_overlap = 0.0

        for p in promos:
            p_ep = p["primary_episode_id"]
            if p_ep == g["episode"]:
                p_start = p["segments"][0]["start"]
                p_end = p["segments"][-1]["end"]
                iou, overlap = compute_iou(g["start_s"], g["end_s"], p_start, p_end)
                if iou > best_iou:
                    best_iou = iou
                    best_overlap = overlap
                    best_match = p

        if best_match and (best_iou >= iou_threshold or best_overlap >= 15.0):
            gold_matched_in_top10.add(g["gold_id"])
            promos_matched.add(best_match["promo_id"])
            matches_top10.append({
                "gold_id": g["gold_id"],
                "episode": g["episode"],
                "gold_interval": f"{g['start_ts']} - {g['end_ts']}",
                "tool_promo_id": best_match["promo_id"],
                "tool_rank": best_match["rank"],
                "tool_interval": f"{best_match['segments'][0]['start_ts']} - {best_match['segments'][-1]['end_ts']}",
                "iou": best_iou,
                "overlap_seconds": best_overlap,
                "status": "MATCH"
            })
        else:
            matches_top10.append({
                "gold_id": g["gold_id"],
                "episode": g["episode"],
                "gold_interval": f"{g['start_ts']} - {g['end_ts']}",
                "tool_promo_id": best_match["promo_id"] if best_match else "NONE",
                "tool_rank": best_match["rank"] if best_match else None,
                "tool_interval": f"{best_match['segments'][0]['start_ts']} - {best_match['segments'][-1]['end_ts']}" if best_match else "NONE",
                "iou": best_iou,
                "overlap_seconds": best_overlap,
                "status": "MISSED_IN_TOP10"
            })

    # 5. Check Gold Recall in Candidate Pool
    gold_matched_in_pool = set()
    for g in gold_picks:
        for c in all_candidates:
            if c["episode_id"] == g["episode"]:
                iou, overlap = compute_iou(g["start_s"], g["end_s"], c["start_time"], c["end_time"])
                if iou >= iou_threshold or overlap >= 15.0:
                    gold_matched_in_pool.add(g["gold_id"])
                    break

    # Calculate metrics
    num_gold = len(gold_picks)
    recall_top10 = (len(gold_matched_in_top10) / num_gold * 100) if num_gold > 0 else 0.0
    recall_pool = (len(gold_matched_in_pool) / num_gold * 100) if num_gold > 0 else 0.0

    # Precision: Top 10 promos that belong to gold episodes and match gold picks
    gold_episodes = {g["episode"] for g in gold_picks}
    top10_in_gold_eps = [p for p in promos if p["primary_episode_id"] in gold_episodes]
    precision_top10 = (len(promos_matched) / len(top10_in_gold_eps) * 100) if top10_in_gold_eps else 0.0

    matched_ious = [m["iou"] for m in matches_top10 if m["status"] == "MATCH"]
    mean_iou = (sum(matched_ious) / len(matched_ious)) if matched_ious else 0.0

    report = {
        "gold_picks_count": num_gold,
        "recall_in_top_10_percent": round(recall_top10, 2),
        "recall_in_candidate_pool_percent": round(recall_pool, 2),
        "precision_in_gold_episodes_percent": round(precision_top10, 2),
        "mean_iou_of_matches": round(mean_iou, 3),
        "match_details": matches_top10
    }
    return report


def main():
    parser = argparse.ArgumentParser(description="Evaluate tool promos against gold hand-labeled set.")
    parser.add_argument("--gold", default="gold_template.csv", help="Path to gold_template.csv")
    parser.add_argument("--promos", default="output/promos.json", help="Path to promos.json")
    parser.add_argument("--candidates", default="output/candidates.json", help="Path to candidates.json")
    parser.add_argument("--out", default="output/gold_evaluation.json", help="Path to write evaluation report")
    args = parser.parse_args()

    report = evaluate_gold_set(args.gold, args.promos, args.candidates)
    
    out_file = Path(args.out)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\n============================================================")
    print("GOLD-SET BENCHMARK EVALUATION")
    print("============================================================")
    print(f"Total Gold Standard Picks:     {report['gold_picks_count']}")
    print(f"Recall in Top 10 Promos:       {report['recall_in_top_10_percent']:.1f}%")
    print(f"Recall in Full Candidate Pool: {report['recall_in_candidate_pool_percent']:.1f}%")
    print(f"Precision in Gold Episodes:    {report['precision_in_gold_episodes_percent']:.1f}%")
    print(f"Mean IoU (Temporal Alignment): {report['mean_iou_of_matches']:.3f}")
    print("\nDetailed Alignment Table:")
    for m in report["match_details"]:
        icon = "[MATCH]" if m["status"] == "MATCH" else "[MISS] "
        print(f"  {icon} {m['gold_id']} (Ep{m['episode']}): Gold [{m['gold_interval']}] vs Tool Rank #{m['tool_rank']} [{m['tool_interval']}] -> IoU: {m['iou']:.2f}")
    print(f"\nReport saved to: {out_file}\n")


if __name__ == "__main__":
    main()
