-- Migration: add product_packages table and orders.product_package_id
-- Run: docker exec -i twj_db psql -U openpg -d tokowebjaya < scripts/migrate_product_packages.sql

CREATE TABLE IF NOT EXISTS product_packages (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id           UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    name_id              VARCHAR(255) NOT NULL,
    name_en              VARCHAR(255) NOT NULL,
    description_id       TEXT,
    description_en       TEXT,
    price_otf            NUMERIC(15, 2),
    price_monthly        NUMERIC(15, 2),
    price_yearly         NUMERIC(15, 2),
    license_type         VARCHAR(20),
    max_activations      INTEGER,
    max_agent            INTEGER,
    license_duration_days INTEGER,
    features             JSONB NOT NULL DEFAULT '[]',
    sort_order           INTEGER NOT NULL DEFAULT 0,
    is_active            BOOLEAN NOT NULL DEFAULT TRUE,
    created_at           TIMESTAMP NOT NULL DEFAULT now(),
    updated_at           TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_product_packages_product_id ON product_packages(product_id);

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS product_package_id UUID
        REFERENCES product_packages(id) ON DELETE SET NULL;
