"""
run.py - Main CLI entrypoint for Kuku Microdrama Promo Finder.

Usage:
    python run.py --input <path_to_scripts_folder> --out <path_to_output_folder> [--stitch]
"""

import sys
import os
import argparse
import time
from pathlib import Path

from screenplay_parser import parse_folder
from bible_builder import build_bible
from candidate_generator import run_candidate_generation
from judge_and_rank import run_judging_and_ranking


def main():
    parser = argparse.ArgumentParser(description="Find the best promotional clips from microdrama screenplays.")
    parser.add_argument("--input", required=True, help="Folder containing episode .txt screenplay files")
    parser.add_argument("--out", default="output", help="Output directory for generated promos, reports, and logs")
    parser.add_argument("--stitch", action="store_true", help="Enable multi-segment stitching for high-context clips")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    args = parser.parse_args()

    overall_start = time.time()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(" KUKU MICRODRAMA PROMO FINDER (PROBLEM 1)")
    print(f" Input:  {args.input}")
    print(f" Output: {args.out}")
    print(f" Multi-Segment Stitching: {'ENABLED' if args.stitch else 'DISABLED'}")
    print("=" * 70)

    # ── Phase 1: Parse Screenplays ──────────────────────────────────
    print("\n[PHASE 1/5] Parsing screenplay files and extracting structured units...")
    metas, units_by_ep, parse_report = parse_folder(args.input)
    print(f"Parsed {parse_report.total_episodes} episodes ({parse_report.total_units} total units).")

    parsed_units_path = out_dir / "parsed_units.json"
    import json
    from dataclasses import asdict
    with open(parsed_units_path, "w", encoding="utf-8") as f:
        json.dump({str(k): [asdict(u) for u in v] for k, v in units_by_ep.items()}, f, indent=2)

    meta_path = out_dir / "episode_meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump([asdict(m) for m in metas], f, indent=2)

    parse_report_path = out_dir / "parse_report.json"
    with open(parse_report_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_episodes": parse_report.total_episodes,
            "total_units": parse_report.total_units,
            "warnings": parse_report.warnings,
            "errors": parse_report.errors,
        }, f, indent=2)

    # ── Phase 2: Show Bible ─────────────────────────────────────────
    print("\n[PHASE 2/5] Synthesizing Show Bible (premise, characters, central twists)...")
    bible_path = out_dir / "bible.json"
    bible = build_bible(meta_path=str(meta_path), out_path=str(bible_path))

    # ── Phase 3: Candidate Generation ──────────────────────────────
    print("\n[PHASE 3/5] Generating and filtering candidate windows (20s - 60s)...")
    candidates_path = out_dir / "candidates.json"
    run_candidate_generation(
        parsed_units_path=str(parsed_units_path),
        bible_path=str(bible_path),
        out_path=str(candidates_path),
        config_path=args.config
    )

    # ── Phase 4 & 5: Judging, Deduplication, and Ranking ───────────
    print(f"\n[PHASE 4 & 5] Judging, deduplicating, enforcing diversity, and ranking promos...")
    ranked_promos = run_judging_and_ranking(
        candidates_path=str(candidates_path),
        bible_path=str(bible_path),
        parsed_units_path=str(parsed_units_path),
        out_dir=str(out_dir),
        enable_stitch=args.stitch,
        config_path=args.config
    )

    elapsed = round(time.time() - overall_start, 2)
    print("\n" + "=" * 70)
    print(f" PIPELINE COMPLETE in {elapsed}s")
    print(f" Top {len(ranked_promos)} Promos Generated:")
    for p in ranked_promos[:5]:
        print(f"  #{p.rank:02d} [{p.promo_role}] Ep{p.primary_episode_id:02d} ({p.total_duration:.1f}s) Score: {p.weighted_score:.2f} | {p.hook_text[:60]}...")
    print("=" * 70)
    print(f"\nDeliverable files saved in: {out_dir}/")
    print(f"  - report.md   (Editor-friendly layout)")
    print(f"  - promos.json (Full machine-readable promos with segments & scores)")
    print(f"  - promos.csv  (Tabular export for video editors)")
    print(f"  - run_log.json(Audit metrics, tokens, latency, cost projection)")


if __name__ == "__main__":
    main()
