# 🎬 3-Minute Video Walkthrough Script: Kuku Promo Finder

**Target Duration:** 3 minutes (180 seconds)  
**Format:** Loom / Screen Share with Webcam in Corner  
**Tone:** Confident, senior engineering, crisp, zero fluff  
**Screen Setup Required:**
1. VS Code / Terminal with workspace open (`c:\Users\arvin\Downloads\Kuku`)
2. Browser tab with Streamlit UI (`http://localhost:8501`)
3. `output/report.md` open in markdown preview

---

## ⏱️ Visual & Narration Cue Sheet

```
+-------------------------------------------------------------------------------------------------+
| Time           | Screen View                 | What You Do               | Audio / Spoken Script|
+-------------------------------------------------------------------------------------------------+
| 0:00 - 0:25    | VS Code: README.md / Title  | Look at camera            | Problem Framing      |
| 0:25 - 0:55    | Terminal: Powershell        | Run python run.py         | Live Pipeline Run    |
| 0:55 - 1:40    | VS Code: output/report.md   | Scroll & highlight promo  | Results Walkthrough  |
| 1:40 - 2:15    | Terminal: python checks.py  | Run checks & evaluate     | Quality & Gold Set   |
| 2:15 - 2:40    | Browser: Streamlit app.py   | Toggle role filters       | Editor UI Demo       |
| 2:40 - 3:00    | VS Code: SOLUTION_DOC.md    | Point to Scale section    | Scale, Cost & Wrap   |
+-------------------------------------------------------------------------------------------------+
```

---

## 🎙️ Timed Transcript & Screen Actions

### [0:00 – 0:25] 1. Problem Framing & Core Architecture (25s)
**Screen View:** VS Code displaying `README.md` or camera full screen.

> *"Hi everyone, I’m walking you through my solution for Problem 1: 'Find the Promos'.*  
> *Microdramas live or die by their user acquisition on TikTok and Reels. Today, video editors spend hours watching dozens of 1-to-2-minute episodes to find high-converting 30-second clips. My goal was to build a re-runnable, model-swappable tool that fully automates this discovery without ever trusting an LLM to invent timestamps.*  
> *I designed this around three core principles: mathematical boundary integrity enforced in code, a model-agnostic LLM interface supporting free-tier Gemini or Anthropic, and outputs tailored directly for campaign rollout."*

---

### [0:25 – 0:55] 2. Live Execution: One-Command Pipeline (30s)
**Screen View:** Terminal in `c:\Users\arvin\Downloads\Kuku`.  
**Action:** Type and execute the command live:
```bash
python run.py --input "data/I Married a Broken Soldier. He was a Duke" --out output
```

> *"Everything runs with a single command.*  
> *(Hit Enter, let output stream).*  
> *Under the hood, the pipeline runs in five deliberate stages:*  
> *First, pure Python regex parses all 50 episodes into 3,727 structured units—validating continuity and duration. Next, a map-reduce LLM pass synthesizes a unified Show Bible, mapping premise, character dynamics, and twist revelation episodes so we avoid late spoilers.*  
> *Third, a sliding window generator enumerates all 20 to 60-second windows snapping strictly to unit boundaries, pruning 18,000 raw windows down to top candidates.*  
> *Finally, our strong-tier judge evaluates the first 3 seconds for viral hook punch and the final seconds for an open cliffhanger cut, enforcing episode diversity."*

---

### [0:55 – 1:40] 3. Results Walkthrough: Top Promos & Campaign Strategy (45s)
**Screen View:** Open `output/report.md` (or `promos.csv`) side-by-side with preview.  
**Action:** Highlight Promo #1 (`ep01_u22_u52`) and Promo #5 (`ep04_u73_u92`).

> *"Here are our top ranked promos.*  
> *Look at Rank #1 from Episode 1. It’s a 47.2-second clip from thirty-three seconds to one minute twenty-one. Notice how the hook lands within the first 3 seconds: Lady Juliana gasps, 'Gerald? Why are you holding her hand?' while the camera reveals his fingers interlocked with her sister at the altar.*  
> *And the cliffhanger cuts right on Clarissa sneering, 'Long enough to know he was never going to marry you'—right before her father reacts. It’s an immediate, high-stakes emotional ambush with zero backstory needed.*  
> *We don't just dump timestamps; the tool classifies clips into **Series Launchers**—cold-acquisition hooks for Days 1 and 2—and **Mid-Series Teasers**, like Rank #10 in Episode 16 where Alexander slams an assassin into a stone wall demanding 'Who sent you?!'. Every timestamp is backed by exact screenplay dialogue."*

---

### [1:40 – 2:15] 4. Automated Quality Checks & Gold-Set Benchmark (35s)
**Screen View:** Switch to terminal.  
**Action:** Run the automated checks and gold set evaluation:
```bash
python checks.py
python evaluate.py
```

> *"Now, the most critical part of this assignment: quality verification.*  
> *(Run `python checks.py`)*  
> *`checks.py` mathematically verifies six constraints across every promo: duration between 20 and 60 seconds, zero internal overlaps, narrative ordering, and that every start and end timestamp exists in our parsed unit dictionary. We have a **100% pass rate**—zero hallucinated timestamps.*  
> *(Run `python evaluate.py`)*  
> *Next, I created a hand-labeled Gold Standard benchmark from five episodes without looking at tool outputs. Our tool achieved **80% recall in the Top 10**, **100% recall in the full candidate pool**, and a **0.752 mean IoU** temporal alignment. That proves the candidate sliding window captures the exact human editorial moments."*

---

### [2:15 – 2:40] 5. Human-in-the-Loop: Interactive Streamlit UI (25s)
**Screen View:** Switch to browser showing Streamlit (`streamlit run app.py`).  
**Action:** Click the role filter between "Series Launcher" and "Mid-Series Teaser", expand screenplay text.

> *"Here is how a human video editor actually uses this tool.*  
> *In our Streamlit review studio, editors can filter by campaign role, verify opening hook and cliffhanger cuts side-by-side, inspect live audit metrics, and expand the full parsed script with speaker highlights.*  
> *This turns an editor’s workflow from watching 50 episodes to reviewing 10 pre-curated, verified candidates in under five minutes."*

---

### [2:40 – 3:00] 6. Scale, Cost & Honest Limits (20s)
**Screen View:** Quick flash of `output/run_log.json` and `AI_FAILURES.md`.

> *"Finally, scale and cost. On Gemini 2.5 Flash, processing this entire 50-episode show costs less than **half a cent**—four-tenths of a cent. Scaling to 100 shows a week is just eighteen dollars total.*  
> *Where does it fail? It’s text-only. It can't see the actor's facial expression during the slap or hear the musical sting timing. With a multimodal model like Gemini Pro Video, we’d evaluate visual delivery directly.*  
> *The entire repo is clean, documented, fully tested with 28 passing unit tests, and ready to re-run on any new screenplay folder. Thank you!"*

---

## 💡 Quick Tips for Recording
- **Resolution:** 1080p (1920x1080) or 1440p
- **Window arrangement:** Keep terminal and VS Code split 50/50, or use desktop spaces
- **Command cheat sheet:** Keep `python run.py`, `python checks.py`, `python evaluate.py`, and `streamlit run app.py` pre-typed in terminal history so you can just press Up-Arrow and Enter.
