ALTER TABLE content_items
    ALTER COLUMN likes_count DROP NOT NULL,
    ALTER COLUMN comments_count DROP NOT NULL,
    ALTER COLUMN shares_count DROP NOT NULL;
