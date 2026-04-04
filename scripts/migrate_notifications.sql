-- Migration: create notifications table
-- Run: docker exec -i twj_db psql -U openpg -d tokowebjaya < scripts/migrate_notifications.sql

CREATE TYPE notificationtype AS ENUM (
    'order_paid',
    'order_failed',
    'invoice_created',
    'subscription_new',
    'subscription_renewal',
    'subscription_expiring',
    'subscription_cancelled',
    'general'
);

CREATE TABLE IF NOT EXISTS notifications (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type       notificationtype NOT NULL DEFAULT 'general',
    title      VARCHAR(255) NOT NULL,
    body       TEXT,
    link       VARCHAR(500),
    is_read    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS ix_notifications_is_read ON notifications(user_id, is_read);
