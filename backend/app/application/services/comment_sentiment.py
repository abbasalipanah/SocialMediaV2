"""Batch orchestration for persisted comment sentiment."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.ports import CommentSentimentProvider, CommentSentimentRepository


@dataclass(frozen=True)
class CommentSentimentRun:
    classified: int
    model: str | None


class CommentSentimentCoordinator:
    def __init__(
        self,
        *,
        repository: CommentSentimentRepository,
        provider: CommentSentimentProvider,
        batch_size: int = 50,
    ) -> None:
        if batch_size < 1 or batch_size > 100:
            raise ValueError("comment_sentiment_batch_size_invalid")
        self._repository = repository
        self._provider = provider
        self._batch_size = batch_size

    async def run(self, *, limit: int) -> CommentSentimentRun:
        if limit < 1 or limit > 10_000:
            raise ValueError("comment_sentiment_limit_invalid")
        pending = self._repository.list_pending(limit=limit)
        classified = 0
        model: str | None = None
        for offset in range(0, len(pending), self._batch_size):
            requested = pending[offset : offset + self._batch_size]
            batch = await self._provider.classify(requested)
            if {item.comment_row_id for item in batch.items} != {
                item.comment_row_id for item in requested
            }:
                raise ValueError("comment_sentiment_response_incomplete")
            self._repository.save(batch)
            classified += len(batch.items)
            model = batch.model
        return CommentSentimentRun(classified=classified, model=model)


__all__ = ["CommentSentimentCoordinator", "CommentSentimentRun"]
