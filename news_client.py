"""Native research client — replaces last30days Claude Code skill.

Uses only Python + HTTP. No CLIs, no auth required for the free tier.
Sources:
  • Reddit JSON API   (public, no key needed)
  • Google News RSS   (public, no key needed)
  • Perplexity API    (optional — produces excellent synthesis, needs key)

Produces the same dict format the rest of the pipeline expects.
"""

from __future__ import annotations

import json
import os
import time
from datetime import date
from typing import Final
from urllib.parse import quote
from xml.etree import ElementTree

import requests

from logger import logger
from config import L30_CACHE_DIR, PERPLEXITY_API_KEY


REDDIT_JSON_URL: Final[str] = "https://www.reddit.com/search.json"
GN_RSS_URL: Final[str] = "https://news.google.com/rss/search?q={query}&hl=en-GB&gl=GB&ceid=GB:en"
PERPLEXITY_API: Final[str] = "https://api.perplexity.ai/chat/completions"

# Global financial news RSS feeds (no auth, used as Tier-2/3 fallbacks)
GLOBAL_RSS_FEEDS: Final[dict[str, str]] = {
    "reuters_top": "https://www.reutersagency.com/feed/?best-topics=business",
    "ft_markets": "https://www.ft.com/?format=rss",
    "cnbc_top": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "cointelegraph": "https://cointelegraph.com/rss",
    "fxstreet": "https://www.fxstreet.com/news/feed",
}

# NewsNow / Google News search endpoints by region
REGIONAL_NEWS_URLS: Final[dict[str, str]] = {
    "us": "https://news.google.com/rss/search?q={query}+site:bloomberg.com+OR+site:reuters.com+OR+site:wsj.com&hl=en-US&gl=US&ceid=US:en",
    "uk": "https://news.google.com/rss/search?q={query}+site:ft.com+OR+site:reuters.com+OR+site:bbc.com&hl=en-GB&gl=GB&ceid=GB:en",
    "asia": "https://news.google.com/rss/search?q={query}+site:scmp.com+OR+site:nikkei.com+OR+site:reuters.com&hl=en-SG&gl=SG&ceid=SG:en",
    "emerging": "https://news.google.com/rss/search?q={query}+emerging+markets&hl=en-GB&gl=GB&ceid=GB:en",
    "crypto": "https://news.google.com/rss/search?q={query}+crypto+OR+bitcoin+OR+ethereum&hl=en-GB&gl=GB&ceid=GB:en",
}


class SimpleResearchClient:
    """Lightweight research engine with optional Perplexity enrichment."""

    def __init__(self, perplexity_key: str | None = None):
        self.perplexity_key = perplexity_key
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AfricanPulse/1.0"
        })

    # ── Public ─────────────────────────────────────────────

    def fetch_topic_brief(self, topic: str) -> dict:
        """Return a last30days-compatible dict for *topic*."""
        today = date.today().isoformat()
        cache_file = os.path.join(L30_CACHE_DIR, f"{self._safe_key(topic)}_{today}.json")
        os.makedirs(L30_CACHE_DIR, exist_ok=True)

        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        # Gather raw signals (multi-source, multi-region)
        reddit = self._reddit_search(topic, limit=5)
        news = self._global_news(topic, limit=8)
        engagement = self._rough_engagement(reddit, news)

        # Optional Perplexity for AI synthesis
        synthesis = self._perplexity_synth(topic) or self._local_synth(topic, reddit, news)

        result = {
            "topic": topic,
            "synthesis": synthesis,
            "engagement_score": engagement,
            "reddit": reddit,
            "x": [],  # left to agent_reach / deep_dive
            "youtube": [],
            "polymarket": [],
            "top_query": topic,
            "sources": ["reddit", "google-news", "regional-news"],
        }

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        return result

    # ── Reddit (free, no key) ─────────────────────────────

    def _reddit_search(self, topic: str, limit: int = 5) -> list[dict]:
        try:
            url = f"{REDDIT_JSON_URL}?q={quote(topic)}&limit={limit}&sort=hot&t=week"
            # Reddit requires a descriptive User-Agent; generic ones get 403 Blocked
            headers = {
                "User-Agent": "AfricanPulseBot/1.0 (by /u/AfricanPulseBot)"
            }
            r = self._session.get(url, headers=headers, timeout=15)
            r.raise_for_status()
            data = r.json()
            posts = []
            for child in data.get("data", {}).get("children", [])[:limit]:
                p = child.get("data", {})
                posts.append({
                    "subreddit": p.get("subreddit", ""),
                    "title": p.get("title", ""),
                    "upvotes": p.get("ups", 0),
                    "url": f"https://reddit.com{p.get('permalink', '')}",
                    "selftext": p.get("selftext", "")[:500],
                })
            return posts
        except Exception:
            logger.error(f"Reddit search failed for '{topic}'", exc_info=True)
            return []

    # ── Google News RSS (free, no key) ─────────────────────

    def _google_news(self, topic: str, limit: int = 5) -> list[dict]:
        try:
            url = GN_RSS_URL.format(query=quote(topic))
            r = self._session.get(url, timeout=15)
            r.raise_for_status()
            root = ElementTree.fromstring(r.content)
            items = []
            for item in root.findall(".//item")[:limit]:
                items.append({
                    "title": item.findtext("title", ""),
                    "link": item.findtext("link", ""),
                    "pubDate": item.findtext("pubDate", ""),
                })
            return items
        except Exception:
            logger.error(f"Google News RSS failed for '{topic}'", exc_info=True)
            return []

    # ── Global multi-source news (Tier-2/3 fallback) ────────

    def _global_news(self, topic: str, limit: int = 8) -> list[dict]:
        """Fetch news from Google News + regional RSS feeds."""
        all_items = []

        # 1. Google News (general, always works)
        try:
            gn = self._google_news(topic, limit=5)
            all_items.extend(gn)
        except Exception:
            pass

        # 2. Regional / sector-specific Google News
        region_keys = ["us", "uk", "asia", "emerging", "crypto"]
        for key in region_keys:
            try:
                url = REGIONAL_NEWS_URLS[key].format(query=quote(topic))
                r = self._session.get(url, timeout=15)
                r.raise_for_status()
                root = ElementTree.fromstring(r.content)
                for item in root.findall(".//item")[:3]:
                    all_items.append({
                        "title": item.findtext("title", ""),
                        "link": item.findtext("link", ""),
                        "pubDate": item.findtext("pubDate", ""),
                        "source_label": f"gn-{key}",
                    })
            except Exception:
                continue

        # 3. Deduplicate by title
        seen = set()
        deduped = []
        for item in all_items:
            title = (item.get("title") or "").strip()
            if title and title not in seen:
                seen.add(title)
                deduped.append(item)

        return deduped[:limit]

    # ── Perplexity (optional — needs key) ────────────────────

    def _perplexity_synth(self, topic: str) -> str | None:
        if not self.perplexity_key:
            return None
        try:
            r = requests.post(
                PERPLEXITY_API,
                headers={
                    "Authorization": f"Bearer {self.perplexity_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "sonar",
                    "messages": [
                        {
                            "role": "system",
                            "content": "Summarise what the community is saying about this topic in 3-4 sentences. Include trending themes and sentiment.",
                        },
                        {"role": "user", "content": topic},
                    ],
                    "max_tokens": 300,
                },
                timeout=30,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception:
            logger.warning("Perplexity synthesis failed — falling back to local")
            return None

    # ── Local synthesis (no external AI) ────────────────────

    def _local_synth(self, topic: str, reddit: list, news: list) -> str:
        parts = [f"Global trending discussion on '{topic}':\n"]
        if reddit:
            parts.append("Reddit community highlights:")
            for post in reddit[:3]:
                parts.append(f"- r/{post['subreddit']}: {post['title']} ({post['upvotes']}→)")
        if news:
            sources = {}
            for item in news[:5]:
                src = item.get("source_label", "news")
                sources.setdefault(src, []).append(item)
            parts.append("\nGlobal news signals:")
            for src, items in list(sources.items())[:3]:
                for it in items[:2]:
                    parts.append(f"- [{src}] {it['title']}")
        return "\n".join(parts)

    # ── Helpers ─────────────────────────────────────────────

    def _rough_engagement(self, reddit: list, news: list) -> int:
        """Heuristic engagement score."""
        score = sum(p.get("upvotes", 0) for p in reddit)
        score += len(news) * 50  # news items as weaker signal
        return min(score, 9999)

    @staticmethod
    def _safe_key(topic: str) -> str:
        return topic.lower().replace(" ", "_")[:60]


# ── Module-level helpers (mirrors research.py interface) ─

def fetch_topic_brief(topic: str) -> dict:
    """Drop-in replacement for the old last30days fetch."""
    client = SimpleResearchClient(perplexity_key=PERPLEXITY_API_KEY)
    return client.fetch_topic_brief(topic)


def fetch_all_briefs(topics: list[str] | None = None) -> list[dict]:
    from config import DAILY_TOPICS
    topics = topics or DAILY_TOPICS
    client = SimpleResearchClient(perplexity_key=PERPLEXITY_API_KEY)
    results = []
    for topic in topics:
        result = client.fetch_topic_brief(topic)
        if result:
            result["_topic"] = topic
            results.append(result)
        time.sleep(0.5)  # be kind to free APIs
    return results
