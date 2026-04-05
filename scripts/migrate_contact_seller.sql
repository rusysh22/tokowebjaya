-- Migration: Add contact_seller pricing model and contact fields to products
-- Run: docker exec -i twj_db psql -U openpg -d tokowebjaya < scripts/migrate_contact_seller.sql

-- 1. Add contact columns
ALTER TABLE products
  ADD COLUMN IF NOT EXISTS contact_whatsapp VARCHAR(30),
  ADD COLUMN IF NOT EXISTS contact_email    VARCHAR(255),
  ADD COLUMN IF NOT EXISTS contact_address  TEXT;

-- 2. Extend the pricingmodel enum with new value
ALTER TYPE pricingmodel ADD VALUE IF NOT EXISTS 'contact_seller';
