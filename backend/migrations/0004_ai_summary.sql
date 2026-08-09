-- Structured, V2-owned AI Summary history. Raw provider inputs are never persisted.

ALTER TABLE brand_ai_insights
    ADD COLUMN IF NOT EXISTS connector_analysis text,
    ADD COLUMN IF NOT EXISTS anomalies text,
    ADD COLUMN IF NOT EXISTS platform_evaluations text,
    ADD COLUMN IF NOT EXISTS llm_model varchar(128),
    ADD COLUMN IF NOT EXISTS error_message text,
    ADD COLUMN IF NOT EXISTS created_by_user_sub varchar(128);

CREATE INDEX IF NOT EXISTS ix_brand_ai_insights_brand_completed
ON brand_ai_insights (brand_id, completed_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS ix_brand_ai_insights_brand_status_created
ON brand_ai_insights (brand_id, status, created_at DESC, id DESC);
