"""Database module for the local AI News dashboard.

This module manages:
1. SQLite initialization.
2. ORM model definitions.
3. Duplicate-safe insertion helpers.
4. Date-range query helpers.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any, Sequence

from sqlalchemy import Boolean, DateTime, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

DB_FILENAME = "ainews.db"
DATABASE_URL = f"sqlite:///{DB_FILENAME}"

# SQLAlchemy engine + session factory shared by the app.
engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy declarative models."""


class Article(Base):
    """Stores normalized content from email, RSS, and social sources."""

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_body: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True, index=True)
    published_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    processed_status: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


def init_db() -> None:
    """Create tables if they do not already exist."""
    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    """Return a new database session."""
    return SessionLocal()


def _is_duplicate(session: Session, payload: dict[str, Any]) -> bool:
    """Check duplicate rules using URL or exact content match.

    Duplicate policy:
    - If URL exists, treat an existing matching URL as duplicate.
    - Otherwise, fallback to exact `content_body` match.
    """
    content_body = (payload.get("content_body") or "").strip()
    url = (payload.get("url") or "").strip() or None

    if url:
        url_match_stmt = select(Article.id).where(Article.url == url).limit(1)
        if session.execute(url_match_stmt).first() is not None:
            return True

    if content_body:
        content_match_stmt = select(Article.id).where(Article.content_body == content_body).limit(1)
        if session.execute(content_match_stmt).first() is not None:
            return True

    return False


def insert_articles(records: Sequence[dict[str, Any]]) -> tuple[int, int]:
    """Insert records and skip duplicates.

    Returns:
        (inserted_count, skipped_count)
    """
    if not records:
        return (0, 0)

    inserted_count = 0
    skipped_count = 0

    with get_session() as session:
        for record in records:
            if _is_duplicate(session, record):
                skipped_count += 1
                continue

            article = Article(
                source_type=record.get("source_type", "unknown"),
                author=record.get("author"),
                title=record.get("title"),
                content_body=(record.get("content_body") or "").strip(),
                url=record.get("url"),
                published_date=record.get("published_date") or datetime.utcnow(),
                processed_status=bool(record.get("processed_status", False)),
            )
            session.add(article)
            inserted_count += 1

        session.commit()

    return (inserted_count, skipped_count)


def query_articles_by_date_range(start_date: date, end_date: date) -> list[Article]:
    """Fetch articles within an inclusive date range."""
    start_dt = datetime.combine(start_date, time.min)
    end_dt = datetime.combine(end_date, time.max)

    with get_session() as session:
        stmt = (
            select(Article)
            .where(Article.published_date >= start_dt, Article.published_date <= end_dt)
            .order_by(Article.published_date.desc())
        )
        return list(session.scalars(stmt).all())


def query_articles_for_last_hours(hours: int = 24) -> list[Article]:
    """Convenience query for recent windows (default: 24 hours)."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    with get_session() as session:
        stmt = select(Article).where(Article.published_date >= cutoff).order_by(Article.published_date.desc())
        return list(session.scalars(stmt).all())
