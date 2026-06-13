"""Two-stage research orchestrator.

Provides ``fetch_all_briefs`` / ``fetch_topic_brief`` that transparently choose
between:
  a) **news_client** — default. Pure-Python, free, works everywhere.
  b) **last30days JSON** — if a ``cache/last30days/<topic>_<date>.json`` file
     already exists (e.g. you ran the Claude Code skill manually).
  c) **last30days CLI** — attempted as a last-resort if the ``claude`` binary
     exists in PATH.

After picking the top topics the scheduler calls ``agent_reach.deep_dive``
for the raw community-material layer.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import date, datetime, timedelta

from logger import logger
from config import L30_CACHE_DIR

# ── Cache helpers ─────────────────────────────────────────

def _cache_path(topic: str, day: str | None = None) -> str:
    day = day or date.today().isoformat()
    key = topic.lower().replace(" ", "_")[:60]
    return os.path.join(L30_CACHE_DIR, f"{key}_{day}.json")


def _fallback_research(topic: str) -> dict:
    """Minimal fallback when everything else fails."""
    return {
        "topic": topic,
        "synthesis": f"[FALLBACK] No research data for '{topic}'. Save JSON to cache or install deps.",
        "engagement_score": 0,
        "reddit": [],
        "x": [],
        "youtube": [],
        "polymarket": [],
    }


def fetch_topic_brief(topic: str, *, prefer_last30days: bool = False) -> dict:
    """
    Get a research brief for ``topic``.

    Tries, in order:
      1. Today's cached JSON (fast, zero network)
      2. ``news_client`` (pure Python, free, always available)
      3. ``last30days`` via ``claude`` subprocess (rarely works)
      4. Hard fallback with a warning

    Returns dict always populated with at least `` topic``, ``synthesis``,
    ``engagement_score`` and ``reddit`` keys.
    """
    os.makedirs(L30_CACHE_DIR, exist_ok=True)
    today = date.today().isoformat()
    cache_file = _cache_path(topic, today)

    # 1. Cached JSON (you saved it from the Claude Code skill manually)
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                data.setdefault("_topic", topic)
                return data
        except Exception:
            logger.warning(f"Cache read failed for {topic}")

    # 2. Default: news_client (always works, no auth required)
    if not prefer_last30days:
        try:
            import news_client
            data = news_client.fetch_topic_brief(topic)
            data.setdefault("_topic", topic)
            return data
        except ImportError:
            logger.warning("news_client.py missing — falling back to last30days")
        except Exception:
            logger.warning("news_client failed — trying last30days fallback")

    # 3. last30days CLI (rarely available outside Claude Code)
    try:
        if shutil.which("claude"):
            result = subprocess.run(
                ["claude", f"/last30days {topic} --emit=json"],
                capture_output=True, text=True, timeout=120, shell=True
            )
            data = json.loads(result.stdout)
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            data.setdefault("_topic", topic)
            return data
    except (json.JSONDecodeError, subprocess.TimeoutExpired):
        pass
    except Exception:
        logger.debug("last30days CLI attempt failed silently")

    # 4. Hard fallback — nothing worked
    logger.error(f"All research methods failed for '{topic}' — returning placeholder")
    data = _fallback_research(topic)
    data["_topic"] = topic
    return data


def fetch_all_briefs(topics: list[str] | list[dict] | None = None, *, warn_on_fallback: bool = True) -> list[dict]:
    """Run research across *topics* (default = config.DAILY_TOPICS or dynamic discovery).

    ``topics`` can be:
      - list[str] — legacy static strings (each used for both search and display)
      - list[dict] — dynamic discovery objects with 'headline' + 'query' keys
        where 'query' is used for the search and 'headline' is stored for display.
    """
    from config import DAILY_TOPICS, USE_DYNAMIC_TOPICS

    if topics is not None:
        targets = topics
    elif USE_DYNAMIC_TOPICS:
        try:
            from topic_discoverer import discover_topics
            targets = discover_topics(count=15)
            logger.info(f"Dynamic topics discovered: {len(targets)}")
        except Exception:
            logger.warning("Dynamic topic discovery failed — falling back to static DAILY_TOPICS")
            targets = DAILY_TOPICS
    else:
        targets = DAILY_TOPICS

    results = []
    for item in targets:
        # Handle both string (legacy) and dict (dynamic) targets
        if isinstance(item, dict):
            headline = item["headline"]
            query = item["query"]
        else:
            headline = query = item

        brief = fetch_topic_brief(query)
        if brief:
            brief.setdefault("_headline", headline)   # display text
            brief.setdefault("_query", query)          # search text
            brief.setdefault("_topic", query)          # internal topic key
            results.append(brief)

    if results and warn_on_fallback:
        fallback_count = sum(1 for r in results if "[FALLBACK]" in r.get("synthesis", ""))
        if fallback_count:
            logger.warning(f"{fallback_count}/{len(results)} topics returned fallback data")
    return results


# ── Maintenance helpers ───────────────────────────────────

def cleanup_old_cache(days: int = 7) -> None:
    """Remove cache files older than ``days``."""
    cutoff = datetime.now() - timedelta(days=days)
    if not os.path.exists(L30_CACHE_DIR):
        return
    for fname in os.listdir(L30_CACHE_DIR):
        path = os.path.join(L30_CACHE_DIR, fname)
        if os.path.isfile(path):
            mtime = datetime.fromtimestamp(os.path.getmtime(path))
            if mtime < cutoff:
                try:
                    os.remove(path)
                except Exception:
                    pass
