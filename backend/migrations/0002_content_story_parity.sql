-- Nullable provider detail fields for Revision 6 / R4 content and Stories parity.
-- Missing provider values stay NULL; media candidate arrays never contain synthetic URLs.

ALTER TABLE content_items ADD COLUMN IF NOT EXISTS views_count double precision;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS reach_count double precision;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS cover_url varchar(2048);
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS thumbnail_url varchar(2048);
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS cover_candidates jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS thumbnail_candidates jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS media_url_candidates jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS full_video_watched_rate double precision;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS total_time_watched double precision;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS average_time_watched double precision;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS interactions_count double precision;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS replies_count double precision;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS profile_visits double precision;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS follows_count double precision;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS taps_forward double precision;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS taps_back double precision;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS swipe_forward double precision;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS exits double precision;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS navigation_count double precision;
ALTER TABLE content_items ADD COLUMN IF NOT EXISTS completion_rate double precision;
