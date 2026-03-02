"""Data ingestion module for Gmail, RSS, and social sources."""

from __future__ import annotations

import base64
import logging
import os
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Iterable

import feedparser
from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

LOGGER = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def _to_utc_naive(dt: datetime) -> datetime:
    """Normalize datetimes to UTC without timezone for SQLite storage."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _to_aware_utc(dt: datetime) -> datetime:
    """Normalize datetime values to timezone-aware UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _strip_html(raw: str) -> str:
    """Return plain text from HTML or raw text input."""
    if not raw:
        return ""
    soup = BeautifulSoup(raw, "html.parser")
    return soup.get_text("\n", strip=True)


def _decode_message_part(data: str | None) -> str:
    """Decode Gmail URL-safe base64 payload."""
    if not data:
        return ""
    decoded = base64.urlsafe_b64decode(data.encode("utf-8"))
    return decoded.decode("utf-8", errors="ignore")


def _extract_text_from_gmail_payload(payload: dict[str, Any]) -> str:
    """Walk Gmail MIME parts and return best-effort plain text content."""

    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data")

    if mime_type == "text/plain" and body_data:
        return _decode_message_part(body_data)

    if mime_type == "text/html" and body_data:
        return _strip_html(_decode_message_part(body_data))

    combined_parts: list[str] = []
    for part in payload.get("parts", []) or []:
        part_text = _extract_text_from_gmail_payload(part)
        if part_text:
            combined_parts.append(part_text)

    if combined_parts:
        return "\n\n".join(combined_parts)

    if body_data:
        return _strip_html(_decode_message_part(body_data))

    return ""


def authenticate_gmail(
    credentials_path: str = "credentials.json",
    token_path: str = "token.json",
):
    """Authenticate Gmail API via OAuth and return a Gmail service client."""
    creds: Credentials | None = None

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    f"Missing OAuth credentials file: {credentials_path}. "
                    "Download it from Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def _gmail_query(label: str, start_dt: datetime, end_dt: datetime) -> str:
    """Build Gmail search query for label and time window."""
    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())
    return f"label:{label} after:{start_ts} before:{end_ts}"


def fetch_gmail_articles(
    label: str = "AI-News",
    start_datetime: datetime | None = None,
    end_datetime: datetime | None = None,
    max_results: int = 100,
    credentials_path: str = "credentials.json",
    token_path: str = "token.json",
) -> list[dict[str, Any]]:
    """Fetch Gmail messages in a date window and normalize to article records."""
    end_dt = end_datetime or datetime.now(timezone.utc)
    start_dt = start_datetime or (end_dt - timedelta(hours=24))

    start_dt = _to_aware_utc(start_dt)
    end_dt = _to_aware_utc(end_dt)

    service = authenticate_gmail(credentials_path=credentials_path, token_path=token_path)
    query = _gmail_query(label=label, start_dt=start_dt, end_dt=end_dt)

    response = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )
    message_refs = response.get("messages", [])

    articles: list[dict[str, Any]] = []

    for msg_ref in message_refs:
        message_id = msg_ref.get("id")
        if not message_id:
            continue

        full_msg = (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )

        payload = full_msg.get("payload", {})
        headers = {h.get("name", "").lower(): h.get("value", "") for h in payload.get("headers", [])}
        raw_body = _extract_text_from_gmail_payload(payload)

        published_header = headers.get("date")
        if published_header:
            published_date = _to_utc_naive(parsedate_to_datetime(published_header))
        else:
            internal_ms = int(full_msg.get("internalDate", "0"))
            published_date = datetime.utcfromtimestamp(internal_ms / 1000) if internal_ms else datetime.utcnow()

        articles.append(
            {
                "source_type": "email",
                "author": headers.get("from"),
                "title": headers.get("subject", "No Subject"),
                "content_body": _strip_html(raw_body),
                "url": f"gmail://{message_id}",
                "published_date": published_date,
                "processed_status": False,
            }
        )

    LOGGER.info("Fetched %s email articles", len(articles))
    return articles


def fetch_rss_articles(
    feed_urls: Iterable[str],
    start_datetime: datetime | None = None,
    end_datetime: datetime | None = None,
) -> list[dict[str, Any]]:
    """Fetch and normalize entries from a configurable RSS feed list."""
    end_dt = _to_utc_naive(end_datetime or datetime.utcnow())
    start_dt = _to_utc_naive(start_datetime or (datetime.utcnow() - timedelta(hours=24)))

    articles: list[dict[str, Any]] = []

    for feed_url in feed_urls:
        if not feed_url:
            continue

        parsed_feed = feedparser.parse(feed_url)

        for entry in parsed_feed.entries:
            published_dt: datetime
            if getattr(entry, "published_parsed", None):
                published_dt = datetime(*entry.published_parsed[:6])
            elif getattr(entry, "updated_parsed", None):
                published_dt = datetime(*entry.updated_parsed[:6])
            else:
                published_dt = datetime.utcnow()

            published_dt = _to_utc_naive(published_dt)
            if not (start_dt <= published_dt <= end_dt):
                continue

            content_html = ""
            if getattr(entry, "content", None):
                content_html = "\n".join(item.get("value", "") for item in entry.content)
            else:
                content_html = getattr(entry, "summary", "")

            articles.append(
                {
                    "source_type": "rss",
                    "author": getattr(entry, "author", None),
                    "title": getattr(entry, "title", "Untitled RSS Entry"),
                    "content_body": _strip_html(content_html),
                    "url": getattr(entry, "link", None),
                    "published_date": published_dt,
                    "processed_status": False,
                }
            )

    LOGGER.info("Fetched %s RSS articles", len(articles))
    return articles


def fetch_social_posts(
    api_key: str | None,
    start_datetime: datetime | None = None,
    end_datetime: datetime | None = None,
    query_terms: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Placeholder for social ingestion (X/LinkedIn) via scraper APIs.

    This function intentionally returns an empty list until a concrete provider is wired.
    The rest of the app remains functional and future integrations can swap this with
    a provider-specific client (for example, Apify actors).
    """
    _ = (start_datetime, end_datetime, query_terms)

    if not api_key:
        LOGGER.info("No social API key provided; skipping social ingestion.")
        return []

    LOGGER.info(
        "Social ingestion placeholder called. Add scraper API logic here (e.g., Apify actor run)."
    )
    return []
