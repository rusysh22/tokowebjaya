-- Migration: Appointment & ProductAvailability tables
-- Run: docker exec -i twj_db psql -U openpg -d tokowebjaya < scripts/migrate_appointments.sql

-- Enums
DO $$ BEGIN
  CREATE TYPE appointmenttype AS ENUM ('demo','call','meeting');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE appointmentstatus AS ENUM ('pending','confirmed','cancelled','completed','rejected');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Product availability slots
CREATE TABLE IF NOT EXISTS product_availability (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id            UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  day_of_week           INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
  start_time            TIME NOT NULL,
  end_time              TIME NOT NULL,
  slot_duration_minutes INTEGER NOT NULL DEFAULT 60,
  is_active             BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_availability_product ON product_availability(product_id);

-- Appointments
CREATE TABLE IF NOT EXISTS appointments (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id   UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  appt_type    appointmenttype NOT NULL DEFAULT 'demo',
  status       appointmentstatus NOT NULL DEFAULT 'pending',
  appt_date    DATE NOT NULL,
  appt_time    TIME NOT NULL,
  timezone     VARCHAR(50) DEFAULT 'Asia/Jakarta',
  notes        TEXT,
  admin_note   TEXT,
  created_at   TIMESTAMP DEFAULT NOW(),
  updated_at   TIMESTAMP DEFAULT NOW(),
  confirmed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_appointments_product ON appointments(product_id);
CREATE INDEX IF NOT EXISTS idx_appointments_user    ON appointments(user_id);
CREATE INDEX IF NOT EXISTS idx_appointments_date    ON appointments(appt_date);
CREATE INDEX IF NOT EXISTS idx_appointments_status  ON appointments(status);
