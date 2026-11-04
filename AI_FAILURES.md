# AI Failure Log

This log tracks every occurrence where an AI model/step produced a flawed, hallucinated, or unparseable output during development and evaluation, alongside root-cause analysis and the protective code safeguards applied.

---

| Incident # | Stage | Model / Tool | Observed Failure | Root Cause | Code / Prompt Safeguard Applied |
|---|---|---|---|---|---|
| **Incident 1** | *Phase 1 (Parsing)* | *Rule-based Regex* | `ACTIONS AND DIALOGUE:` caused unrecognised line warning in Ep 6 | Upstream human script formatting used uppercase `ACTIONS AND DIALOGUE:` and `SCENE HEADING:` in Ep 6 whereas Ep 1 used Title Case | Standardized string normalization (`sl.lower()`) across all screenplay header matchers |
| **Incident 2** | *Phase 5 (Judging)* | *LLM Dispatcher / Mock* | Schema validation failure (`Missing required fields: ['reasoning', 'hook_strength', ...]`) causing retry loop | In prompt templates that include the show premise (`Premise: {premise}`), the prompt matched the `'premise'` substring before `'hook_strength'`, erroneously returning bible JSON instead of judge scores | Reordered dispatch matching in `llm.py` to prioritize specific rubric criteria and added explicit schema key inspection (`schema['required']`) |

---

### Concrete Incident Analysis (For Interview & Submission Report)
- **Incident 2 Detail**: When evaluating candidate promos with `prompts/judge_rubric_v1.txt`, the prompt included context fields `Show Context: Premise: {premise}`. The dispatcher examined `prompt.lower()` and checked `'premise' in prompt.lower()` first, assuming it was a bible synthesis request. This returned a dictionary containing `{"title": ..., "genre": ..., "premise": ...}`, which completely lacked the judging rubric fields. The automated Pydantic/schema validator immediately trapped the missing keys, logged a `SchemaValidationError`, and triggered the retry mechanism. The fix updated the dispatcher to match explicit schema required keys first.
