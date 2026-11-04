"""
bible_builder.py - Generate the show bible (premise, characters, central twists/spoilers).
Uses map-reduce: gathers per-episode loglines/continuity, feeds into strong-tier LLM.
Saves to output/bible.json.
"""

import json
from pathlib import Path
from typing import Dict, Any, List

from llm import call_llm


BIBLE_SCHEMA = {
    "required": ["title", "genre", "tone", "premise", "main_characters", "central_twists"]
}


def load_prompt_template(template_name: str = "show_bible_v1.txt") -> str:
    path = Path("prompts") / template_name
    if not path.exists():
        raise FileNotFoundError(f"Prompt template missing: {path}")
    return path.read_text(encoding="utf-8")


def build_bible(meta_path: str = "output/episode_meta.json", out_path: str = "output/bible.json") -> Dict[str, Any]:
    with open(meta_path, "r", encoding="utf-8") as f:
        metas = json.load(f)

    # Compile condensed episode summaries
    summary_lines = []
    for m in metas:
        ep_num = m["episode_id"]
        logline = m.get("logline", "")
        continuity = m.get("continuity_notes", "")
        summary_lines.append(f"Episode {ep_num:02d}: {logline} [Continuity: {continuity}]")

    episodes_text = "\n".join(summary_lines)

    template = load_prompt_template("show_bible_v1.txt")
    prompt = template.format(episode_summaries=episodes_text)

    print(f"Building Show Bible across {len(metas)} episodes using strong-tier LLM...")
    bible_data = call_llm(prompt, schema=BIBLE_SCHEMA, tier="strong")

    # Save bible
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(bible_data, f, indent=2)

    print(f"Show Bible successfully saved to {out_file}")
    return bible_data


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate show bible from parsed episode metadata.")
    parser.add_argument("--meta", default="output/episode_meta.json", help="Path to episode_meta.json")
    parser.add_argument("--out", default="output/bible.json", help="Path to save bible.json")
    args = parser.parse_args()

    build_bible(args.meta, args.out)
