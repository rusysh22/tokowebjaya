-- Promo codes table
CREATE TABLE IF NOT EXISTS promo_codes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code            VARCHAR(50) UNIQUE NOT NULL,
    description     VARCHAR(255),
    discount_type   VARCHAR(20) NOT NULL DEFAULT 'percent',
    discount_value  NUMERIC(12,2) NOT NULL,
    min_amount      NUMERIC(12,2),
    max_discount    NUMERIC(12,2),
    max_uses        INTEGER,
    used_count      INTEGER NOT NULL DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    valid_from      TIMESTAMP,
    valid_until     TIMESTAMP,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_promo_codes_code      ON promo_codes(code);
CREATE INDEX IF NOT EXISTS idx_promo_codes_is_active ON promo_codes(is_active);

-- Add promo_code and final_amount columns to orders table
ALTER TABLE orders ADD COLUMN IF NOT EXISTS promo_code      VARCHAR(50);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS discount_amount NUMERIC(12,2) DEFAULT 0;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS final_amount    NUMERIC(12,2);

-- Backfill final_amount = amount for existing orders
UPDATE orders SET final_amount = amount WHERE final_amount IS NULL;
