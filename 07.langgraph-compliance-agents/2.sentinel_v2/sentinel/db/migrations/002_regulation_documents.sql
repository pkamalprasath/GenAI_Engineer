-- Regulation documents table for pgvector semantic search
-- Populated by scripts/ingest_regulations.py from YAML files
-- Supports cosine similarity search via pgvector embedding column

CREATE TABLE IF NOT EXISTS regulation_documents (
    id               SERIAL PRIMARY KEY,
    regulation_name  TEXT NOT NULL,
    full_name        TEXT NOT NULL,
    section          TEXT NOT NULL,
    content          TEXT NOT NULL,
    domain           TEXT NOT NULL DEFAULT 'finance',
    active           BOOLEAN NOT NULL DEFAULT TRUE,
    embedding        vector(1536),
    created_at       TIMESTAMPTZ DEFAULT now()
);

-- Unique constraint on (regulation_name, section) prevents duplicate sections
CREATE UNIQUE INDEX IF NOT EXISTS idx_regulation_docs_unique
    ON regulation_documents (regulation_name, section);

-- Support queries by domain
CREATE INDEX IF NOT EXISTS idx_regulation_docs_domain
    ON regulation_documents (domain, active);

-- Tenant-agnostic (regulations are global); no tenant_id column
