# Project Assumptions & Problem Framing

This document records all operational assumptions made where the brief is silent or flexible.

---

## 1. Screenplay Format & Parsing (Phase 1)
- **Explicit Timestamps**: Every dialogue, action, camera direction, and sound effect unit in the provided dataset has explicit `Start: (MM:SS.ff) | End: (MM:SS.ff)` boundaries. Timestamps are parsed as floating-point seconds rounded to 2 decimal places.
- **Dialogue End Times**: If a future screenplay format omits line end timestamps, `end` will default to `next_unit.start` or `start + 2.0s`. In the current dataset, all units have explicit end timestamps.
- **Multi-Scene Structure**: Episodes frequently contain multiple scenes (up to 5 per episode, e.g., Ep 18, Ep 39). Scene transitions are continuous. Promo windows can span across scene boundaries within an episode if narrative continuity holds, or stay within a single high-tension scene.
- **Unit Classification**:
  - `dialogue`: Identified by character name headers (with optional emotional directions in parentheses).
  - `action`: Physical character or environmental actions.
  - `camera`: Camera positioning, movements, and angles.
  - `sound_fx`: Audio cues, musical stings, door slams, and sound effects.
- **Case Invariance**: Section tags (`SCENE HEADING`, `SCENE START`, `ACTIONS AND DIALOGUE`) are treated case-insensitively to accommodate script variations (e.g., Episode 6 vs Episode 1).
- **Validation Constraints**: Plausible microdrama episode length is defined as 30s to 240s. All 50 episodes in the dataset range between 70.5s (Ep 44) and 200.8s (Ep 36), with a mean duration of ~125s (~2.1 minutes).

---

## 2. Show Bible & Spoilers (Phase 2)
- **Show Identity**: *I Married a Broken Soldier. He was a Duke* (English-language microdrama, historical romance / secret identity / revenge genre).
- **Map-Reduce Aggregation**: To preserve free-tier context limits and avoid rate-limiting, episode summaries and key revelation points are generated per episode using the cheap model tier, and merged into a unified `bible.json` by the strong model tier.
- **Twist Revelation Tracking**: The central dramatic twist (the "crippled soldier" husband is actually the Duke of Ashburn) is unmasked in Episode 42. Promos designed for user acquisition (Episodes 1-10) must not reveal this climax directly unless specifically designated as mid-series teasers with high spoiler flags.

---

## 3. Candidate Windows & Promos (Phases 3-5)
- **Duration Constraints**: Valid promos must be strictly between 20.0s and 60.0s total duration.
- **Unit Boundary Rule**: Promo clip segments must START exactly on a unit start timestamp and END exactly on a unit end timestamp. No cutting mid-sentence or mid-action.
- **Start/End Selection Heuristics**:
  - Starts favor units with immediate dramatic impact: dialogue lines (accusations, questions, sudden declarations), sudden physical action, or scene openings. Pure camera tracking transitions or trailing sound effects are avoided as start points.
  - Ends favor cliffhanger moments: dialogue ending in questions or ultimatums, musical/sound stings, or the immediate cut before a scene change.
- **Sliding Step & Deduplication**:
  - Windows are enumerated at unit granularity across each episode.
  - Windows overlapping with an Intersection-over-Union (IoU) > 0.5 within an episode are deduplicated, retaining only the higher-scoring variant.
- **Top-N per Episode Cap**: Defaulted to top 8 candidates per episode to balance candidate diversity against downstream LLM judging costs (yielding ~388 candidates across 50 episodes).
- **Ranking Formula**: Weighted combination of `Hook Strength (35%)`, `Cliffhanger Quality (30%)`, `Standalone Clarity (20%)`, and `Emotional Pull (15%)`, with penalties/disqualifications for hard-fail flags (`starts_mid_thought`, `ends_resolved`, `spoils_major_twist`, `needs_missing_context`).
