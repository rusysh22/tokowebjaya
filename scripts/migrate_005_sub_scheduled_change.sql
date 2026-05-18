-- Migration 005: Subscription scheduled package change
-- Allows upgrade/downgrade effective at next billing cycle.
-- Run: docker exec -i twj_db psql -U openpg -d tokowebjaya < scripts/migrate_005_sub_scheduled_change.sql

BEGIN;

-- Add scheduled_package_id so upgrades/downgrades take effect at next renewal
ALTER TABLE subscriptions
  ADD COLUMN IF NOT EXISTS scheduled_package_id UUID
    REFERENCES product_packages(id) ON DELETE SET NULL;

-- Index for quick lookup during renewal processing
CREATE INDEX IF NOT EXISTS idx_subscriptions_scheduled_package
  ON subscriptions(scheduled_package_id)
  WHERE scheduled_package_id IS NOT NULL;

-- Verify
SELECT
  COUNT(*)                                              AS total_subscriptions,
  COUNT(scheduled_package_id)                           AS with_scheduled_change,
  column_name,
  data_type
FROM subscriptions
CROSS JOIN information_schema.columns
WHERE table_name = 'subscriptions'
  AND column_name = 'scheduled_package_id'
GROUP BY column_name, data_type;

COMMIT;
