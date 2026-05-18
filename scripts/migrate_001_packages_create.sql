-- =============================================================================
-- FASE 1.1 — Create package-related tables
-- Run: docker exec -i twj_db psql -U openpg -d tokowebjaya < scripts/migrate_001_packages_create.sql
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. product_packages
--    Satu produk bisa punya banyak paket (Standard, Premium, Enterprise, dll).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS product_packages (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id              UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,

    code                    VARCHAR(50)  NOT NULL,          -- "standard", "premium", "enterprise"
    name_id                 VARCHAR(255) NOT NULL,
    name_en                 VARCHAR(255) NOT NULL,
    tagline_id              VARCHAR(500),
    tagline_en              VARCHAR(500),
    description_id          TEXT,
    description_en          TEXT,

    is_default              BOOLEAN NOT NULL DEFAULT FALSE,  -- paket yang di-highlight saat produk dibuka
    is_popular              BOOLEAN NOT NULL DEFAULT FALSE,  -- badge "Most Popular"
    sort_order              INTEGER NOT NULL DEFAULT 0,

    -- License / delivery config (dipindah dari products)
    license_type            VARCHAR(20)  NOT NULL DEFAULT 'none', -- token|password|credential|download|none
    max_activations         INTEGER      NOT NULL DEFAULT 1,
    license_duration_days   INTEGER,                              -- NULL = ikut billing cycle
    access_url              VARCHAR(500),
    guidebook_url           VARCHAR(500),
    guidebook_text_id       TEXT,
    guidebook_text_en       TEXT,
    webhook_url             VARCHAR(500),
    download_file           VARCHAR(500),

    status                  VARCHAR(20)  NOT NULL DEFAULT 'draft', -- active|draft|archived

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_package_code UNIQUE (product_id, code)
);

CREATE INDEX IF NOT EXISTS idx_product_packages_product_id ON product_packages(product_id);
CREATE INDEX IF NOT EXISTS idx_product_packages_status     ON product_packages(status);

-- ---------------------------------------------------------------------------
-- 2. package_prices
--    Satu paket bisa punya banyak opsi billing (one_time, monthly, yearly, contact).
--    Menggantikan kolom price_otf / price_monthly / price_yearly yang flat di products.
-- ---------------------------------------------------------------------------
CREATE TYPE billing_type_enum AS ENUM ('one_time', 'monthly', 'yearly', 'contact');

CREATE TABLE IF NOT EXISTS package_prices (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    package_id      UUID NOT NULL REFERENCES product_packages(id) ON DELETE CASCADE,

    billing_type    billing_type_enum NOT NULL,
    amount          NUMERIC(15, 2),         -- NULL hanya untuk billing_type='contact'
    currency        CHAR(3) NOT NULL DEFAULT 'IDR',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_package_price_billing UNIQUE (package_id, billing_type)
);

CREATE INDEX IF NOT EXISTS idx_package_prices_package_id ON package_prices(package_id);
CREATE INDEX IF NOT EXISTS idx_package_prices_active     ON package_prices(package_id, is_active);

-- ---------------------------------------------------------------------------
-- 3. package_features
--    Bullet point ✓/✗ untuk tabel perbandingan di halaman pricing.
--    Label bisa berisi teks fitur ("Unlimited Projects", "Priority Support").
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS package_features (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    package_id  UUID NOT NULL REFERENCES product_packages(id) ON DELETE CASCADE,

    label_id    VARCHAR(500) NOT NULL,
    label_en    VARCHAR(500) NOT NULL,
    included    BOOLEAN NOT NULL DEFAULT TRUE,   -- TRUE = ✓, FALSE = ✗ (fitur tapi tidak dapat)
    sort_order  INTEGER NOT NULL DEFAULT 0,

    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_package_features_package_id ON package_features(package_id);

-- ---------------------------------------------------------------------------
-- 4. product_limit_schemas
--    Mendefinisikan DIMENSI kuota apa saja yang relevan untuk sebuah produk.
--    Disimpan sekali per produk, bukan per paket.
--    Contoh: produk "Helpdesk AI" punya dimensi max_agents, storage_gb, api_calls_monthly.
-- ---------------------------------------------------------------------------
CREATE TYPE limit_value_type_enum AS ENUM ('int', 'bool', 'enum');

CREATE TABLE IF NOT EXISTS product_limit_schemas (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id              UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,

    key                     VARCHAR(100) NOT NULL,   -- "max_agents", "storage_gb", "api_calls_monthly"
    label_id                VARCHAR(255) NOT NULL,   -- "Jumlah Agent"
    label_en                VARCHAR(255) NOT NULL,   -- "Number of Agents"
    unit                    VARCHAR(50),             -- "agent", "GB", "calls/month" — null jika boolean
    value_type              limit_value_type_enum NOT NULL DEFAULT 'int',
    enum_options            JSONB,                   -- ["basic","advanced","priority"] hanya untuk value_type='enum'
    is_unlimited_allowed    BOOLEAN NOT NULL DEFAULT TRUE,  -- boleh di-set unlimited di PackageLimit
    sort_order              INTEGER NOT NULL DEFAULT 0,
    is_visible_on_pricing_page BOOLEAN NOT NULL DEFAULT TRUE,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_limit_schema_key UNIQUE (product_id, key)
);

CREATE INDEX IF NOT EXISTS idx_limit_schemas_product_id ON product_limit_schemas(product_id);

-- ---------------------------------------------------------------------------
-- 5. package_limits
--    Nilai kuota per paket untuk setiap dimensi yang sudah didefinisikan di schema.
--    Contoh: Premium -> max_agents = 15, Standard -> max_agents = 3.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS package_limits (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    package_id  UUID NOT NULL REFERENCES product_packages(id) ON DELETE CASCADE,
    schema_id   UUID NOT NULL REFERENCES product_limit_schemas(id) ON DELETE CASCADE,

    -- Isi salah satu sesuai value_type di schema
    value_int   INTEGER,
    value_bool  BOOLEAN,
    value_text  VARCHAR(255),   -- untuk value_type='enum', isi salah satu dari enum_options

    is_unlimited BOOLEAN NOT NULL DEFAULT FALSE,  -- override semua value_* → tak terbatas

    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_package_limit UNIQUE (package_id, schema_id)
);

CREATE INDEX IF NOT EXISTS idx_package_limits_package_id ON package_limits(package_id);
CREATE INDEX IF NOT EXISTS idx_package_limits_schema_id  ON package_limits(schema_id);

COMMIT;
