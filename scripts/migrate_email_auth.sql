-- Migration: Add email+password auth fields to users table
-- Run: docker exec -i twj_db psql -U openpg -d tokowebjaya < scripts/migrate_email_auth.sql

BEGIN;

-- Add auth provider enum
DO $$ BEGIN
    CREATE TYPE authprovider AS ENUM ('google', 'email');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Add new columns
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255),
    ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS auth_provider authprovider NOT NULL DEFAULT 'google';

-- Existing users (Google OAuth) are already verified
UPDATE users SET email_verified = TRUE WHERE google_id IS NOT NULL;

COMMIT;

SELECT 'Migration migrate_email_auth OK' AS result;
