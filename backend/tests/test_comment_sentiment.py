from __future__ import annotations

import pytest

from app.application.ports import (
    ClassifiedCommentSentiment,
    CommentSentimentBatch,
    PendingCommentSentiment,
)
from app.application.services import CommentSentimentCoordinator


class FakeRepository:
    def __init__(self) -> None:
        self.pending = tuple(
            PendingCommentSentiment(comment_row_id=index, text=f"comment {index}")
            for index in range(1, 6)
        )
        self.saved: list[CommentSentimentBatch] = []

    def list_pending(self, *, limit: int):
        return self.pending[:limit]

    def save(self, batch: CommentSentimentBatch) -> None:
        self.saved.append(batch)


class FakeProvider:
    async def classify(self, comments):
        return CommentSentimentBatch(
            items=tuple(
                ClassifiedCommentSentiment(item.comment_row_id, "neutral") for item in comments
            ),
            model="google/gemini-2.5-flash-lite",
        )


@pytest.mark.asyncio
async def test_comment_sentiment_batches_and_persists_every_requested_comment() -> None:
    repository = FakeRepository()
    coordinator = CommentSentimentCoordinator(
        repository=repository,
        provider=FakeProvider(),
        batch_size=2,
    )

    result = await coordinator.run(limit=5)

    assert result.classified == 5
    assert result.model == "google/gemini-2.5-flash-lite"
    assert [len(batch.items) for batch in repository.saved] == [2, 2, 1]
