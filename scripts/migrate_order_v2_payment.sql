-- Add Duitku V2 payment fields to orders table
ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_method_code VARCHAR(20);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_method_name VARCHAR(100);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS va_number VARCHAR(100);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS qr_string TEXT;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS payment_code VARCHAR(100);
