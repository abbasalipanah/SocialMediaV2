"""Scheduled low-cost comment sentiment runner."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging

from sqlalchemy import create_engine, text

from app.application.services import CommentSentimentCoordinator
from app.core import ConfigurationError, WritePolicy, load_settings
from app.infrastructure.persistence.social_v2 import SocialCommentStore
from app.infrastructure.providers.ai import OpenRouterCommentSentimentProvider

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify stored social comments")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--scheduled", action="store_true")
    args = parser.parse_args(argv)
    settings = load_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(message)s",
        force=True,
    )
    if args.scheduled and not settings.worker_schedule_enabled:
        raise ConfigurationError("Scheduled sentiment is disabled")
    if not settings.db.url:
        raise ConfigurationError("Comment sentiment requires SOCIAL_DB_URL")
    if not settings.ai_summary.configured:
        raise ConfigurationError("Comment sentiment provider is not configured")
    policy = WritePolicy.from_settings(settings)
    policy.assert_allows_mutation("comment.sentiment")
    engine = create_engine(settings.db.url, pool_pre_ping=True, pool_size=2, max_overflow=0)
    lock = engine.connect()
    acquired = bool(
        lock.execute(
            text("SELECT pg_try_advisory_lock(hashtext(:name))"),
            {"name": "social_media_v2:comment_sentiment"},
        ).scalar_one()
    )
    if not acquired:
        logger.warning("comment_sentiment_skipped_lock_held")
        lock.close()
        engine.dispose()
        return 0
    try:
        coordinator = CommentSentimentCoordinator(
            repository=SocialCommentStore(engine, policy),
            provider=OpenRouterCommentSentimentProvider(settings.ai_summary),
            batch_size=args.batch_size,
        )
        result = asyncio.run(coordinator.run(limit=args.limit))
        print(
            json.dumps(
                {"classified": result.classified, "model": result.model},
                separators=(",", ":"),
            )
        )
        return 0
    finally:
        lock.execute(
            text("SELECT pg_advisory_unlock(hashtext(:name))"),
            {"name": "social_media_v2:comment_sentiment"},
        )
        lock.close()
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]
