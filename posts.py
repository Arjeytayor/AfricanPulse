"""Publish content to Substack and X (Twitter).

All functions are non-blocking and return bool success indicators
so the pipeline continues even if a post fails.

Configuration (environment variables):

Substack (email-to-post — recommended):
    SUBSTACK_SMTP_SERVER    — SMTP server (e.g. smtp.gmail.com)
    SUBSTACK_SMTP_PORT      — SMTP port (e.g. 587)
    SUBSTACK_SMTP_USER      — SMTP login email
    SUBSTACK_SMTP_PASSWORD  — SMTP password / app password
    SUBSTACK_POST_EMAIL     — Your Substack post-by-email address

X / Twitter (API v2):
    X_API_KEY               — Consumer Key
    X_API_SECRET            — Consumer Secret
    X_ACCESS_TOKEN          — Access Token
    X_ACCESS_SECRET         — Access Token Secret
"""

from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import requests

from logger import logger

# ── Optional tweepy import ────────────────────────────────
try:
    import tweepy

    _TWEEPY_OK = True
except ImportError:  # pragma: no cover
    _TWEEPY_OK = False

# ── Configuration ──────────────────────────────────────────

SUBSTACK_SMTP_SERVER = os.environ.get("SUBSTACK_SMTP_SERVER", "")
SUBSTACK_SMTP_PORT = int(os.environ.get("SUBSTACK_SMTP_PORT", "587"))
SUBSTACK_SMTP_USER = os.environ.get("SUBSTACK_SMTP_USER", "")
SUBSTACK_SMTP_PASSWORD = os.environ.get("SUBSTACK_SMTP_PASSWORD", "")
SUBSTACK_POST_EMAIL = os.environ.get("SUBSTACK_POST_EMAIL", "")

X_API_KEY = os.environ.get("X_API_KEY", "")
X_API_SECRET = os.environ.get("X_API_SECRET", "")
X_ACCESS_TOKEN = os.environ.get("X_ACCESS_TOKEN", "")
X_ACCESS_SECRET = os.environ.get("X_ACCESS_SECRET", "")

# ── Helpers ────────────────────────────────────────────────

def _truncate(text: str, limit: int = 280) -> str:
    """Truncate *text* so it does not exceed *limit* chars."""
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _has_substack_config() -> bool:
    """Return True if all required Substack SMTP variables are set."""
    return all(
        (SUBSTACK_SMTP_SERVER, SUBSTACK_SMTP_USER, SUBSTACK_SMTP_PASSWORD, SUBSTACK_POST_EMAIL)
    )


def _has_x_config() -> bool:
    """Return True if all required X API variables are set."""
    return all((X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET))

# ── Substack ──────────────────────────────────────────────

def post_substack_email(title: str, body: str, *, excerpt: str = "", publish: bool = False) -> bool:
    """Send an article to Substack via their email-to-post feature.

    Substack automatically converts the email into a draft post.
    If ``publish=True`` it still appears as a draft — manual review
    before hitting ``Publish`` is recommended.

    Returns *True* on success, *False* on failure.
    """
    if not _has_substack_config():
        logger.warning("Substack SMTP not configured — skipping newsletter post")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = title
    msg["From"] = SUBSTACK_SMTP_USER
    msg["To"] = SUBSTACK_POST_EMAIL

    # Substack uses the first line after the subject as the excerpt/summary
    html = f"""\
<html><body>
{excerpt or title}
<br><br>
{body.replace(chr(10), "<br>")}
</body></html>
"""
    msg.attach(MIMEText(body, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(SUBSTACK_SMTP_SERVER, SUBSTACK_SMTP_PORT) as server:
            server.starttls()
            server.login(SUBSTACK_SMTP_USER, SUBSTACK_SMTP_PASSWORD)
            server.sendmail(SUBSTACK_SMTP_USER, SUBSTACK_POST_EMAIL, msg.as_string())

        status = "sent (draft on Substack)" if not publish else "sent (review draft on Substack)"
        logger.info(f"Substack email-to-post {status}: {title}")
        return True
    except Exception as exc:
        logger.error(f"Substack email failed: {exc}")
        return False

# ── X / Twitter ──────────────────────────────────────────

def _x_client():
    """Return an authenticated tweepy Client or None."""
    if not _TWEEPY_OK:
        logger.warning("tweepy not installed — cannot post to X")
        return None
    if not _has_x_config():
        logger.warning("X API credentials not configured — skipping X post")
        return None
    try:
        client = tweepy.Client(
            consumer_key=X_API_KEY,
            consumer_secret=X_API_SECRET,
            access_token=X_ACCESS_TOKEN,
            access_token_secret=X_ACCESS_SECRET,
        )
        # Lightweight auth check
        me = client.get_me()
        if me.errors:
            raise RuntimeError(str(me.errors))
        logger.debug(f"X client authenticated as @{me.data['username']}")
        return client
    except Exception as exc:
        logger.warning(f"X authentication failed: {exc}")
        return None


def post_x(text: str, *, media_path: Optional[str] = None) -> bool:
    """Post a tweet to X.

    Automatically truncates to 280 chars.  Optional *media_path*
    uploads a single image.

    Returns *True* on success, *False* on failure.
    """
    client = _x_client()
    if not client:
        return False

    text = _truncate(text)

    media_id = None
    if media_path:
        try:
            # v1.1 auth required for media upload
            v1_auth = tweepy.OAuth1UserHandler(
                consumer_key=X_API_KEY,
                consumer_secret=X_API_SECRET,
                access_token=X_ACCESS_TOKEN,
                access_token_secret=X_ACCESS_SECRET,
            )
            v1_api = tweepy.API(v1_auth)
            media = v1_api.media_upload(media_path)
            media_id = media.media_id
        except Exception as exc:
            logger.warning(f"X media upload failed: {exc}")

    try:
        if media_id:
            client.create_tweet(text=text, media_ids=[media_id])
        else:
            client.create_tweet(text=text)
        logger.info(f"Posted to X: {_truncate(text, 60)}")
        return True
    except Exception as exc:
        logger.error(f"X post failed: {exc}")
        return False


def post_x_thread(tweets: list[str]) -> list[str]:
    """Post a thread (list of tweets) to X.

    Each tweet replies to the previous one.  Automatically
    truncates each tweet to 280 chars.

    Returns list of tweet IDs that were successfully posted.
    """
    client = _x_client()
    if not client:
        return []

    tweet_ids: list[str] = []
    reply_to: Optional[str] = None

    for raw_tweet in tweets:
        tweet = _truncate(raw_tweet)
        try:
            if reply_to:
                resp = client.create_tweet(text=tweet, in_reply_to_tweet_id=reply_to)
            else:
                resp = client.create_tweet(text=tweet)
            tweet_id = resp.data["id"]
            tweet_ids.append(str(tweet_id))
            reply_to = tweet_id
            logger.info(f"Thread tweet posted: {tweet_id}")
        except Exception as exc:
            logger.error(f"Thread tweet failed: {exc}")
            break

    return tweet_ids

# ── High-level wrappers ───────────────────────────────────

def publish_article(title: str, article: str, *, excerpt: str = "", publish: bool = False) -> bool:
    """Publish a full article to Substack.

    Convenience wrapper around :func:`post_substack_email`.
    """
    return post_substack_email(title, article, excerpt=excerpt, publish=publish)


def post_short(text: str, *, media_path: Optional[str] = None) -> bool:
    """Post a single short tweet to X.

    Convenience wrapper around :func:`post_x`.
    """
    return post_x(text, media_path=media_path)
