from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text

from tests.phase5_fake_meta import FakeMetaServer

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
FIXTURE = Path(__file__).parent / "fixtures" / "phase5" / "meta_golden.json"
ORACLE_URL = os.getenv("TEST_PARITY_ORACLE_URL")
CANDIDATE_URL = os.getenv("TEST_PARITY_CANDIDATE_URL")
pytestmark = pytest.mark.skipif(
    not ORACLE_URL or not CANDIDATE_URL,
    reason="separate parity PostgreSQL databases are not configured",
)


def _prepare(engine: Engine) -> None:
    with engine.begin() as connection:
        for table_name in (
            "social_projection_state",
            "content_comments",
            "media_assets",
            "metrics_daily",
            "content_items",
            "assets",
            "brands",
        ):
            connection.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
        connection.execute(text("CREATE TABLE brands (id integer PRIMARY KEY)"))
        connection.execute(
            text(
                """CREATE TABLE assets (
                       id integer PRIMARY KEY,
                       brand_id integer NOT NULL REFERENCES brands(id),
                       platform varchar(64) NOT NULL
                   )"""
            )
        )
        connection.execute(
            text(
                """CREATE TABLE content_comments (
                       id serial PRIMARY KEY, asset_id integer NOT NULL REFERENCES assets(id),
                       content_id varchar(255) NOT NULL, platform varchar(32) NOT NULL,
                       comment_id varchar(255) NOT NULL, user_id varchar(255),
                       user_name varchar(255), text text NOT NULL, like_count integer NOT NULL,
                       reply_count integer NOT NULL, answered boolean NOT NULL,
                       attachment_type varchar(64), attachment_media_type varchar(64),
                       attachment_url varchar(1024), commented_at timestamptz,
                       sentiment varchar(16), sentiment_model varchar(128),
                       sentiment_classified_at timestamptz,
                       created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
                       UNIQUE (asset_id, comment_id)
                   )"""
            )
        )
        connection.execute(
            text(
                """CREATE TABLE metrics_daily (
                       id serial NOT NULL, asset_id integer NOT NULL REFERENCES assets(id),
                       brand_id integer NOT NULL REFERENCES brands(id), date date NOT NULL,
                       metric_id varchar(64) NOT NULL, value_numeric double precision NOT NULL,
                       breakdown_key varchar(64), breakdown_value varchar(128),
                       PRIMARY KEY (id, date)
                   )"""
            )
        )
        connection.execute(
            text(
                """CREATE UNIQUE INDEX uq_metrics_daily_account_rows
                   ON metrics_daily (asset_id, date, metric_id)
                   WHERE breakdown_key IS NULL AND breakdown_value IS NULL"""
            )
        )
        connection.execute(
            text(
                """CREATE TABLE content_items (
                       id serial PRIMARY KEY, asset_id integer NOT NULL REFERENCES assets(id),
                       brand_id integer NOT NULL REFERENCES brands(id),
                       content_id varchar(128) NOT NULL, content_type varchar(32) NOT NULL,
                       permalink varchar(512) NOT NULL, message varchar(4096) NOT NULL,
                       media_url varchar(2048) NOT NULL, created_time timestamptz,
                       likes_count integer NOT NULL, comments_count integer NOT NULL,
                       shares_count integer NOT NULL, views_count double precision,
                       reach_count double precision, cover_url varchar(2048),
                       thumbnail_url varchar(2048),
                       cover_candidates jsonb NOT NULL DEFAULT '[]'::jsonb,
                       thumbnail_candidates jsonb NOT NULL DEFAULT '[]'::jsonb,
                       media_url_candidates jsonb NOT NULL DEFAULT '[]'::jsonb,
                       full_video_watched_rate double precision,
                       total_time_watched double precision,
                       average_time_watched double precision,
                       interactions_count double precision, replies_count double precision,
                       saves_count double precision, sticker_taps double precision,
                       profile_visits double precision, follows_count double precision,
                       taps_forward double precision, taps_back double precision,
                       swipe_forward double precision, exits double precision,
                       navigation_count double precision, completion_rate double precision,
                       reposts_count integer, quotes_count integer, link_clicks integer,
                       profile_clicks integer, video_views_count integer,
                       video_playback_0_count integer, video_playback_25_count integer,
                       video_playback_50_count integer, video_playback_75_count integer,
                       video_playback_100_count integer,
                       created_at timestamptz NOT NULL,
                       updated_at timestamptz NOT NULL DEFAULT now(),
                       UNIQUE (asset_id, content_id)
                   )"""
            )
        )
        connection.execute(
            text(
                """CREATE TABLE media_assets (
                       id serial PRIMARY KEY, brand_id integer NOT NULL REFERENCES brands(id),
                       asset_id integer NOT NULL REFERENCES assets(id),
                       content_id varchar(128) NOT NULL, platform varchar(32) NOT NULL,
                       media_kind varchar(32) NOT NULL, storage_path varchar(1024) NOT NULL,
                       source_url varchar(2048) NOT NULL, source_status integer,
                       mime_type varchar(128) NOT NULL, size_bytes integer NOT NULL,
                       checksum varchar(64) NOT NULL, last_verified_at timestamptz,
                       created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
                       UNIQUE (asset_id, content_id, media_kind)
                   )"""
            )
        )
        connection.execute(
            text(
                """CREATE TABLE social_projection_state (
                       projection_key varchar(512) PRIMARY KEY,
                       payload_json jsonb NOT NULL,
                       updated_at timestamptz NOT NULL
                   )"""
            )
        )
        connection.execute(text("INSERT INTO brands (id) VALUES (7)"))
        connection.execute(
            text("INSERT INTO assets (id, brand_id, platform) VALUES (11, 7, 'facebook')")
        )
        connection.execute(
            text("INSERT INTO assets (id, brand_id, platform) VALUES (12, 7, 'instagram')")
        )


def _run(script: str, env: dict[str, str]) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "parity" / script)],
        cwd=ROOT,
        env={**os.environ, **env},
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def _database_snapshot(engine: Engine) -> dict[str, list[list[object]]]:
    statements = {
        "metrics": """SELECT asset_id, brand_id, date::text, metric_id, value_numeric
                       FROM metrics_daily ORDER BY asset_id, date, metric_id""",
        "content": """SELECT asset_id, brand_id, content_id, content_type, permalink,
                              message, media_url, created_time::text, likes_count,
                              comments_count, shares_count
                       FROM content_items ORDER BY asset_id, content_id""",
        "media": """SELECT brand_id, asset_id, content_id, platform, media_kind,
                            storage_path, source_url, source_status, mime_type,
                            size_bytes, checksum
                     FROM media_assets ORDER BY asset_id, content_id, media_kind""",
        "comments": """SELECT asset_id, content_id, platform, comment_id, user_id,
                               user_name, text, like_count, reply_count, answered,
                               attachment_type, attachment_media_type, attachment_url,
                               commented_at::text
                        FROM content_comments ORDER BY asset_id, comment_id""",
    }
    with engine.connect() as connection:
        return {
            name: [list(row) for row in connection.execute(text(statement)).all()]
            for name, statement in statements.items()
        }


def _file_snapshot(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_upstream_golden_and_v2_db_filesystem_differential(tmp_path: Path) -> None:
    assert ORACLE_URL and CANDIDATE_URL
    oracle_engine = create_engine(ORACLE_URL)
    candidate_engine = create_engine(CANDIDATE_URL)
    _prepare(oracle_engine)
    _prepare(candidate_engine)
    oracle_root = tmp_path / "oracle"
    candidate_root = tmp_path / "candidate"
    server = FakeMetaServer(FIXTURE)
    server.start()
    try:
        oracle = _run(
            "v1_golden_projection_oracle.py",
            {
                "PARITY_DATABASE_URL": ORACLE_URL,
                "PARITY_MEDIA_ROOT": str(oracle_root),
                "GOLDEN_FIXTURE": str(FIXTURE),
                "V1_BACKEND_ROOT": "/home/api/colab_scripts/Accumulate/backend",
            },
        )
        candidate = _run(
            "v2_collection_candidate.py",
            {
                "PARITY_DATABASE_URL": CANDIDATE_URL,
                "PARITY_MEDIA_ROOT": str(candidate_root),
                "FAKE_META_ORIGIN": server.origin,
                "FIXTURE_PROVIDER_TOKEN": "fixture-token-not-secret",
            },
        )
    finally:
        server.close()
    assert candidate == oracle
    assert _database_snapshot(candidate_engine) == _database_snapshot(oracle_engine)
    assert _file_snapshot(candidate_root) == _file_snapshot(oracle_root)
    oracle_engine.dispose()
    candidate_engine.dispose()
