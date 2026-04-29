CREATE TABLE IF NOT EXISTS token_blocklist (
    id SERIAL PRIMARY KEY,
    jti VARCHAR(36) NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_token_blocklist_jti ON token_blocklist (jti);
