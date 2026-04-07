-- Migration: product_licenses table + delivery fields on products
-- Run: Get-Content scripts/migrate_product_licenses.sql | docker exec -i twj_db psql -U openpg -d tokowebjaya

-- ── License type enum ────────────────────────────────────────────────────────
DO $$ BEGIN
    CREATE TYPE license_type AS ENUM ('token', 'password', 'credential', 'download', 'none');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ── Delivery config fields on products ──────────────────────────────────────
ALTER TABLE products
    ADD COLUMN IF NOT EXISTS license_type        VARCHAR(20)  DEFAULT 'none',
    ADD COLUMN IF NOT EXISTS access_url          VARCHAR(500) NULL,
    ADD COLUMN IF NOT EXISTS guidebook_url       VARCHAR(500) NULL,
    ADD COLUMN IF NOT EXISTS guidebook_text_id   TEXT         NULL,
    ADD COLUMN IF NOT EXISTS guidebook_text_en   TEXT         NULL,
    ADD COLUMN IF NOT EXISTS max_activations     INTEGER      DEFAULT 1,
    ADD COLUMN IF NOT EXISTS license_duration_days INTEGER    NULL,  -- NULL = follow subscription cycle
    ADD COLUMN IF NOT EXISTS webhook_url         VARCHAR(500) NULL;  -- URL aplikasi eksternal untuk notif

-- ── product_licenses table ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS product_licenses (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id          UUID        NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    user_id           UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id        UUID        NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    subscription_id   UUID        NULL REFERENCES subscriptions(id) ON DELETE SET NULL,

    -- Delivery type
    license_type      VARCHAR(20) NOT NULL DEFAULT 'token',

    -- Credentials (stored encrypted)
    license_key       VARCHAR(255) NULL,   -- token: TWJ-XXXX-XXXX-XXXX-XXXX
    license_password  VARCHAR(255) NULL,   -- password untuk enkripsi file / credential
    license_username  VARCHAR(255) NULL,   -- username untuk credential type
    access_url        VARCHAR(500) NULL,   -- URL aplikasi / download

    -- Validity
    expires_at        TIMESTAMP   NULL,    -- NULL = lifetime
    grace_until       TIMESTAMP   NULL,    -- 3 hari setelah expires_at
    max_activations   INTEGER     DEFAULT 1,
    activated_count   INTEGER     DEFAULT 0,

    -- Download tracking
    download_count    INTEGER     DEFAULT 0,
    max_downloads     INTEGER     DEFAULT 5,
    last_downloaded_at TIMESTAMP  NULL,

    -- Status
    is_active         BOOLEAN     DEFAULT TRUE,
    revoked_at        TIMESTAMP   NULL,
    revoked_reason    TEXT        NULL,

    -- Reminder tracking
    reminded_7d       BOOLEAN     DEFAULT FALSE,
    reminded_3d       BOOLEAN     DEFAULT FALSE,
    reminded_expired  BOOLEAN     DEFAULT FALSE,

    -- Extra data (domain_lock, seats, version, last_validated_ip, etc.)
    license_metadata  JSONB       DEFAULT '{}',

    created_at        TIMESTAMP   DEFAULT NOW(),
    updated_at        TIMESTAMP   DEFAULT NOW()
);

-- ── Indexes ──────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_licenses_user        ON product_licenses(user_id);
CREATE INDEX IF NOT EXISTS idx_licenses_order       ON product_licenses(order_id);
CREATE INDEX IF NOT EXISTS idx_licenses_product     ON product_licenses(product_id);
CREATE INDEX IF NOT EXISTS idx_licenses_key         ON product_licenses(license_key);
CREATE INDEX IF NOT EXISTS idx_licenses_expires     ON product_licenses(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_licenses_active      ON product_licenses(is_active);

-- ── license_activations table (track per-device) ─────────────────────────────
CREATE TABLE IF NOT EXISTS license_activations (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    license_id      UUID        NOT NULL REFERENCES product_licenses(id) ON DELETE CASCADE,
    device_id       VARCHAR(255) NULL,
    ip_address      VARCHAR(45)  NULL,
    user_agent      TEXT         NULL,
    activated_at    TIMESTAMP    DEFAULT NOW(),
    last_seen_at    TIMESTAMP    DEFAULT NOW(),
    is_active       BOOLEAN      DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_activations_license ON license_activations(license_id);
