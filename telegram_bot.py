"""Telegram delivery — briefing card, article, script, file attachments."""

import os
import requests

import config
from logger import logger
from datetime import date

BASE_URL = f"https://api.telegram.org/bot{config.BOT_TOKEN}"


def _split_html_safe(text: str, max_len: int = 4000) -> list[str]:
    """Split ``text`` into chunks that do NOT break HTML tags."""
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break

        # Find the last safe split point before max_len
        split_point = text.rfind("\n", 0, max_len)
        if split_point == -1:
            split_point = text.rfind(" ", 0, max_len)
        if split_point == -1:
            split_point = max_len  # hard cut — last resort

        chunk = text[:split_point]
        # If this chunk opened a tag that it didn't close, shift to previous break
        open_tags = chunk.count("<") - chunk.count(">")
        if open_tags > 0:
            alt = text.rfind("\n", 0, split_point - 20)
            if alt > 0:
                split_point = alt
                chunk = text[:split_point]

        chunks.append(chunk)
        text = text[split_point:].lstrip("\n ")
    return chunks


def send_message(text: str, parse_mode: str = "HTML") -> bool:
    try:
        chunks = _split_html_safe(text)
        for chunk in chunks:
            resp = requests.post(
                f"{BASE_URL}/sendMessage",
                json={"chat_id": config.CHAT_ID, "text": chunk, "parse_mode": parse_mode},
                timeout=15
            )
            resp.raise_for_status()
        return True
    except Exception:
        logger.error("Telegram send_message failed", exc_info=True)
        return False


def send_file(filepath: str, caption: str = "") -> bool:
    # Guard: file must exist and be non-empty for Telegram to accept it
    if not filepath or not os.path.exists(filepath):
        logger.warning(f"Telegram send_file: file does not exist: {filepath}")
        return False
    try:
        file_size = os.path.getsize(filepath)
        if file_size == 0:
            logger.warning(f"Telegram send_file: file is empty: {filepath}")
            return False
        with open(filepath, "rb") as f:
            resp = requests.post(
                f"{BASE_URL}/sendDocument",
                data={"chat_id": config.CHAT_ID, "caption": caption},
                files={"document": f},
                timeout=30
            )
            resp.raise_for_status()
        return True
    except requests.exceptions.HTTPError as e:
        # Log the actual Telegram response for debugging 400 errors
        try:
            error_detail = resp.json()
            logger.error(f"Telegram send_file HTTP {e.response.status_code}: {error_detail}")
        except Exception:
            logger.error(f"Telegram send_file HTTP {e.response.status_code}: {e}")
        return False
    except Exception:
        logger.error("Telegram send_file failed", exc_info=True)
        return False


def send_daily_output(
    briefing: str,
    article: str,
    script: str,
    article_path: str,
    script_path: str,
    article_orig_path: str = "",
    script_orig_path: str = "",
    article_humanized: str = "",
    script_humanized: str = ""
) -> None:
    """Send briefing, article, script, and attachments in sequence.

    If humanizer was applied, sends:
      - Original first (so user sees raw content before polish)
      - Then humanized version
    If humanizer was skipped, only original is sent.
    """
    send_message(briefing)

    # Always send original first — user sees raw stories before any polish
    send_message("📝 <b>ORIGINAL ARTICLE DRAFT</b>\n📋 (Raw — before humanizer)")
    if article_orig_path and os.path.exists(article_orig_path):
        with open(article_orig_path, "r", encoding="utf-8") as f:
            original_article = f.read()
        send_message(
            f"📝 <b>ARTICLE — WorldPulse</b>\n"
            f"{'━'*20}\n\n{original_article}\n{'━'*20}\n"
        )
        send_file(article_orig_path, caption="Original article .md")
    else:
        send_message(
            f"📝 <b>ARTICLE — WorldPulse</b>\n"
            f"{'━'*20}\n\n{article}\n{'━'*20}\n"
        )
        send_file(article_path, caption="Article .md file")

    # If humanizer was applied, also send the polished version
    if article_humanized:
        send_message("✨ <b>HUMANIZED VERSION (optional)</b>\n" + "━"*20)
        send_message(article_humanized)
        send_file(article_path, caption="Humanized article .md")

    # Same for script
    send_message("🎬 <b>ORIGINAL SCRIPT DRAFT</b>\n📋 (Raw — before humanizer)")
    if script_orig_path and os.path.exists(script_orig_path):
        with open(script_orig_path, "r", encoding="utf-8") as f:
            original_script = f.read()
        send_message(
            f"🎬 <b>SHORTS SCRIPT — WorldPulse</b>\n"
            f"{'━'*20}\n\n{original_script}\n{'━'*20}\n"
            f"🎙️ [OVERLAY] = text in CapCut. [PAUSE] = breath."
        )
        send_file(script_orig_path, caption="Original script .md")
    else:
        send_message(
            f"🎬 <b>SHORTS SCRIPT — WorldPulse</b>\n"
            f"{'━'*20}\n\n{script}\n{'━'*20}\n"
            f"🎙️ [OVERLAY] = text in CapCut. [PAUSE] = breath."
        )
        send_file(script_path, caption="Script .md file")

    if script_humanized:
        send_message("✨ <b>HUMANIZED SCRIPT (optional)</b>\n" + "━"*20)
        send_message(script_humanized)
        send_file(script_path, caption="Humanized script .md")
