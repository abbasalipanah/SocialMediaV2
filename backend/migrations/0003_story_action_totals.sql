-- Provider-backed action fields used by selected-story and selected-period views.
-- Unsupported provider values remain NULL; a reported zero remains a real zero.

ALTER TABLE content_items ADD COLUMN IF NOT EXISTS saves_count double precision;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS sticker_taps double precision;
