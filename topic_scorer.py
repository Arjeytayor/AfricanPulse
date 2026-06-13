"""Score topics by global trending signal, filtering duplicates."""

from logger import logger
from vector_store import is_duplicate, get_africa_context


def score_topic(research_result: dict) -> float:
    """
    Score a topic purely on its global trending / engagement signal.
    African relevance is now a minor bonus (5 %) and only applied
    when the topic genuinely has African context.

    Returns a float score (higher = better).  Normalized to roughly [0, 1].
    """
    try:
        engagement = research_result.get("engagement_score", 0)
        topic_text = research_result.get("synthesis", "") or research_result.get("_topic", "")

        # Africa bonus is now minimal and truly optional
        try:
            africa_contexts = get_africa_context(topic_text, k=3)
            africa_bonus = min(len(africa_contexts) / 3.0, 1.0) * 0.05  # max 5%
        except Exception:
            africa_bonus = 0.0

        # 95 % pure trending signal, 5 % optional regional bonus
        score = (0.95 * min(engagement / 1000, 1.0)) + africa_bonus
        return score
    except Exception:
        logger.error("Topic scoring failed", exc_info=True)
        return 0.0


def pick_best_topics(research_results: list[dict], max_picks: int = 2) -> list[dict]:
    """
    Filters out near-duplicates, scores remaining topics,
    returns top ``max_picks`` results.
    """
    filtered = []
    for result in research_results:
        topic_text = result.get("synthesis", "") or result.get("_topic", "")
        if not is_duplicate(topic_text):
            result["_score"] = score_topic(result)
            filtered.append(result)

    filtered.sort(key=lambda x: x["_score"], reverse=True)
    return filtered[:max_picks]
