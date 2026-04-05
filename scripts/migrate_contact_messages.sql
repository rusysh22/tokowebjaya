-- Contact messages table
CREATE TABLE IF NOT EXISTS contact_messages (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name       VARCHAR(255) NOT NULL,
    email      VARCHAR(255) NOT NULL,
    subject    VARCHAR(500),
    message    TEXT NOT NULL,
    status     VARCHAR(20) NOT NULL DEFAULT 'new',
    ip_address VARCHAR(64),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    read_at    TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_contact_messages_status     ON contact_messages(status);
CREATE INDEX IF NOT EXISTS idx_contact_messages_created_at ON contact_messages(created_at DESC);
