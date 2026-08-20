-- Persist AI-derived comment sentiment so dashboard reads never call a provider.

ALTER TABLE content_comments
    ADD COLUMN IF NOT EXISTS sentiment varchar(16),
    ADD COLUMN IF NOT EXISTS sentiment_model varchar(128),
    ADD COLUMN IF NOT EXISTS sentiment_classified_at timestamptz;

CREATE INDEX IF NOT EXISTS ix_content_comments_sentiment_pending
ON content_comments (commented_at DESC NULLS LAST, id DESC)
WHERE sentiment IS NULL AND length(btrim(text)) > 0;

CREATE INDEX IF NOT EXISTS ix_content_comments_asset_sentiment_date
ON content_comments (asset_id, sentiment, commented_at DESC);
