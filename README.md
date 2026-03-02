# AI News Aggregator and Productivity Synthesizer

A local-first Streamlit app that collects AI news from your Gmail newsletters and RSS feeds, stores it in SQLite, and uses Gemini to produce a practical daily business briefing plus LinkedIn-ready content.

## What this is useful for

- Staying updated on AI launches without reading every newsletter manually
- Translating technical AI updates into business impact for Product, Marketing, Engineering, and Sales teams
- Turning one selected update into a polished LinkedIn post quickly
- Maintaining your own local history of AI updates for date-based review

## How it works

1. Ingestion layer (`ingestion.py`):
- Gmail API reads emails from a chosen label (default: `AI-News`) in the last 24 hours or a date range
- RSS parser reads entries from configured AI/tech feeds
- Social ingestion is a modular placeholder for future scraper API integration

2. Storage layer (`database.py`):
- Saves normalized records to local SQLite database (`ainews.db`)
- Deduplicates by URL first, then by exact content body

3. AI layer (`ai_engine.py`):
- Uses Gemini via `google-genai`
- Generates a structured daily briefing from selected records
- Generates LinkedIn post drafts using a fixed persona:
  Associate Director of Product in e-commerce/SaaS

4. UI layer (`app.py`):
- Sidebar lets you save keys/config, refresh data, and set feed sources
- Main tabs show daily briefing + raw source expanders + LinkedIn generator/editor

## Tech stack

- Frontend: Streamlit
- Backend: Python 3.10+
- Database: SQLite + SQLAlchemy
- Integrations: Gmail API, RSS (`feedparser`), Gemini (`google-genai`)

## Project structure

```text
.
├── app.py
├── ai_engine.py
├── database.py
├── ingestion.py
├── requirements.txt
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

## Setup

### 1) Clone and install

```bash
git clone https://github.com/garvitburad/AI_News_Tracker.git
cd AI_News_Tracker
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2) Configure environment

```bash
cp .env.example .env
```

Set these in `.env`:

- `GEMINI_API_KEY`: required, use your **Google AI Studio** Gemini API key
- `GENAI_MODEL`: optional (default `gemini-2.0-flash`)
- `GMAIL_LABEL`: Gmail label to ingest (default `AI-News`)
- `GOOGLE_OAUTH_CREDENTIALS_FILE`: OAuth client file path (default `credentials.json`)
- `GMAIL_TOKEN_FILE`: token cache file (default `token.json`)
- `RSS_FEEDS`: comma-separated RSS URLs
- `APIFY_API_KEY`: optional (for future social integration)

Note:
- `GOOGLE_GENAI_API_KEY` is still accepted for backward compatibility, but prefer `GEMINI_API_KEY`.

## Gemini key (Google AI Studio)

1. Open [Google AI Studio](https://aistudio.google.com/)
2. Create an API key
3. Put it in `.env` as:

```env
GEMINI_API_KEY=your_key_here
```

## Gmail connection setup

1. Open [Google Cloud Console](https://console.cloud.google.com/)
2. Create/select a project
3. Enable **Gmail API**
4. Configure **OAuth consent screen** (External is fine)
5. Add your Gmail as a test user (if in testing mode)
6. Create OAuth client credentials:
- APIs & Services > Credentials > Create Credentials > OAuth client ID
- App type: **Desktop app**
7. Download credentials JSON and place it in project root as `credentials.json`

On first refresh, browser OAuth opens and creates `token.json` locally.

## Run the app

```bash
source .venv/bin/activate
streamlit run app.py
```

Then:

1. In sidebar, add/save `GEMINI_API_KEY` and other settings
2. Click `Refresh Data (Last 24 Hours)`
3. Pick date range
4. Click `Generate Synthesized Briefing`
5. Open `LinkedIn Post Generator` tab and generate/edit post drafts

## Data model

SQLite file: `ainews.db`

Table: `articles`

- `id`
- `source_type` (`email`, `rss`, `social`)
- `author`
- `title`
- `content_body`
- `url`
- `published_date`
- `processed_status`

## Troubleshooting

- Gmail OAuth errors:
  Verify `credentials.json`, OAuth consent setup, and test-user permissions.
- Empty AI output:
  Verify `GEMINI_API_KEY` and internet access.
- No inserted records:
  Check date window, Gmail label, and duplicate filtering.

## Security

Do not commit these files:

- `.env`
- `credentials.json`
- `token.json`
- `ainews.db`

## License

See [LICENSE](./LICENSE).
