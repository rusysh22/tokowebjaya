-- =============================================================================
-- FASE 1.2 — Alter existing tables: add package foreign keys (nullable)
-- Kolom dibuat nullable dulu; di-populate oleh backfill (migrate_003),
-- lalu di-set NOT NULL di cleanup migration (migrate_004).
-- Run: docker exec -i twj_db psql -U openpg -d tokowebjaya < scripts/migrate_002_packages_fk.sql
-- =============================================================================

BEGIN;

-- orders: catat paket & price mana yang dibeli
ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS package_id       UUID REFERENCES product_packages(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS package_price_id UUID REFERENCES package_prices(id)   ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_orders_package_id       ON orders(package_id);
CREATE INDEX IF NOT EXISTS idx_orders_package_price_id ON orders(package_price_id);

-- subscriptions: catat paket yang aktif di-subscribe
ALTER TABLE subscriptions
    ADD COLUMN IF NOT EXISTS package_id UUID REFERENCES product_packages(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_subscriptions_package_id ON subscriptions(package_id);

-- product_licenses: untuk bisa baca config limit dari paket yang bersangkutan
ALTER TABLE product_licenses
    ADD COLUMN IF NOT EXISTS package_id UUID REFERENCES product_packages(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_product_licenses_package_id ON product_licenses(package_id);

COMMIT;
