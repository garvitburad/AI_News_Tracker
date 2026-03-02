# AI News Aggregator and Productivity Synthesizer

A local-first Streamlit app that ingests AI updates from Gmail newsletters, RSS feeds, and modular social sources, stores everything in SQLite, and uses Google GenAI to generate:

- A daily executive AI briefing
- Function-specific productivity insights (Product, Marketing, Engineering, Sales)
- LinkedIn-ready post remixes from selected stories

## Features

- Gmail ingestion with OAuth (`AI-News` label by default)
- RSS ingestion from configurable feed list
- Social ingestion placeholder (modular hook for Apify or any scraper API)
- SQLite persistence with duplicate-safe inserts
- Date-range filtering for historical briefings
- LLM-generated daily synthesis and LinkedIn post generation
- Local `.env` configuration from Streamlit sidebar

## Project Structure

```text
.
├── app.py               # Streamlit UI
├── ai_engine.py         # LLM summarization + LinkedIn remix
├── database.py          # SQLAlchemy models and DB helpers
├── ingestion.py         # Gmail/RSS/social ingestion
├── requirements.txt     # Pinned Python dependencies
├── .env.example         # Environment variable template
├── LICENSE
└── README.md
```

## Prerequisites

- Python 3.10+
- Google account for Gmail API access
- Google GenAI API key

## 1. Clone and Set Up

```bash
git clone https://github.com/garvitburad/AI_News_Tracker.git
cd AI_News_Tracker
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 2. Configure Environment Variables

Copy and edit the template:

```bash
cp .env.example .env
```

Set values in `.env`:

- `GOOGLE_GENAI_API_KEY`: required for briefing/post generation
- `GENAI_MODEL`: optional model override (`gemini-2.0-flash` default)
- `GMAIL_LABEL`: Gmail label to ingest from (`AI-News` default)
- `RSS_FEEDS`: comma-separated feed URLs
- `GOOGLE_OAUTH_CREDENTIALS_FILE`: Gmail OAuth credentials file path (`credentials.json`)
- `GMAIL_TOKEN_FILE`: OAuth token cache path (`token.json`)
- `APIFY_API_KEY`: optional (social ingestion placeholder)

## 3. Gmail API Setup (Google Cloud Console)

1. Open Google Cloud Console: https://console.cloud.google.com/
2. Create/select a project.
3. Enable **Gmail API** for the project.
4. Go to **APIs & Services > OAuth consent screen** and configure:
   - App type: External (or Internal if Workspace)
   - Add your test user email if app is in testing mode
5. Go to **APIs & Services > Credentials > Create Credentials > OAuth client ID**.
6. Choose **Desktop app**.
7. Download the credentials JSON and place it in project root as `credentials.json` (or update `GOOGLE_OAUTH_CREDENTIALS_FILE`).
8. On first Gmail refresh in the app, browser OAuth will open and create `token.json`.

## 4. Run the App

```bash
streamlit run app.py
```

Then in the sidebar:

1. Add/save API keys and feed config.
2. Click **Refresh Data (Last 24 Hours)**.
3. Select date range and click **Generate Synthesized Briefing**.
4. In **LinkedIn Post Generator**, pick an item and click **Generate LinkedIn Post**.

## Data Model

SQLite database file: `ainews.db`

`articles` table columns:

- `id`
- `source_type` (`email`, `rss`, `social`)
- `author`
- `title`
- `content_body`
- `url`
- `published_date`
- `processed_status`

Duplicate handling:

- Skips insert if URL already exists
- Falls back to exact content-body dedupe when URL is missing

## Notes on Social Ingestion

`ingestion.py` includes `fetch_social_posts(...)` as a provider-agnostic placeholder. Wire in Apify (or another service) by replacing this function body while preserving normalized output fields.

## Troubleshooting

- Gmail ingestion fails with missing credentials:
  - Ensure `credentials.json` exists and path matches `.env`.
- OAuth fails for unverified app:
  - Add your account as a test user in OAuth consent screen.
- Empty LLM output:
  - Verify `GOOGLE_GENAI_API_KEY` and internet connectivity.
- No new records inserted:
  - Check date window and dedupe behavior.

## Security

- Do not commit `.env`, `credentials.json`, `token.json`, or `ainews.db`.
- Rotate keys if accidentally exposed.

## License

See [LICENSE](./LICENSE).
