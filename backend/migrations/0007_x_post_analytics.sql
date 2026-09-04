ALTER TABLE content_items
    ADD COLUMN reposts_count integer,
    ADD COLUMN quotes_count integer,
    ADD COLUMN link_clicks integer,
    ADD COLUMN profile_clicks integer,
    ADD COLUMN video_views_count integer,
    ADD COLUMN video_playback_0_count integer,
    ADD COLUMN video_playback_25_count integer,
    ADD COLUMN video_playback_50_count integer,
    ADD COLUMN video_playback_75_count integer,
    ADD COLUMN video_playback_100_count integer;

UPDATE content_items AS content
SET profile_clicks = content.profile_visits
FROM assets AS asset
WHERE asset.id = content.asset_id
  AND asset.platform = 'x'
  AND content.profile_visits IS NOT NULL;
