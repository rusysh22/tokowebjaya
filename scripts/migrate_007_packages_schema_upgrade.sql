-- =============================================================================
-- FASE 0 — Upgrade product_packages schema: add columns missing from old table
-- Run BEFORE migrate_001 through migrate_003.
-- =============================================================================

BEGIN;

ALTER TABLE product_packages
    ADD COLUMN IF NOT EXISTS code          VARCHAR(50),
    ADD COLUMN IF NOT EXISTS tagline_id    VARCHAR(500),
    ADD COLUMN IF NOT EXISTS tagline_en    VARCHAR(500),
    ADD COLUMN IF NOT EXISTS is_default    BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS is_popular    BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS access_url    VARCHAR(500),
    ADD COLUMN IF NOT EXISTS guidebook_url VARCHAR(500),
    ADD COLUMN IF NOT EXISTS guidebook_text_id TEXT,
    ADD COLUMN IF NOT EXISTS guidebook_text_en TEXT,
    ADD COLUMN IF NOT EXISTS webhook_url   VARCHAR(500),
    ADD COLUMN IF NOT EXISTS download_file VARCHAR(500),
    ADD COLUMN IF NOT EXISTS status        VARCHAR(20) NOT NULL DEFAULT 'draft';

-- Set code dari name_id untuk 2 existing rows
UPDATE product_packages
SET code = lower(replace(name_id, ' ', '_'))
WHERE code IS NULL;

-- Mark existing packages as active dan default
UPDATE product_packages SET status = 'active', is_default = TRUE WHERE code IS NOT NULL;

-- Sekarang enforce NOT NULL dan unique constraint
ALTER TABLE product_packages ALTER COLUMN code SET NOT NULL;

ALTER TABLE product_packages
    DROP CONSTRAINT IF EXISTS uq_package_code;
ALTER TABLE product_packages
    ADD CONSTRAINT uq_package_code UNIQUE (product_id, code);

SELECT 'product_packages upgraded' AS result, COUNT(*) AS rows FROM product_packages;

COMMIT;
