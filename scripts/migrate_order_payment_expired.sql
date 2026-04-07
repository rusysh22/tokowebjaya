-- Add payment_expired_at column to orders table
ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_expired_at TIMESTAMP;
