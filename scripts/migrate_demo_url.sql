-- Migration: Add demo_url column to products
-- Run: docker exec -i twj_db psql -U openpg -d tokowebjaya < scripts/migrate_demo_url.sql

ALTER TABLE products ADD COLUMN IF NOT EXISTS demo_url VARCHAR(500);
