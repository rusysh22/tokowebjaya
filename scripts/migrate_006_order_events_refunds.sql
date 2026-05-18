-- Phase 1: Audit log, refund system, and notification deep-links
-- Run: docker exec -i twj_db psql -U openpg -d tokowebjaya < scripts/migrate_006_order_events_refunds.sql

BEGIN;

-- ─── 1. Extend order_status enum ────────────────────────────────────────────
DO $$ BEGIN
    ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'partially_refunded';
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ─── 2. order_events (append-only audit log) ─────────────────────────────────
CREATE TABLE IF NOT EXISTS order_events (
    id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id   UUID        NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    actor_type VARCHAR(20) NOT NULL DEFAULT 'system',
    actor_id   UUID        REFERENCES users(id) ON DELETE SET NULL,
    metadata   JSONB,
    note       TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_order_events_order_id   ON order_events(order_id);
CREATE INDEX IF NOT EXISTS idx_order_events_created_at ON order_events(created_at DESC);

-- ─── 3. refund_status enum ───────────────────────────────────────────────────
DO $$ BEGIN
    CREATE TYPE refund_status AS ENUM ('pending', 'approved', 'rejected', 'processed', 'failed');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ─── 4. refunds table ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS refunds (
    id                UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id          UUID          NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
    user_id           UUID          NOT NULL REFERENCES users(id)  ON DELETE RESTRICT,
    reviewed_by       UUID          REFERENCES users(id) ON DELETE SET NULL,
    status            refund_status NOT NULL DEFAULT 'pending',
    amount            INTEGER       NOT NULL,
    reason            TEXT          NOT NULL,
    admin_note        TEXT,
    rejection_reason  TEXT,
    gateway_refund_id VARCHAR(255),
    requested_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    reviewed_at       TIMESTAMPTZ,
    processed_at      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_refunds_order_id ON refunds(order_id);
CREATE INDEX IF NOT EXISTS idx_refunds_user_id  ON refunds(user_id);
CREATE INDEX IF NOT EXISTS idx_refunds_status   ON refunds(status);

-- ─── 5. Notification FK columns ──────────────────────────────────────────────
ALTER TABLE notifications
    ADD COLUMN IF NOT EXISTS order_id        UUID REFERENCES orders(id)        ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS subscription_id UUID REFERENCES subscriptions(id)  ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS invoice_id      UUID REFERENCES invoices(id)       ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_notifications_order_id        ON notifications(order_id)        WHERE order_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_notifications_subscription_id ON notifications(subscription_id) WHERE subscription_id IS NOT NULL;

-- ─── 6. Extend notification_type enum ───────────────────────────────────────
DO $$ BEGIN
    ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'refund_requested';
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'refund_approved';
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'refund_rejected';
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'refund_processed';
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

COMMIT;
