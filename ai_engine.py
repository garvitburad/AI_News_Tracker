"""AI processing module using google-genai for synthesis and LinkedIn remix."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Sequence

from google import genai


@dataclass
class AIEngine:
    """Wrapper around Google GenAI SDK with opinionated prompts."""

    api_key: str
    model: str = "gemini-2.0-flash"

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError("Missing GOOGLE_GENAI_API_KEY.")
        self.client = genai.Client(api_key=self.api_key)

    def generate_daily_briefing(
        self,
        articles: Sequence[Any],
        start_date: date,
        end_date: date,
    ) -> str:
        """Generate a structured daily briefing from aggregated content."""
        if not articles:
            return "No source content found in the selected date range."

        context = self._build_articles_context(articles)
        prompt = f"""
You are an expert AI industry analyst and productivity strategist.

Analyze the source content below from {start_date.isoformat()} to {end_date.isoformat()}.

Your output must be a concise but information-dense daily briefing with these sections:

1) Top AI Breakthroughs & Launches
- Prioritize concrete launches, model updates, benchmark results, funding, and product announcements.
- Group related updates and avoid repeating the same story.

2) Practical Productivity Tools by Function
- Extract tools or capabilities that can improve team productivity.
- For each function below, include at least one practical workflow improvement if evidence exists:
  - Product
  - Marketing
  - Engineering
  - Sales
- For each item, include:
  - Tool / capability name
  - What changed
  - Why it matters
  - Example workflow impact in one sentence

3) Executive Takeaways
- 3-5 bullets for cross-functional leadership.
- Focus on adoption signals, implementation risks, and near-term opportunities.

Formatting rules:
- Use markdown headings and short bullet points.
- Keep language factual and actionable.
- Avoid hype and unsupported claims.

Source content:
{context}
""".strip()

        return self._call_model(prompt)

    def generate_linkedin_post(self, source_text: str) -> str:
        """Remix one selected item into a polished LinkedIn post."""
        prompt = f"""
You are writing a LinkedIn post as an Associate Director of Product in the e-commerce and SaaS ecosystem.

Tone and style constraints:
- Analytical and product-focused.
- Bridge technical AI developments with practical business and merchant impact.
- Professional, clear, and insightful.
- Avoid sensational language.

Task:
Transform the source material into a highly engaging LinkedIn post.

Post structure:
- Strong opening hook (1 sentence).
- 2-4 short paragraphs that explain what happened and why it matters.
- 3 actionable takeaways for product and business teams.
- End with a thoughtful question to spark discussion.
- Add 5-8 relevant hashtags.

Source material:
{source_text}
""".strip()

        return self._call_model(prompt)

    def _call_model(self, prompt: str) -> str:
        """Run model inference and extract text safely."""
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
        )

        if hasattr(response, "text") and response.text:
            return response.text.strip()

        # Fallback for structured candidates when `.text` is absent.
        parts: list[str] = []
        for candidate in getattr(response, "candidates", []) or []:
            content = getattr(candidate, "content", None)
            if not content:
                continue
            for part in getattr(content, "parts", []) or []:
                text_value = getattr(part, "text", None)
                if text_value:
                    parts.append(text_value)

        return "\n".join(parts).strip() or "Model returned an empty response."

    def _build_articles_context(self, articles: Sequence[Any], max_chars: int = 45000) -> str:
        """Flatten article objects/dicts into bounded prompt context."""
        chunks: list[str] = []
        total_chars = 0

        for article in articles:
            source_type = self._get_value(article, "source_type") or "unknown"
            title = self._get_value(article, "title") or "Untitled"
            author = self._get_value(article, "author") or "Unknown author"
            published = self._get_value(article, "published_date") or "Unknown date"
            body = self._get_value(article, "content_body") or ""
            url = self._get_value(article, "url") or "N/A"

            chunk = (
                f"Source: {source_type}\n"
                f"Title: {title}\n"
                f"Author: {author}\n"
                f"Published: {published}\n"
                f"URL: {url}\n"
                f"Body:\n{body}\n"
                "-----\n"
            )

            if total_chars + len(chunk) > max_chars:
                break

            chunks.append(chunk)
            total_chars += len(chunk)

        return "\n".join(chunks)

    @staticmethod
    def _get_value(item: Any, key: str) -> Any:
        """Read key from dict-like or object-like inputs."""
        if isinstance(item, dict):
            return item.get(key)
        return getattr(item, key, None)
