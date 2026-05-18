-- =============================================================================
-- FASE 2 — Backfill: convert existing products → packages structure
-- Aman dijalankan berkali-kali (idempotent via INSERT ... ON CONFLICT DO NOTHING).
-- Run AFTER migrate_001 dan migrate_002.
-- Run: docker exec -i twj_db psql -U openpg -d tokowebjaya < scripts/migrate_003_packages_backfill.sql
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- STEP 1: Tiap Product yang belum punya package → buat 1 package "default"
--         Copy name, description, dan seluruh license config dari product.
-- ---------------------------------------------------------------------------
INSERT INTO product_packages (
    id,
    product_id,
    code,
    name_id,
    name_en,
    description_id,
    description_en,
    is_default,
    is_popular,
    sort_order,
    license_type,
    max_activations,
    license_duration_days,
    access_url,
    guidebook_url,
    guidebook_text_id,
    guidebook_text_en,
    webhook_url,
    download_file,
    status,
    created_at,
    updated_at
)
SELECT
    gen_random_uuid(),
    p.id,
    'default',
    p.name_id,
    p.name_en,
    p.description_id,
    p.description_en,
    TRUE,   -- is_default
    FALSE,  -- is_popular
    0,      -- sort_order
    COALESCE(p.license_type, 'none'),
    COALESCE(p.max_activations, 1),
    p.license_duration_days,
    p.access_url,
    p.guidebook_url,
    p.guidebook_text_id,
    p.guidebook_text_en,
    p.webhook_url,
    p.download_file,
    CASE p.status
        WHEN 'active'   THEN 'active'
        WHEN 'draft'    THEN 'draft'
        WHEN 'archived' THEN 'archived'
        ELSE 'draft'
    END,
    p.created_at,
    p.updated_at
FROM products p
WHERE NOT EXISTS (
    SELECT 1 FROM product_packages pp WHERE pp.product_id = p.id
);

-- ---------------------------------------------------------------------------
-- STEP 2: Buat PackagePrice dari kolom flat price_* di products.
--         Satu package bisa dapat 1–3 rows (one_time, monthly, yearly).
-- ---------------------------------------------------------------------------

-- 2a. one_time — dari price_otf
INSERT INTO package_prices (id, package_id, billing_type, amount, currency, is_active)
SELECT
    gen_random_uuid(),
    pp.id,
    'one_time',
    p.price_otf,
    'IDR',
    TRUE
FROM products p
JOIN product_packages pp ON pp.product_id = p.id AND pp.code = 'default'
WHERE p.price_otf IS NOT NULL
  AND p.pricing_model IN ('one_time', 'both')
ON CONFLICT (package_id, billing_type) DO NOTHING;

-- 2b. monthly — dari price_monthly
INSERT INTO package_prices (id, package_id, billing_type, amount, currency, is_active)
SELECT
    gen_random_uuid(),
    pp.id,
    'monthly',
    p.price_monthly,
    'IDR',
    TRUE
FROM products p
JOIN product_packages pp ON pp.product_id = p.id AND pp.code = 'default'
WHERE p.price_monthly IS NOT NULL
  AND p.pricing_model IN ('subscription', 'both')
ON CONFLICT (package_id, billing_type) DO NOTHING;

-- 2c. yearly — dari price_yearly
INSERT INTO package_prices (id, package_id, billing_type, amount, currency, is_active)
SELECT
    gen_random_uuid(),
    pp.id,
    'yearly',
    p.price_yearly,
    'IDR',
    TRUE
FROM products p
JOIN product_packages pp ON pp.product_id = p.id AND pp.code = 'default'
WHERE p.price_yearly IS NOT NULL
  AND p.pricing_model IN ('subscription', 'both')
ON CONFLICT (package_id, billing_type) DO NOTHING;

-- 2d. contact_seller — dari pricing_model = 'contact_seller'
INSERT INTO package_prices (id, package_id, billing_type, amount, currency, is_active)
SELECT
    gen_random_uuid(),
    pp.id,
    'contact',
    NULL,   -- tidak ada amount untuk contact
    'IDR',
    TRUE
FROM products p
JOIN product_packages pp ON pp.product_id = p.id AND pp.code = 'default'
WHERE p.pricing_model = 'contact_seller'
ON CONFLICT (package_id, billing_type) DO NOTHING;

-- ---------------------------------------------------------------------------
-- STEP 3: Backfill JSON features → package_features rows
--         p.features adalah JSON array of strings: ["Feature A", "Feature B", ...]
--         Kita simpan label_id = label_en = text tersebut (bilingual bisa diupdate manual).
-- ---------------------------------------------------------------------------
INSERT INTO package_features (id, package_id, label_id, label_en, included, sort_order)
SELECT
    gen_random_uuid(),
    pp.id,
    feat.value,
    feat.value,
    TRUE,
    feat.ord
FROM products p
JOIN product_packages pp ON pp.product_id = p.id AND pp.code = 'default'
CROSS JOIN LATERAL jsonb_array_elements_text(
    CASE jsonb_typeof(p.features::jsonb)
        WHEN 'array' THEN p.features::jsonb
        ELSE '[]'::jsonb
    END
) WITH ORDINALITY AS feat(value, ord)
WHERE p.features IS NOT NULL
  AND p.features::text <> '[]'
  AND p.features::text <> 'null'
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- STEP 4: Backfill orders — set package_id dari default package product-nya.
--         package_price_id di-match berdasarkan order.type + amount.
-- ---------------------------------------------------------------------------
UPDATE orders o
SET package_id = pp.id
FROM product_packages pp
WHERE pp.product_id = o.product_id
  AND pp.code = 'default'
  AND o.package_id IS NULL;

-- Match package_price_id: order one_time → cari PackagePrice one_time dengan amount sama
UPDATE orders o
SET package_price_id = price.id
FROM package_prices price
WHERE price.package_id = o.package_id
  AND price.billing_type = 'one_time'
  AND o.type = 'one_time'
  AND o.package_price_id IS NULL;

-- Match package_price_id: order subscription → cari berdasarkan billing_cycle di subscription
UPDATE orders o
SET package_price_id = price.id
FROM package_prices price,
     subscriptions sub
WHERE price.package_id          = o.package_id
  AND sub.product_id            = o.product_id
  AND sub.user_id               = o.user_id
  AND price.billing_type::text  = sub.billing_cycle::text
  AND o.type = 'subscription'
  AND o.package_price_id IS NULL;

-- ---------------------------------------------------------------------------
-- STEP 5: Backfill subscriptions — set package_id dari default package.
-- ---------------------------------------------------------------------------
UPDATE subscriptions s
SET package_id = pp.id
FROM product_packages pp
WHERE pp.product_id = s.product_id
  AND pp.code = 'default'
  AND s.package_id IS NULL;

-- ---------------------------------------------------------------------------
-- STEP 6: Backfill product_licenses — set package_id.
-- ---------------------------------------------------------------------------
UPDATE product_licenses pl
SET package_id = pp.id
FROM product_packages pp
WHERE pp.product_id = pl.product_id
  AND pp.code = 'default'
  AND pl.package_id IS NULL;

-- ---------------------------------------------------------------------------
-- STEP 7: Verifikasi — tampilkan ringkasan hasil backfill.
-- ---------------------------------------------------------------------------
SELECT 'products'         AS tabel, COUNT(*) AS total FROM products
UNION ALL
SELECT 'packages created', COUNT(*) FROM product_packages
UNION ALL
SELECT 'prices created',   COUNT(*) FROM package_prices
UNION ALL
SELECT 'features created', COUNT(*) FROM package_features
UNION ALL
SELECT 'orders backfilled (package_id set)',       COUNT(*) FROM orders       WHERE package_id IS NOT NULL
UNION ALL
SELECT 'orders backfilled (package_price_id set)', COUNT(*) FROM orders       WHERE package_price_id IS NOT NULL
UNION ALL
SELECT 'subscriptions backfilled',                 COUNT(*) FROM subscriptions WHERE package_id IS NOT NULL
UNION ALL
SELECT 'licenses backfilled',                      COUNT(*) FROM product_licenses WHERE package_id IS NOT NULL;

COMMIT;
