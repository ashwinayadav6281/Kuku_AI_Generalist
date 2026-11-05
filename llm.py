"""
llm.py - Model-swappable LLM interface with caching, schema validation, and token tracking.

Supports:
- Gemini (default free tier, via GEMINI_API_KEY or GOOGLE_API_KEY)
- OpenAI / OpenAI-compatible (via OPENAI_API_KEY, optional OPENAI_BASE_URL)
- Anthropic (via ANTHROPIC_API_KEY)
- Mock / Offline mode (for testing without API keys)

Features:
- `call_llm(prompt, schema=None, tier="cheap"|"strong")`
- Disk caching by SHA-256(provider + model + prompt + schema)
- Automatic retry on invalid JSON (up to 2 retries)
- Cumulative usage tracking (prompt tokens, completion tokens, latency)
"""

import os
import json
import hashlib
import time
import re
from pathlib import Path
from typing import Optional, Dict, Any, Union
import requests
import yaml
from dotenv import load_dotenv

# Load local .env or ~/.env
load_dotenv(override=False)
user_env = Path.home() / ".env"
if user_env.exists():
    load_dotenv(dotenv_path=user_env, override=False)


# ── Global Usage Tracking ────────────────────────────────────────────────────

_USAGE_TRACKER = {
    "total_calls": 0,
    "cache_hits": 0,
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_latency_seconds": 0.0,
    "calls_by_tier": {"cheap": 0, "strong": 0},
    "errors": 0,
}


def get_usage_stats() -> Dict[str, Any]:
    """Return a copy of the cumulative usage metrics."""
    return dict(_USAGE_TRACKER)


def reset_usage_stats():
    """Reset the usage counters."""
    global _USAGE_TRACKER
    _USAGE_TRACKER = {
        "total_calls": 0,
        "cache_hits": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_latency_seconds": 0.0,
        "calls_by_tier": {"cheap": 0, "strong": 0},
        "errors": 0,
    }


# ── Configuration Loader ─────────────────────────────────────────────────────

def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    cfg_file = Path(config_path)
    if cfg_file.exists():
        with open(cfg_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {
        "llm": {
            "provider": "gemini",
            "cheap_model": "gemini-2.5-flash",
            "strong_model": "gemini-2.5-flash",
            "temperature": 0.2,
            "max_retries": 2,
            "timeout_seconds": 45,
            "cache_dir": ".llm_cache",
            "use_cache": True,
        }
    }


# ── Cache Management ─────────────────────────────────────────────────────────

def _get_cache_key(provider: str, model: str, prompt: str, schema_str: str) -> str:
    content = f"{provider}:{model}:{schema_str}:{prompt}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _read_from_cache(cache_dir: Path, key: str) -> Optional[str]:
    cache_file = cache_dir / f"{key}.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("response")
        except Exception:
            return None
    return None


def _write_to_cache(cache_dir: Path, key: str, response: str, meta: Dict[str, Any]):
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{key}.json"
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"response": response, "meta": meta}, f, indent=2)
    except Exception:
        pass


# ── JSON Cleaner & Validator ─────────────────────────────────────────────────

def extract_json(raw_text: str) -> str:
    """Extract clean JSON substring from an LLM response."""
    text = raw_text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    # Find the outermost JSON structure {...} or [...]
    first_brace = text.find("{")
    first_bracket = text.find("[")
    
    start_idx = -1
    if first_brace != -1 and first_bracket != -1:
        start_idx = min(first_brace, first_bracket)
    elif first_brace != -1:
        start_idx = first_brace
    elif first_bracket != -1:
        start_idx = first_bracket

    if start_idx != -1:
        # Determine closing char
        is_object = (text[start_idx] == "{")
        close_char = "}" if is_object else "]"
        last_idx = text.rfind(close_char)
        if last_idx != -1 and last_idx > start_idx:
            return text[start_idx : last_idx + 1]

    return text


def validate_json(raw_text: str, schema: Optional[Dict[str, Any]] = None) -> Any:
    """
    Parse text as JSON and optionally validate against a schema.
    Raises ValueError on failure.
    """
    cleaned = extract_json(raw_text)
    try:
        parsed = json.loads(cleaned)
    except Exception as e:
        raise ValueError(f"JSONDecodeError: {e}. Raw response snippet: {raw_text[:200]}")

    if schema:
        # Check required fields if schema specifies them
        required_fields = schema.get("required", [])
        if isinstance(parsed, dict):
            missing = [f for f in required_fields if f not in parsed]
            if missing:
                raise ValueError(f"SchemaValidationError: Missing required fields: {missing}")
    return parsed


# ── Provider Implementations ─────────────────────────────────────────────────

def _call_gemini(model: str, prompt: str, schema: Optional[Dict[str, Any]], timeout: int) -> tuple:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY (or GOOGLE_API_KEY) is missing. "
            "Please set it in your environment or in a .env file."
        )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    generation_config: Dict[str, Any] = {
        "temperature": 0.2,
    }
    if schema:
        generation_config["response_mime_type"] = "application/json"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": generation_config,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini API Error {resp.status_code}: {resp.text}")

    data = resp.json()
    try:
        candidates = data["candidates"]
        content_text = candidates[0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected Gemini response structure: {data}")

    usage = data.get("usageMetadata", {})
    prompt_tokens = usage.get("promptTokenCount", len(prompt) // 4)
    completion_tokens = usage.get("candidatesTokenCount", len(content_text) // 4)

    return content_text, prompt_tokens, completion_tokens


def _call_openai(model: str, prompt: str, schema: Optional[Dict[str, Any]], timeout: int) -> tuple:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing. Set it in environment or .env file.")

    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    url = f"{base_url}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }
    if schema:
        payload["response_format"] = {"type": "json_object"}

    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"OpenAI API Error {resp.status_code}: {resp.text}")

    data = resp.json()
    content_text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", len(prompt) // 4)
    completion_tokens = usage.get("completion_tokens", len(content_text) // 4)

    return content_text, prompt_tokens, completion_tokens


def _call_anthropic(model: str, prompt: str, schema: Optional[Dict[str, Any]], timeout: int) -> tuple:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is missing. Set it in environment or .env file.")

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model": model,
        "max_tokens": 2048,
        "temperature": 0.2,
        "messages": [{"role": "user", "content": prompt}],
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if resp.status_code != 200:
        raise RuntimeError(f"Anthropic API Error {resp.status_code}: {resp.text}")

    data = resp.json()
    content_text = data["content"][0]["text"]
    usage = data.get("usage", {})
    prompt_tokens = usage.get("input_tokens", len(prompt) // 4)
    completion_tokens = usage.get("output_tokens", len(content_text) // 4)

    return content_text, prompt_tokens, completion_tokens


def _call_mock(model: str, prompt: str, schema: Optional[Dict[str, Any]]) -> tuple:
    """
    Deterministic mock provider for offline testing and verification.
    Parses prompt context and outputs valid synthetic JSON conforming to the requested schema.
    """
    prompt_lower = prompt.lower()

    if "hook_strength" in prompt_lower or (schema and "hook_strength" in schema.get("required", [])):
        # Dynamic evaluation based on candidate prompt text
        hook_match = re.search(r'Opening Hook [^:]*:\s*"?([^\n]+)', prompt, re.IGNORECASE)
        cliff_match = re.search(r'Closing Cliffhanger [^:]*:\s*"?([^\n]+)', prompt, re.IGNORECASE)
        ep_match = re.search(r'Episode:\s*(\d+)', prompt, re.IGNORECASE)
        dur_match = re.search(r'Total Duration:\s*([\d.]+)', prompt, re.IGNORECASE)

        hook_text = hook_match.group(1).strip().strip('"') if hook_match else ""
        cliff_text = cliff_match.group(1).strip().strip('"') if cliff_match else ""
        ep_id = int(ep_match.group(1)) if ep_match else 1
        dur = float(dur_match.group(1)) if dur_match else 35.0

        h_low = hook_text.lower()
        c_low = cliff_text.lower()
        p_low = prompt.lower()

        # Hook strength (1 to 5)
        if any(w in h_low for w in ["slap", "shove", "gasp", "grab", "strike", "fling", "sob"]):
            h_str = 5
            h_why = "Visceral physical shock in opening 3s"
        elif any(w in h_low for w in ["holding her hand", "marrying me", "divorce", "marry", "bastard", "liar", "betray", "poison", "kill", "die", "disown"]):
            h_str = 5
            h_why = "Explosive marital betrayal / accusation hook"
        elif any(w in h_low for w in ["why are you", "who is", "what do you mean", "how dare", "look at me", "remove her", "enough!"]):
            h_str = 4
            h_why = "High-status confrontation hook"
        elif any(f"({d})" in h_low for d in ["outraged", "sneering", "furious", "heartbroken", "tearful", "coldly"]):
            h_str = 4
            h_why = "High emotional intensity opening"
        else:
            h_str = 3
            h_why = "Standard dialogue opening"

        # Cliffhanger quality (1 to 5)
        ends_res = False
        if any(w in c_low for w in ["very well", "goodbye", "yes father", "understood", "as you wish", "i agree"]):
            c_qual = 2
            ends_res = True
            c_why = "Resolves ongoing dramatic tension"
        elif "?" in cliff_text:
            c_qual = 5
            c_why = "High-stakes unanswered question cut"
        elif any(w in c_low for w in ["or else", "choose", "never", "too late", "wait", "carefully", "try me", "mark my words", "what did you find"]):
            c_qual = 5
            c_why = "Leaves an unresolved ultimatum or threat hanging"
        elif any(w in c_low for w in ["who are you", "what have you done", "help", "look at me"]):
            c_qual = 4
            c_why = "Escalates tension right before cutoff"
        else:
            c_qual = 3
            c_why = "Moderate dramatic cutoff"

        # Standalone clarity (1 to 5)
        if ep_id <= 2:
            clarity = 5
        elif ep_id <= 5:
            clarity = 4
        elif ep_id <= 12:
            clarity = 4 if any(n in p_low for n in ["juliana", "gerald", "clarissa"]) else 3
        elif ep_id <= 25:
            clarity = 3
        else:
            clarity = 2

        # Emotional pull (1 to 5)
        emo_count = sum(1 for w in ["heartbreak", "tears", "shame", "betray", "love", "ruin", "scandal", "broken", "proud", "daughter", "father"] if w in p_low)
        emo = min(5, max(3, 3 + (emo_count // 2)))

        # Hard fail flags
        starts_mid = bool(hook_text.strip().startswith(("and ", "but ", "so ", "because ", "...")))
        spoils_twist = bool(ep_id >= 40 and any(w in p_low for w in ["duke of ashburn", "rightful duke", "unmask", "true identity"]))
        needs_context = bool(ep_id > 30 and clarity <= 2)

        # Dynamic Why It Works
        spk = hook_text.split(":")[0].strip() if ":" in hook_text else "Lead character"
        if h_str >= 5 and c_qual >= 5:
            why_works = f"High-velocity emotional ambush: opens on an explosive {spk} hook and snaps shut on an urgent, unanswered cut."
        elif h_str >= 5:
            why_works = f"Immediate hook halts feed scroll instantly, propelled by raw indignation from {spk}."
        elif c_qual >= 5:
            why_works = f"Intense confrontation culminating in an unresolved cliffhanger that forces viewers to click next."
        else:
            why_works = f"Solid dramatic conflict driven by {spk} with natural emotional tension."

        reasoning = f"{h_why} ({h_str}/5); {c_why} ({c_qual}/5); clarity {clarity}/5 and emotional resonance {emo}/5."

        mock_data = {
            "reasoning": reasoning,
            "hook_strength": h_str,
            "cliffhanger_quality": c_qual,
            "standalone_clarity": clarity,
            "emotional_pull": emo,
            "starts_mid_thought": starts_mid,
            "ends_resolved": ends_res,
            "spoils_major_twist": spoils_twist,
            "needs_missing_context": needs_context,
            "why_it_works": why_works
        }
    elif "chosen_setup_id" in prompt_lower or (schema and "chosen_setup_id" in schema.get("required", [])):
        mock_data = {
            "chosen_setup_id": "NONE",
            "reasoning": "The core dramatic scene is already self-contained."
        }
    elif "hook_potential" in prompt_lower or "scenes" in prompt_lower:
        mock_data = {
            "episode_id": 1,
            "scenes": [
                {
                    "scene_id": 1,
                    "hook_potential": 4,
                    "hook_type": "shocking line / confrontation",
                    "cliffhanger_potential": 4,
                    "is_open_ended": True,
                    "intensity": "high",
                    "context_needed": "low",
                    "spoiler_risk": False,
                    "best_hook_line": "Gerald, why are you holding her hand?",
                    "best_cliffhanger_line": "Long enough to know he was never going to marry you."
                }
            ]
        }
    elif "campaign_strategy" in prompt_lower or (schema and "campaign_strategy" in schema.get("required", [])):
        mock_data = {
            "campaign_strategy": "Lead with high-impact altar betrayal to drive viral installs, followed by escalating confrontations and revenge payoff.",
            "ranked_promos": []
        }
    elif "bible" in prompt_lower or (schema and "premise" in schema.get("required", [])) or (schema and "central_twists" in schema.get("required", [])):
        mock_data = {
            "title": "I Married a Broken Soldier. He was a Duke",
            "genre": "Historical Romance, Revenge Drama, Secret Identity",
            "tone": "Melodramatic, Tense, High Stakes, Aristocratic Vindication",
            "premise": "Lady Juliana is abandoned at the altar by her fiancé Gerald and her cruel family in favor of her sister Clarissa. To salvage her dignity, she impulsively agrees to marry a scarred, crippled ex-soldier. Unbeknownst to her and her malicious former family, her humble soldier husband is secretly Alexander, the long-presumed-dead Duke of Ashburn, who is investigating corruption and treachery among the high nobility.",
            "main_characters": [
                {"name": "Lady Juliana", "role": "Protagonist", "description": "Dutiful, proud noblewoman betrayed by family"},
                {"name": "Alexander (Mysterious Soldier / Duke)", "role": "Male Lead", "description": "War-hardened soldier secretly Duke of Ashburn"},
                {"name": "Gerald", "role": "Antagonist", "description": "Juliana's callous former fiancé"},
                {"name": "Clarissa", "role": "Antagonist", "description": "Juliana's scheming younger sister"},
                {"name": "Lord Ashcroft", "role": "Antagonist", "description": "Juliana's cruel father who disowns her"},
                {"name": "Lady Ashcroft (Barbara)", "role": "Antagonist", "description": "Spiteful stepmother"}
            ],
            "central_twists": [
                {"episode": 1, "twist": "Gerald dumps Juliana at the altar to marry her sister Clarissa."},
                {"episode": 4, "twist": "Juliana takes marriage vows with a mysterious scarred soldier."},
                {"episode": 5, "twist": "Juliana's family formally disowns her and throws her mother's ledger in the mud."},
                {"episode": 25, "twist": "Alexander discovers someone is systematically poisoning the Dowager Duchess with arsenic."},
                {"episode": 42, "twist": "Alexander officially unmasks himself in full ducal regalia as the rightful Duke of Ashburn, shocking the entire court."}
            ]
        }
    else:
        mock_data = {"status": "ok", "message": "Mock response"}

    text = json.dumps(mock_data)
    return text, len(prompt) // 4, len(text) // 4


# ── Unified Call Interface ───────────────────────────────────────────────────

def call_llm(
    prompt: str,
    schema: Optional[Dict[str, Any]] = None,
    tier: str = "cheap",
    config_path: str = "config.yaml"
) -> Any:
    """
    Execute a model-swappable LLM call.

    Args:
        prompt: User/System prompt text.
        schema: Optional JSON schema / required keys for validation.
        tier: "cheap" (bulk tagging) or "strong" (bible, judging, ranking).
        config_path: Path to config.yaml.

    Returns:
        Validated JSON (dict or list) if schema is provided or JSON detected;
        otherwise plain text string.
    """
    config = load_config(config_path)
    llm_cfg = config.get("llm", {})

    provider = os.getenv("LLM_PROVIDER", llm_cfg.get("provider", "gemini")).lower()
    
    # Model selection based on tier
    if tier == "strong":
        model = os.getenv("LLM_STRONG_MODEL", llm_cfg.get("strong_model", "gemini-2.5-flash"))
    else:
        model = os.getenv("LLM_CHEAP_MODEL", llm_cfg.get("cheap_model", "gemini-2.5-flash"))

    use_cache = llm_cfg.get("use_cache", True)
    cache_dir = Path(llm_cfg.get("cache_dir", ".llm_cache"))
    max_retries = int(llm_cfg.get("max_retries", 2))
    timeout = int(llm_cfg.get("timeout_seconds", 45))

    schema_str = json.dumps(schema, sort_keys=True) if schema else ""
    cache_key = _get_cache_key(provider, model, prompt, schema_str)

    # 1. Check cache
    if use_cache:
        cached_resp = _read_from_cache(cache_dir, cache_key)
        if cached_resp is not None:
            _USAGE_TRACKER["cache_hits"] += 1
            _USAGE_TRACKER["total_calls"] += 1
            _USAGE_TRACKER["calls_by_tier"][tier] = _USAGE_TRACKER["calls_by_tier"].get(tier, 0) + 1
            if schema or cached_resp.strip().startswith(("{", "[")):
                try:
                    return validate_json(cached_resp, schema)
                except ValueError:
                    pass  # If cached item failed schema, fall through to re-request
            else:
                return cached_resp

    # 2. Check for active API key; if provider is gemini/openai/anthropic but key is absent, fallback to mock if requested
    has_key = True
    if provider == "gemini" and not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        has_key = False
    elif provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        has_key = False
    elif provider == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        has_key = False

    if not has_key:
        if os.getenv("LLM_OFFLINE_FALLBACK", "0") == "1":
            provider = "mock"
        else:
            raise ValueError(
                f"API key missing for provider '{provider}'. "
                f"Please add your key to .env (see .env.example) or export it, "
                f"or set LLM_OFFLINE_FALLBACK=1 for offline dry runs."
            )

    # 3. Call with retry on invalid JSON
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            start_time = time.time()
            if provider == "gemini":
                raw_text, in_tok, out_tok = _call_gemini(model, prompt, schema, timeout)
            elif provider == "openai":
                raw_text, in_tok, out_tok = _call_openai(model, prompt, schema, timeout)
            elif provider == "anthropic":
                raw_text, in_tok, out_tok = _call_anthropic(model, prompt, schema, timeout)
            elif provider == "mock":
                raw_text, in_tok, out_tok = _call_mock(model, prompt, schema)
            else:
                raise ValueError(f"Unknown LLM provider: '{provider}'")

            latency = time.time() - start_time
            _USAGE_TRACKER["total_calls"] += 1
            _USAGE_TRACKER["prompt_tokens"] += in_tok
            _USAGE_TRACKER["completion_tokens"] += out_tok
            _USAGE_TRACKER["total_latency_seconds"] += latency
            _USAGE_TRACKER["calls_by_tier"][tier] = _USAGE_TRACKER["calls_by_tier"].get(tier, 0) + 1

            if schema or raw_text.strip().startswith(("{", "[")):
                parsed_json = validate_json(raw_text, schema)
                if use_cache:
                    _write_to_cache(cache_dir, cache_key, raw_text, {
                        "provider": provider, "model": model, "tier": tier,
                        "prompt_tokens": in_tok, "completion_tokens": out_tok,
                    })
                return parsed_json
            else:
                if use_cache:
                    _write_to_cache(cache_dir, cache_key, raw_text, {
                        "provider": provider, "model": model, "tier": tier,
                        "prompt_tokens": in_tok, "completion_tokens": out_tok,
                    })
                return raw_text

        except Exception as e:
            last_err = e
            _USAGE_TRACKER["errors"] += 1
            if attempt < max_retries:
                time.sleep(1.0 * (attempt + 1))
                # Append correction prompt on retry if JSON decode error
                prompt += f"\n\nCRITICAL ERROR: Your previous response was not valid JSON ({e}). Output ONLY valid raw JSON."

    raise RuntimeError(f"call_llm failed after {max_retries + 1} attempts. Last error: {last_err}")
