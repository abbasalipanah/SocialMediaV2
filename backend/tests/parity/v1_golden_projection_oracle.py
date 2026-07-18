"""Frozen V1 golden persistence oracle for the characterized Facebook slice."""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

V1_BACKEND = Path(os.environ["V1_BACKEND_ROOT"])
sys.path.insert(0, str(V1_BACKEND))

from app.connectors.facebook.legacy import metrics_store  # noqa: E402


def _media_bytes(source_url: str) -> bytes:
    return f"golden-media:{source_url}".encode()


def main() -> int:
    fixture = json.loads(Path(os.environ["GOLDEN_FIXTURE"]).read_text(encoding="utf-8"))
    routes = {(route["path"], route["after"]): route for route in fixture["routes"]}
    profile = routes[("/v23.0/page-1", None)]["responses"][0]["json"]
    first = routes[("/v23.0/page-1/published_posts", None)]["responses"][0]["json"]
    second = routes[("/v23.0/page-1/published_posts", "fb-next")]["responses"][0]["json"]
    fb_rows = [*first["data"], *second["data"]]
    fb_comment_rows = routes[("/v23.0/post-1/comments", None)]["responses"][0]["json"][
        "data"
    ]
    ig_profile = routes[("/v23.0/ig-1", None)]["responses"][0]["json"]
    ig_rows = routes[("/v23.0/ig-1/media", None)]["responses"][0]["json"]["data"]
    story_rows = routes[("/v23.0/ig-1/stories", None)]["responses"][0]["json"]["data"]
    comment_rows = routes[("/v23.0/ig-post-1/comments", None)]["responses"][0]["json"][
        "data"
    ]
    engine = create_engine(os.environ["PARITY_DATABASE_URL"])
    with Session(engine) as session:
        metrics_store.upsert_daily_account_metrics(
            session,
            asset_id=11,
            date=datetime.date(2026, 7, 14),
            values={"followers": profile["followers_count"]},
        )
        metrics_store.upsert_daily_account_metrics(
            session,
            asset_id=12,
            date=datetime.date(2026, 7, 14),
            values={"followers": ig_profile["followers_count"]},
        )
        for row in fb_rows:
            metrics_store.upsert_content_item(
                session,
                asset_id=11,
                content_id=row["id"],
                values={
                    "content_type": row["status_type"],
                    "permalink": row.get("permalink_url") or "",
                    "message": row.get("message") or "",
                    "media_url": row.get("full_picture") or "",
                    "created_time": row["created_time"],
                    "likes_count": row["reactions"]["summary"]["total_count"],
                    "comments_count": row["comments"]["summary"]["total_count"],
                    "shares_count": row["shares"]["count"],
                },
            )
        for row in ig_rows:
            metrics_store.upsert_content_item(
                session,
                asset_id=12,
                content_id=row["id"],
                values=_ig_content_values(row, story=False),
            )
        for row in story_rows:
            metrics_store.upsert_content_item(
                session,
                asset_id=12,
                content_id=row["id"],
                values=_ig_content_values(row, story=True),
            )
    with engine.begin() as connection:
        for row in fb_comment_rows:
            connection.execute(
                text(
                    """INSERT INTO content_comments (
                           asset_id, content_id, platform, comment_id, user_id,
                           user_name, text, like_count, reply_count, answered,
                           attachment_type, attachment_media_type, attachment_url,
                           commented_at, created_at, updated_at
                       ) VALUES (
                           11, 'post-1', 'facebook', :comment_id, :user_id,
                           :user_name, :text_value, :like_count, :reply_count, false,
                           :attachment_type, NULL, :attachment_url,
                           :commented_at, now(), now()
                       )"""
                ),
                {
                    "comment_id": row["id"],
                    "user_id": row["from"]["id"],
                    "user_name": row["from"]["name"],
                    "text_value": row["message"],
                    "like_count": row["like_count"],
                    "reply_count": row["comment_count"],
                    "attachment_type": row["attachment"]["type"],
                    "attachment_url": row["attachment"]["media"]["image"]["src"],
                    "commented_at": row["created_time"],
                },
            )
        for row in comment_rows:
            connection.execute(
                text(
                    """INSERT INTO content_comments (
                           asset_id, content_id, platform, comment_id, user_id,
                           user_name, text, like_count, reply_count, answered,
                           attachment_type, attachment_media_type, attachment_url,
                           commented_at, created_at, updated_at
                       ) VALUES (
                           12, 'ig-post-1', 'instagram', :comment_id, :user_id,
                           :user_name, :text_value, :like_count, :reply_count, false,
                           NULL, NULL, NULL, :commented_at, now(), now()
                       )"""
                ),
                {
                    "comment_id": row["id"],
                    "user_id": row["from"]["id"],
                    "user_name": row["username"],
                    "text_value": row["text"],
                    "like_count": row["like_count"],
                    "reply_count": len(row["replies"]["data"]),
                    "commented_at": row["timestamp"],
                },
            )
    media_rows = [
        (11, "facebook", row["id"], row.get("full_picture"))
        for row in fb_rows
        if row.get("full_picture")
    ]
    media_rows.extend(
        (
            12,
            "instagram",
            row["id"],
            row.get("media_url") or row.get("thumbnail_url"),
        )
        for row in [*ig_rows, *story_rows]
        if row.get("media_url") or row.get("thumbnail_url")
    )
    media_root = Path(os.environ["PARITY_MEDIA_ROOT"])
    with engine.begin() as connection:
        for account_id, platform, content_id, source_url in media_rows:
            data = _media_bytes(source_url)
            storage_path = f"{platform}/{account_id}/{content_id}.jpg"
            destination = media_root / storage_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            connection.execute(
                text(
                    """INSERT INTO media_assets (
                           brand_id, asset_id, content_id, platform, media_kind,
                           storage_path, source_url, source_status, mime_type,
                           size_bytes, checksum, last_verified_at, created_at, updated_at
                       ) VALUES (
                           7, :account_id, :content_id, :platform, 'cover', :storage_path,
                           :source_url, 200, 'image/jpeg', :size_bytes, :checksum,
                           '2026-07-14T13:00:00+00:00', now(), now()
                       )"""
                ),
                {
                    "account_id": account_id,
                    "content_id": content_id,
                    "platform": platform,
                    "storage_path": storage_path,
                    "source_url": source_url,
                    "size_bytes": len(data),
                    "checksum": hashlib.sha256(data).hexdigest(),
                },
            )
    engine.dispose()
    print(
        json.dumps(
            {
                "status": "success",
                "metric_count": 2,
                "content_count": len(fb_rows) + len(ig_rows) + len(story_rows),
                "comment_count": len(fb_comment_rows) + len(comment_rows),
                "media_count": len(media_rows),
            },
            sort_keys=True,
        )
    )
    return 0


def _ig_content_values(row: dict[str, object], *, story: bool) -> dict[str, object]:
    media_url = row.get("media_url") or row.get("thumbnail_url") or ""
    return {
        "content_type": "story" if story else str(row.get("media_type") or "post").lower(),
        "permalink": row.get("permalink") or "",
        "message": row.get("caption") or "",
        "media_url": media_url,
        "created_time": row["timestamp"],
        "likes_count": row.get("like_count") or 0,
        "comments_count": row.get("comments_count") or 0,
        "shares_count": 0,
    }


if __name__ == "__main__":
    raise SystemExit(main())
