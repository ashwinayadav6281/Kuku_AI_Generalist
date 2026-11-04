# 🎬 Kuku Microdrama Promo Finder (Problem 1)

> **Automated promo discovery tool for short-form episodic microdramas (TikTok, Instagram Reels, YouTube Shorts).**  
> Identifies high-converting 20–60s promo moments with immediate 3-second hooks, unresolved cliffhangers, and verified unit-boundary timestamps.

---

## 🚀 Key Highlights & Architectural Strengths
1. **Mathematical Timestamp Authenticity**: The LLM **never** invents or formats timestamps. Every timestamp is parsed from structured screenplay units by code, snapping strictly to unit boundaries.
2. **Model-Swappable Abstraction (`llm.py`)**: One unified call interface with pluggable support for **Gemini (default free tier)**, **OpenAI / OpenAI-compatible endpoints**, **Anthropic**, and an offline fallback mode (`LLM_OFFLINE_FALLBACK=1`).
3. **Robust to Format Variations**: Screenplay parser handles case differences (`SCENE HEADING` vs `Scene heading`), multi-scene episodes, and variable unit types (`dialogue`, `action`, `camera`, `sound_fx`), failing loudly on unknown inputs.
4. **Constrained Multi-Segment Stitching (`--stitch`)**: When a climactic scene requires setup context, code searches for pre-verified 5–15s preceding segments. The LLM only picks pre-approved segment IDs; code enforces narrative ordering and $\le 60$s duration.
5. **Quality Checking & Gold-Set Evaluation**:
   - Automated boundary and integrity checks: **100.0% pass rate** on all generated promos.
   - Hand-labeled Gold Standard benchmark: **80.0% recall in Top 10** (100% in candidate pool), with a **0.878 Mean IoU** temporal alignment.
   - Stability test: **100.0% Top-10 agreement** across independent runs with disk caching.

---

## 📂 Repository Structure

```
├── run.py                    # Unified CLI runner (1 command for full pipeline)
├── screenplay_parser.py      # Core parser converting .txt scripts into structured units
├── parser.py                 # CLI wrapper satisfying assignment naming
├── bible_builder.py          # Map-reduce show bible synthesizer
├── candidate_generator.py    # Sliding window candidate generator (20-60s) & scoring
├── stitcher.py               # Constrained multi-segment stitching engine
├── judge_and_rank.py         # Strong-tier LLM judge, deduplication, diversity & ranking
├── checks.py                 # Automated quality and boundary checks (duration, IoU, order)
├── evaluate.py               # Benchmark tool output against hand-labeled Gold Set
├── stability_test.py         # Dual-run judging stability and rank shift test
├── failure_analyzer.py       # Automated extractor of worst-passing & suspicious promos
├── app.py                    # Streamlit interactive UI for video editors
├── config.yaml               # Centralized configuration (models, weights, thresholds)
├── .env.example              # Environment variables template
├── requirements.txt          # Python dependencies
├── gold_template.csv         # Hand-labeled gold standard benchmark set
├── ASSUMPTIONS.md            # Documented operational assumptions
├── AI_FAILURES.md            # Running log of real AI failures encountered during development
├── failures.md               # Analysis of 5 worst-ranked and 5 most suspicious promos
├── SOLUTION_DOC.md           # 2-page hiring assignment submission synthesis
├── notebook_run.ipynb        # Google Colab notebook for cloud execution
├── prompts/                  # Externalized, versioned prompt templates
│   ├── show_bible_v1.txt
│   ├── scene_tagging_v1.txt
│   ├── stitching_v1.txt
│   ├── judge_rubric_v1.txt
│   └── ranking_justification_v1.txt
├── tests/                    # Automated unit tests (28 tests passing)
│   ├── test_parser.py
│   ├── test_llm.py
│   ├── test_bible_builder.py
│   ├── test_candidate_generator.py
│   ├── test_judge_and_rank.py
│   └── test_quality_checks.py
└── output/                   # Generated artifacts (cached & reproducible)
    ├── promos.json           # Machine-readable promos with segments, scores, flags
    ├── promos.csv            # Tabular export for video editors
    ├── report.md             # Formatted executive breakdown of Top 10 promos
    ├── run_log.json          # Cost accounting, latency, and scale projection
    ├── bible.json            # Generated show bible
    ├── candidates.json       # Top candidate windows across all episodes
    ├── checks_report.json    # Automated validation audit (100% pass rate)
    └── gold_evaluation.json  # Benchmark metrics vs gold standard
```

---

## 🛠️ Quickstart & Installation

### 1. Clone & Install Dependencies
```bash
git clone <repo-url>
cd Kuku
pip install -r requirements.txt
```

### 2. Configure API Keys
Copy `.env.example` to `.env` and insert your Gemini API key (or export directly):
```bash
cp .env.example .env
# Edit .env:
# GEMINI_API_KEY=your_key_here
```
*(Note: To run offline in dry-run mode without external API calls, set `export LLM_OFFLINE_FALLBACK=1`)*.

---

## ⚡ Running the Tool

### Run on the Included Show (Full 50 Episodes)
```bash
python run.py --input "data/I Married a Broken Soldier. He was a Duke" --out output
```

### Run on a NEW Input Folder (For Live Interview Evaluation)
```bash
python run.py --input path/to/new_show_folder --out output_new
```

### Optional: Enable Multi-Segment Stitching
```bash
python run.py --input "data/I Married a Broken Soldier. He was a Duke" --out output --stitch
```

---

## 🧪 Verification & Quality Benchmarks

### 1. Run Complete Automated Test Suite (28 Tests)
```bash
pytest tests -v
```

### 2. Run Automated Quality Checks
```bash
python checks.py --promos output/promos.json --parsed output/parsed_units.json
```

### 3. Run Gold-Set Evaluation
```bash
python evaluate.py --gold gold_template.csv --promos output/promos.json
```

### 4. Run Judging Stability Test
```bash
python stability_test.py
```

### 5. Run Suspicious & Worst-Ranked Failure Analysis
```bash
python failure_analyzer.py
```

---

## 🖥️ Interactive Video Editor Viewer (Streamlit)

Launch the editor UI to inspect ranked promos with segment timestamps and screenplay dialogue side-by-side:
```bash
streamlit run app.py
```

---

## ⚙️ Model Swapping & Configuration

Model choices and weights are centralized in `config.yaml`:
```yaml
llm:
  provider: "gemini"            # "gemini" | "openai" | "anthropic" | "mock"
  cheap_model: "gemini-2.5-flash"
  strong_model: "gemini-2.5-flash"
  use_cache: true

ranking:
  weights:
    hook_strength: 0.35
    cliffhanger_quality: 0.30
    standalone_clarity: 0.20
    emotional_pull: 0.15
  top_n: 10
  max_promos_per_episode: 2     # Enforce episode diversity
```
To use an OpenAI-compatible endpoint (e.g. OpenRouter, Groq, Ollama):
```bash
export LLM_PROVIDER=openai
export OPENAI_API_KEY=your_key
export OPENAI_BASE_URL=https://api.openai.com/v1
```
