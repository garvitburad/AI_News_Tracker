"""Streamlit frontend for local AI News Aggregator and Productivity Synthesizer."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv, set_key

from ai_engine import AIEngine
from database import init_db, insert_articles, query_articles_by_date_range
from ingestion import fetch_gmail_articles, fetch_rss_articles, fetch_social_posts

load_dotenv()

st.set_page_config(page_title="AI News Aggregator", page_icon="AI", layout="wide")


DEFAULT_RSS_FEEDS = [
    "https://feeds.feedburner.com/oreilly/radar/atom",
    "https://www.marktechpost.com/feed",
    "https://www.unite.ai/feed/",
]


# Initialize database early to ensure all interactions have storage ready.
init_db()


# ------------------------------
# Helpers
# ------------------------------
def save_env_values(values: dict[str, str]) -> None:
    """Persist sidebar configuration to a local `.env` file."""
    env_path = Path(".env")
    if not env_path.exists():
        env_path.touch()

    for key, value in values.items():
        set_key(str(env_path), key, value)
        os.environ[key] = value


def parse_rss_input(raw_text: str) -> list[str]:
    """Parse comma/newline-separated RSS URL input into a cleaned list."""
    parts = [piece.strip() for chunk in raw_text.splitlines() for piece in chunk.split(",")]
    return [part for part in parts if part]


def normalize_date_range(selected: object) -> tuple[date, date]:
    """Normalize Streamlit date input output into `(start_date, end_date)` tuple."""
    if isinstance(selected, tuple) and len(selected) == 2:
        return selected[0], selected[1]
    if isinstance(selected, list) and len(selected) == 2:
        return selected[0], selected[1]
    if isinstance(selected, date):
        return selected, selected

    end_date = date.today()
    return end_date - timedelta(days=1), end_date


def get_ai_engine(api_key: str) -> AIEngine:
    """Create AI engine from current runtime config."""
    model_name = os.getenv("GENAI_MODEL", "gemini-2.0-flash")
    return AIEngine(api_key=api_key, model=model_name)


def get_genai_api_key() -> str:
    """Return Gemini key, preferring AI Studio naming."""
    return os.getenv("GEMINI_API_KEY", "").strip() or os.getenv("GOOGLE_GENAI_API_KEY", "").strip()


# ------------------------------
# Sidebar: data actions + config
# ------------------------------
st.sidebar.header("Data Refresh")

if st.sidebar.button("Refresh Data (Last 24 Hours)", use_container_width=True):
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(hours=24)

    label = os.getenv("GMAIL_LABEL", "AI-News")
    credentials_path = os.getenv("GOOGLE_OAUTH_CREDENTIALS_FILE", "credentials.json")
    token_path = os.getenv("GMAIL_TOKEN_FILE", "token.json")
    apify_api_key = os.getenv("APIFY_API_KEY", "")

    rss_env = os.getenv("RSS_FEEDS", "")
    rss_feeds = parse_rss_input(rss_env) if rss_env else DEFAULT_RSS_FEEDS

    all_records: list[dict] = []

    with st.spinner("Refreshing data from Gmail, RSS, and social sources..."):
        try:
            all_records.extend(
                fetch_gmail_articles(
                    label=label,
                    start_datetime=start_dt,
                    end_datetime=end_dt,
                    credentials_path=credentials_path,
                    token_path=token_path,
                )
            )
        except Exception as exc:
            st.warning(f"Gmail ingestion skipped: {exc}")

        try:
            all_records.extend(fetch_rss_articles(feed_urls=rss_feeds, start_datetime=start_dt, end_datetime=end_dt))
        except Exception as exc:
            st.warning(f"RSS ingestion skipped: {exc}")

        try:
            all_records.extend(
                fetch_social_posts(
                    api_key=apify_api_key,
                    start_datetime=start_dt,
                    end_datetime=end_dt,
                    query_terms=["AI", "LLM", "productivity", "agentic AI"],
                )
            )
        except Exception as exc:
            st.warning(f"Social ingestion skipped: {exc}")

        inserted_count, skipped_count = insert_articles(all_records)

    st.success(
        f"Refresh completed. Inserted {inserted_count} records, skipped {skipped_count} duplicates."
    )

st.sidebar.divider()
st.sidebar.subheader("Configuration")

genai_api_key_val = st.sidebar.text_input(
    "Gemini API Key (Google AI Studio)",
    value=get_genai_api_key(),
    type="password",
)
apify_api_key_val = st.sidebar.text_input(
    "Apify API Key (Optional)",
    value=os.getenv("APIFY_API_KEY", ""),
    type="password",
)
gmail_label_val = st.sidebar.text_input("Gmail Label", value=os.getenv("GMAIL_LABEL", "AI-News"))

rss_default_input = os.getenv("RSS_FEEDS", ",".join(DEFAULT_RSS_FEEDS)).replace(",", "\n")
rss_feeds_val = st.sidebar.text_area(
    "RSS Feeds (one URL per line)",
    value=rss_default_input,
    height=160,
)

if st.sidebar.button("Save Configuration", use_container_width=True):
    save_env_values(
        {
            "GEMINI_API_KEY": genai_api_key_val.strip(),
            # Backward compatibility for older env naming in this project.
            "GOOGLE_GENAI_API_KEY": genai_api_key_val.strip(),
            "APIFY_API_KEY": apify_api_key_val.strip(),
            "GMAIL_LABEL": gmail_label_val.strip() or "AI-News",
            "RSS_FEEDS": ",".join(parse_rss_input(rss_feeds_val)),
            "GOOGLE_OAUTH_CREDENTIALS_FILE": os.getenv("GOOGLE_OAUTH_CREDENTIALS_FILE", "credentials.json"),
            "GMAIL_TOKEN_FILE": os.getenv("GMAIL_TOKEN_FILE", "token.json"),
            "GENAI_MODEL": os.getenv("GENAI_MODEL", "gemini-2.0-flash"),
        }
    )
    st.sidebar.success("Configuration saved to .env")


# ------------------------------
# Main page: briefing + remix
# ------------------------------
st.title("AI News Aggregator & Productivity Synthesizer")
st.caption("Local-first dashboard for AI updates, practical team impact, and LinkedIn-ready insights.")

default_end = date.today()
default_start = default_end - timedelta(days=1)
selected_dates = st.date_input("Date Range", value=(default_start, default_end))
start_date, end_date = normalize_date_range(selected_dates)

articles = query_articles_by_date_range(start_date=start_date, end_date=end_date)

briefing_tab, linkedin_tab = st.tabs(["Daily Briefing", "LinkedIn Post Generator"])

with briefing_tab:
    st.subheader("Daily Briefing")
    st.write(f"Loaded **{len(articles)}** articles between **{start_date}** and **{end_date}**.")

    if st.button("Generate Synthesized Briefing", type="primary"):
        api_key = get_genai_api_key()
        if not api_key:
            st.error("Missing GEMINI_API_KEY. Add your Google AI Studio key in sidebar configuration.")
        elif not articles:
            st.warning("No articles found for the selected date range.")
        else:
            with st.spinner("Generating daily briefing..."):
                engine = get_ai_engine(api_key)
                st.session_state["daily_briefing_text"] = engine.generate_daily_briefing(
                    articles=articles,
                    start_date=start_date,
                    end_date=end_date,
                )

    if st.session_state.get("daily_briefing_text"):
        st.markdown(st.session_state["daily_briefing_text"])

    st.markdown("---")
    st.subheader("Raw Source Content")

    if not articles:
        st.info("No source records available for this date range.")
    else:
        for article in articles:
            title = article.title or "Untitled"
            source = article.source_type
            published = article.published_date.strftime("%Y-%m-%d %H:%M")
            with st.expander(f"[{source.upper()}] {title} ({published})"):
                st.write(f"**Author:** {article.author or 'Unknown'}")
                st.write(f"**Published:** {published}")
                if article.url:
                    st.write(f"**URL:** {article.url}")
                st.write(article.content_body)

with linkedin_tab:
    st.subheader("LinkedIn Post Generator")

    if not articles:
        st.info("Select a date range with available articles to generate a LinkedIn post.")
    else:
        options = {
            f"{idx + 1}. {(article.title or 'Untitled')[:120]} ({article.source_type})": article
            for idx, article in enumerate(articles)
        }
        selected_label = st.selectbox("Choose a source item", options=list(options.keys()))
        selected_article = options[selected_label]

        if st.button("Generate LinkedIn Post"):
            api_key = get_genai_api_key()
            if not api_key:
                st.error("Missing GEMINI_API_KEY. Add your Google AI Studio key in sidebar configuration.")
            else:
                source_text = (
                    f"Title: {selected_article.title}\n"
                    f"Source: {selected_article.source_type}\n"
                    f"Author: {selected_article.author}\n"
                    f"Published: {selected_article.published_date}\n"
                    f"URL: {selected_article.url}\n\n"
                    f"Content:\n{selected_article.content_body}"
                )
                with st.spinner("Generating LinkedIn post..."):
                    engine = get_ai_engine(api_key)
                    st.session_state["linkedin_post_text"] = engine.generate_linkedin_post(source_text)

        linkedin_default = st.session_state.get("linkedin_post_text", "")
        st.text_area(
            "Generated Post (Editable)",
            value=linkedin_default,
            height=320,
            key="linkedin_post_editor",
        )
