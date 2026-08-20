"""Contracts for privacy-minimized comment sentiment classification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

CommentSentiment = Literal["positive", "neutral", "negative"]


@dataclass(frozen=True)
class PendingCommentSentiment:
    comment_row_id: int
    text: str


@dataclass(frozen=True)
class ClassifiedCommentSentiment:
    comment_row_id: int
    sentiment: CommentSentiment


@dataclass(frozen=True)
class CommentSentimentBatch:
    items: tuple[ClassifiedCommentSentiment, ...]
    model: str


class CommentSentimentProvider(Protocol):
    async def classify(
        self, comments: tuple[PendingCommentSentiment, ...]
    ) -> CommentSentimentBatch: ...


class CommentSentimentRepository(Protocol):
    def list_pending(self, *, limit: int) -> tuple[PendingCommentSentiment, ...]: ...

    def save(self, batch: CommentSentimentBatch) -> None: ...


__all__ = [
    "ClassifiedCommentSentiment",
    "CommentSentiment",
    "CommentSentimentBatch",
    "CommentSentimentProvider",
    "CommentSentimentRepository",
    "PendingCommentSentiment",
]
