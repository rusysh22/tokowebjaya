-- =============================================================================
-- FASE 4 — Cleanup: drop deprecated columns from products, enforce NOT NULL
-- ⚠️  Run ONLY after:
--   1. migrate_001, 002, 003 sudah dijalankan
--   2. Fase 3 (service + route baru) sudah di-deploy dan berjalan ≥ 1 minggu
--   3. Semua kolom nullable di orders/subscriptions/product_licenses sudah terisi
--      (verifikasi dulu dengan query di bawah ini sebelum jalankan script ini)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Pre-flight checks — jalankan dulu untuk memastikan aman:
-- ---------------------------------------------------------------------------
-- SELECT COUNT(*) FROM orders       WHERE package_id IS NULL;        -- harus 0
-- SELECT COUNT(*) FROM subscriptions WHERE package_id IS NULL;       -- harus 0
-- SELECT COUNT(*) FROM product_licenses WHERE package_id IS NULL;    -- harus 0
-- SELECT COUNT(*) FROM orders       WHERE package_price_id IS NULL AND type = 'one_time'; -- harus 0
-- ---------------------------------------------------------------------------

BEGIN;

-- Enforce NOT NULL on FK columns setelah backfill lengkap
ALTER TABLE orders          ALTER COLUMN package_id       SET NOT NULL;
ALTER TABLE subscriptions   ALTER COLUMN package_id       SET NOT NULL;
ALTER TABLE product_licenses ALTER COLUMN package_id      SET NOT NULL;
-- package_price_id di orders dibiarkan nullable (subscription renewal tidak selalu punya price row)

-- Drop kolom flat-price yang sudah digantikan package_prices
ALTER TABLE products
    DROP COLUMN IF EXISTS price_otf,
    DROP COLUMN IF EXISTS price_monthly,
    DROP COLUMN IF EXISTS price_yearly,
    DROP COLUMN IF EXISTS pricing_model;

-- Drop license/delivery config yang sudah dipindah ke product_packages
ALTER TABLE products
    DROP COLUMN IF EXISTS license_type,
    DROP COLUMN IF EXISTS access_url,
    DROP COLUMN IF EXISTS guidebook_url,
    DROP COLUMN IF EXISTS guidebook_text_id,
    DROP COLUMN IF EXISTS guidebook_text_en,
    DROP COLUMN IF EXISTS max_activations,
    DROP COLUMN IF EXISTS license_duration_days,
    DROP COLUMN IF EXISTS webhook_url,
    DROP COLUMN IF EXISTS download_file;

-- features JSON di products digantikan package_features rows
ALTER TABLE products DROP COLUMN IF EXISTS features;

COMMIT;
