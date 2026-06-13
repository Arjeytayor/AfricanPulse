"""NVIDIA NIM client — OpenAI-compatible model router with fallback and caching.

Usage:
    from nim_client import generate_text
    article = generate_text(prompt, task="article")

The router automatically:
  • picks the cheapest adequate model for the task
  • falls back to the next model if the first is rate-limited or errors
  • returns a non-empty string or raises
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from typing import Final

from logger import logger

# ── Optional disk cache for LLM responses ─────────────────
_CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache", "nim_llm")
os.makedirs(_CACHE_DIR, exist_ok=True)


def _cache_key(prompt: str, model: str) -> str:
    return hashlib.sha256(f"{model}:{prompt}".encode()).hexdigest()


def _cached(prompt: str, model: str, ttl: int = 3600):
    """Return cached value or None."""
    import glob
    key = _cache_key(prompt, model)
    for f in glob.glob(os.path.join(_CACHE_DIR, f"{key}_*.json")):
        try:
            mtime = os.path.getmtime(f)
            if time.time() - mtime < ttl:
                with open(f, "r", encoding="utf-8") as fp:
                    return json.load(fp)
        except Exception:
            pass
    return None


def _save_cache(prompt: str, model: str, data: dict):
    key = _cache_key(prompt, model)
    path = os.path.join(_CACHE_DIR, f"{key}_{int(time.time())}.json")
    try:
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(data, fp)
    except Exception:
        pass


# ── Model pool & task routing ─────────────────────────────

# ── Model pool — data-driven picks from research on all 40 working models ──
# Article  → largest, best reasoning (675B Mistral > 122B Qwen > 70B LLaMA)
# Script   → fastest good-quality (DeepSeek flash > 70B LLaMA > creative 70B)
# Synthesis → smallest, cheapest viable (3B > 8B)
MODEL_POOL: Final[dict[str, list[str]]] = {
    "article": [
        "mistralai/mistral-large-3-675b-instruct-2512",  # 675B — 9.4/10 quality, best long-form
        "qwen/qwen3.5-122b-a10b",                        # sweet spot: 122B, fast, nearly 397B quality
        "meta/llama-3.3-70b-instruct",                   # real writers prefer this over Maverick
    ],
    "script": [
        "deepseek-ai/deepseek-v4-flash",                  # 98 tok/s, $0.14/M — fastest
        "meta/llama-3.3-70b-instruct",                   # proven for creative/narrative
        "abacusai/dracarys-llama-3.1-70b-instruct",      # tuned for engaging, hook-first content
    ],
    "synthesis": [
        "meta/llama-3.2-3b-instruct",                      # 3B — dirt cheap, sufficient for summaries
        "meta/llama-3.1-8b-instruct",                      # tested, works
    ],
    "fallback": [
        "meta/llama-3.1-8b-instruct",
    ],
}

# ── Rate-limiting (NVIDIA free tier = 40 RPM) ──
# Ensure at least 1.6 seconds between NIM calls to stay under 40 req/min.
_MIN_DELAY_BETWEEN_CALLS = 1.6  # seconds
_last_call_time = threading.Lock()
_last_call_timestamp: float = 0.0

# Max tokens per task
_TASK_MAX_TOKENS: Final[dict[str, int]] = {
    "article": 2000,
    "script": 800,
    "synthesis": 500,
    "fallback": 2000,
}

# ── OpenAI-compatible NIM client ───────────────────────────

def _call_nim(prompt: str, model: str, max_tokens: int, temperature: float = 0.7) -> str:
    """Call NVIDIA NIM via OpenAI-compatible endpoint. Returns text or raises.

    Built-in rate limiting: enforces ~1.6s between calls to stay under the
    free-tier 40 RPM cap. Exponential backoff on 429.
    """
    import config
    import openai

    if not config.NVIDIA_NIM_API_KEY:
        raise RuntimeError("NVIDIA_NIM_API_KEY is not set. Add it to your .env file.")

    # ── Rate-limit: throttle to ≤ 40 RPM ───────────
    global _last_call_timestamp
    with _last_call_time:
        elapsed = time.time() - _last_call_timestamp
        if elapsed < _MIN_DELAY_BETWEEN_CALLS:
            wait = _MIN_DELAY_BETWEEN_CALLS - elapsed
            logger.debug(f"NIM rate-limit: sleeping {wait:.2f}s")
            time.sleep(wait)
        _last_call_timestamp = time.time()

    client = openai.OpenAI(
        base_url=config.NIM_BASE_URL,
        api_key=config.NVIDIA_NIM_API_KEY,
    )

    # ── Exponential backoff on 429 ──────────────────
    max_retries = 3
    retry_wait = 2.0
    last_exc: Exception | None = None

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )

            if not response.choices:
                raise RuntimeError(f"NIM returned empty choices for model {model}")

            content = response.choices[0].message.content
            if not content or not content.strip():
                raise RuntimeError(f"NIM returned empty content for model {model}")

            return content.strip()

        except openai.AuthenticationError as e:
            logger.error(f"NIM Authentication failed — check API key: {e}")
            raise
        except openai.NotFoundError as e:
            logger.error(f"NIM Model not found: {model}. This model may not be available on your key: {e}")
            raise
        except openai.RateLimitError as e:
            last_exc = e
            logger.warning(f"NIM 429 on {model}, attempt {attempt + 1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_wait}s...")
                time.sleep(retry_wait)
                retry_wait *= 2  # exponential backoff
                continue
            break
        except Exception as e:
            logger.error(f"NIM Unexpected error for {model}: {type(e).__name__}: {e}")
            raise

    # Exhausted retries
    if last_exc:
        logger.error(f"NIM all retries exhausted for {model}: {last_exc}")
        raise last_exc
    raise RuntimeError(f"NIM call failed for {model} after {max_retries} retries")


# ── Public API ────────────────────────────────────────────

def generate_text(prompt: str, task: str = "article", *, temperature: float = 0.7) -> str:
    """
    Generate text for *task* (article/script/synthesis).

    Tries models in order, returns first non-empty response.
    Caches successful responses (1 hour TTL).
    """
    models = MODEL_POOL.get(task, MODEL_POOL["fallback"])
    max_tokens = _TASK_MAX_TOKENS.get(task, 2000)

    for model in models:
        # Check cache first
        cached = _cached(prompt, model)
        if cached and cached.get("text"):
            logger.info(f"NIM cache hit: {model} (task={task})")
            return cached["text"]

        # Try live call
        try:
            logger.info(f"NIM call: {model} (task={task})")
            text = _call_nim(prompt, model, max_tokens, temperature)
            if text and text.strip():
                _save_cache(prompt, model, {"text": text, "model": model})
                logger.info(f"NIM success: {model} (task={task}, {len(text)} chars)")
                return text
        except Exception as exc:
            logger.warning(f"NIM failed on {model} (task={task}): {exc}")
            continue

    # All models failed
    logger.error(f"NIM: all models exhausted for task={task}")
    raise RuntimeError(f"NIM all models failed for task={task}")


# ── Legacy bridge for existing Anthropic-style code ─────────

def generate_article(prompt: str) -> str:
    """Legacy-compatibility wrapper used by generator_article.py."""
    return generate_text(prompt, task="article")


def generate_script(prompt: str) -> str:
    """Legacy-compatibility wrapper used by generator_script.py."""
    return generate_text(prompt, task="script")


# ── Health check ─────────────────────────────────────────

def health_check() -> dict:
    """Test all models in the pool and return detailed status."""
    import config
    results = {"api_key_set": bool(config.NVIDIA_NIM_API_KEY), "base_url": config.NIM_BASE_URL}
    model_results = {}

    for task, models in MODEL_POOL.items():
        for model in models:
            try:
                _call_nim("Say 'hello' and nothing else.", model, max_tokens=10)
                model_results[f"{task}:{model}"] = "✅ OK"
                logger.info(f"NIM health check PASS: {model} (task={task})")
            except Exception as exc:
                model_results[f"{task}:{model}"] = f"❌ {type(exc).__name__}: {exc}"
                logger.warning(f"NIM health check FAIL: {model}: {exc}")

    results["models"] = model_results
    return results
