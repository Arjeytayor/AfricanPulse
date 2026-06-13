"""Humanizer pass — light post-processing before delivery.

This module applies a final polish to generated content to catch common
AI-tell patterns, enforce style rules, and ensure the voice feels human.
"""

import re
from logger import logger

# Patterns that flag AI-generated text
FILLER_PHRASES = [
    r"\bdelv(?:e|ing)\s*(?:into|deeper into)",
    r"\bnavigate\s*(?:the|through|around)",
    r"\blandscape\b",
    r"\bit'?s\s+worth\s+noting\b",
    r"\bvibrant\s*tapestry\b",
    r"\bit\s+is\s+important\s+to\b",
    r"\bin\s+conclusion\b",
    r"\blet'?s?\s+dive\s+in\b",
    r"\bthe\s+reason\s+is\b",
    r"\bfurthermore\b",
    r"\bmoreover\b",
]


def _strip_filler(text: str) -> str:
    """Remove known AI filler phrases."""
    for pattern in FILLER_PHRASES:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    # Clean up double spaces / empty lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def _enforce_short_paragraphs(text: str, max_len: int = 120) -> str:
    """Break paragraph lines that exceed a rough visual limit."""
    paragraphs = text.split("\n\n")
    out = []
    for para in paragraphs:
        para = para.strip()
        if len(para) > max_len:
            # Simple sentence split for long paragraphs
            sentences = para.split(". ")
            lines = []
            current = ""
            for s in sentences:
                if len(current) + len(s) < max_len:
                    current += s + ". "
                else:
                    lines.append(current.strip().rstrip(". "))
                    current = s + ". "
            if current:
                lines.append(current.strip().rstrip(". "))
            out.append("\n".join(lines))
        else:
            out.append(para)
    return "\n\n".join(out)


def humanize(text: str) -> str:
    """Apply the full humanizer pass to generated content."""
    try:
        text = _strip_filler(text)
        text = _enforce_short_paragraphs(text)
        return text
    except Exception:
        logger.error("Humanizer pass failed", exc_info=True)
        return text
