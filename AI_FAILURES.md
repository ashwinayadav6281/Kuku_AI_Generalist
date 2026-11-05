# AI Failure Log

This log tracks every occurrence where an AI model/step produced a flawed, hallucinated, or unparseable output during development and evaluation, alongside root-cause analysis and the protective code safeguards applied.

---

| Incident # | Stage | Model / Tool | Observed Failure | Root Cause | Code / Prompt Safeguard Applied |
|---|---|---|---|---|---|
| **Incident 1** | *Phase 1 (Parsing)* | *Rule-based Regex* | `ACTIONS AND DIALOGUE:` caused unrecognised line warning in Ep 6 | Upstream human script formatting used uppercase `ACTIONS AND DIALOGUE:` and `SCENE HEADING:` in Ep 6 whereas Ep 1 used Title Case | Standardized string normalization (`sl.lower()`) across all screenplay header matchers |
| **Incident 2** | *Phase 5 (Judging)* | *LLM Dispatcher / Mock* | Schema validation failure (`Missing required fields: ['reasoning', 'hook_strength', ...]`) causing retry loop | In prompt templates that include the show premise (`Premise: {premise}`), the prompt matched the `'premise'` substring before `'hook_strength'`, erroneously returning bible JSON instead of judge scores | Reordered dispatch matching in `llm.py` to prioritize specific rubric criteria and added explicit schema key inspection (`schema['required']`) |
| **Incident 3** | *Phase 3 (Candidate Tagging)* | *Heuristic / Cheap Tier Tagger* | Casual conversational lines containing "Why" or "Who" received `hook_potential = 4` | Simple substring matching on question words ("why", "who") failed to differentiate calm exposition from dramatic confrontation | Enhanced hook matching to require emotional character directions `(Outraged)`, `(Sneering)`, or explicit high-status conflict verbs |
| **Incident 4** | *Phase 3 & 5 (Window Ranking)* | *Candidate Scoring Heuristic* | 48s–55s promos ranked equally with 28s promos despite higher drop-off risk | Early version treated the entire 20s–60s duration window with a flat linear weight, ignoring short-form retention curves | Implemented a non-linear TikTok duration sweet-spot curve (+0.25 bonus for 25–38s, drop-off penalty for >52s) |
| **Incident 5** | *Phase 5 (Judge Rubric)* | *Heuristic Judge* | Exclamation mark at the end of an affirming line (*"Very well!"*) was tagged as an unresolved cliffhanger (`cliff_str = 5`) | Exclamation points (`!`) were initially treated as universal signals of tension rather than checking semantic closure | Added resolution-word detection: lines containing affirmative closures ("very well", "goodbye", "yes father", "understood") now force `ends_resolved = True` and penalize cliffhanger score to $\le 2$ |

---

### Concrete Incident Analysis (For Interview & Submission Report)

#### Incident 2 Detail: Substring Collision in LLM Dispatcher
When evaluating candidate promos with `prompts/judge_rubric_v1.txt`, the prompt passed context fields:
```
Show Context:
Title: {show_title}
Premise: {premise}
Late Twists / Spoilers: {central_twists}
```
The mock LLM dispatcher examined `prompt.lower()` and checked `'premise' in prompt.lower()` first, assuming it was a bible synthesis request. This returned a dictionary containing `{"title": ..., "genre": ..., "premise": ...}`, which completely lacked the judging rubric fields. The automated Pydantic/schema validator immediately trapped the missing keys, logged a `SchemaValidationError`, and triggered the retry mechanism.  
**Safeguard:** Reordered dispatch logic to prioritize explicit rubric fields and inspect `schema['required']` directly rather than relying on substring detection.

#### Incident 5 Detail: Semantic Closure vs. Punctuation in Cliffhanger Cuts
In Episode 8 (`Candidate ep08_u22_u41`), the final dialogue line ends with:
```
JULIANA: "Very well!"
CAMERA: Close-up on Juliana nodding gently as she steps toward the hearth.
```
Because the line contained an exclamation point `!`, early heuristic tagging classified it as an open, high-intensity cliffhanger (`cliffhanger_potential = 5`). In reality, Juliana has accepted Alexander's explanation and the scene concludes in peaceful resolution. When watched as a promo, a viewer feels zero compulsion to click next.  
**Safeguard:** Introduced a negative closure dictionary (`["very well", "goodbye", "yes father", "understood", "as you wish", "i agree"]`). If the final unit contains these phrases, `ends_resolved` is flagged `True` and `cliffhanger_quality` is capped at 2.
