-- SENTINEL initial schema
-- All tables include tenant_id for row-level isolation.
-- Audit tables are append-only: no UPDATE or DELETE granted in production.

-- Enable pgvector extension (required for engineering-rag integration)
CREATE EXTENSION IF NOT EXISTS vector;

-- ── Decision records ───────────────────────────────────────────────────────────
-- Stores AI decisions that SENTINEL investigates.
-- In production, this table would be populated by the systems under audit.
-- In demo, populated by scripts/seed_database.py from synthetic data.
CREATE TABLE IF NOT EXISTS decision_records (
    id                  SERIAL PRIMARY KEY,
    case_id             VARCHAR(100) NOT NULL,
    tenant_id           VARCHAR(100) NOT NULL,
    outcome             VARCHAR(50)  NOT NULL,
    decision_timestamp  TIMESTAMP    NOT NULL,
    model_version       VARCHAR(100),
    reasoning_text      TEXT,
    metadata            JSONB        DEFAULT '{}',
    created_at          TIMESTAMP    DEFAULT NOW(),
    UNIQUE (case_id, tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_decisions_tenant_date
    ON decision_records (tenant_id, decision_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_decisions_metadata
    ON decision_records USING GIN (metadata);

-- ── Provenance nodes (W3C PROV-O) ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS provenance_nodes (
    id           SERIAL PRIMARY KEY,
    node_id      VARCHAR(200) NOT NULL,
    node_type    VARCHAR(50)  NOT NULL,
    tenant_id    VARCHAR(100) NOT NULL,
    content      JSONB        NOT NULL,
    content_hash VARCHAR(64)  NOT NULL,   -- SHA-256 for tamper detection
    timestamp    TIMESTAMP    NOT NULL,
    metadata     JSONB        DEFAULT '{}',
    UNIQUE (node_id, tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_prov_nodes_tenant
    ON provenance_nodes (tenant_id);
CREATE INDEX IF NOT EXISTS idx_prov_nodes_content
    ON provenance_nodes USING GIN (content);

-- ── Provenance edges ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS provenance_edges (
    id          SERIAL PRIMARY KEY,
    edge_id     VARCHAR(200) NOT NULL,
    source_id   VARCHAR(200) NOT NULL,
    target_id   VARCHAR(200) NOT NULL,
    relation    VARCHAR(100) NOT NULL,   -- W3C PROV-O relation type
    tenant_id   VARCHAR(100) NOT NULL,
    timestamp   TIMESTAMP    NOT NULL,
    metadata    JSONB        DEFAULT '{}',
    UNIQUE (edge_id, tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_prov_edges_tenant
    ON provenance_edges (tenant_id);
CREATE INDEX IF NOT EXISTS idx_prov_edges_source
    ON provenance_edges (source_id, tenant_id);

-- ── Investigations ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS investigations (
    id                 SERIAL PRIMARY KEY,
    investigation_id   VARCHAR(100) NOT NULL UNIQUE,
    tenant_id          VARCHAR(100) NOT NULL,
    status             VARCHAR(50)  NOT NULL DEFAULT 'queued',
    domain             VARCHAR(50)  NOT NULL,
    trigger_mode       VARCHAR(20)  NOT NULL,
    query              TEXT         NOT NULL,   -- PII-redacted query only
    applicant_data     JSONB,                   -- Structured applicant/case data for analysis
    state_snapshot     JSONB,                   -- Full LangGraph state at completion
    total_cost_usd     NUMERIC(10, 6) DEFAULT 0,
    created_at         TIMESTAMP    DEFAULT NOW(),
    completed_at       TIMESTAMP,
    CONSTRAINT chk_status CHECK (status IN (
        'queued','discovering','investigating','analyzing',
        'pending_human','reporting','complete','failed'
    ))
);

CREATE INDEX IF NOT EXISTS idx_investigations_tenant
    ON investigations (tenant_id, created_at DESC);

-- ── Escalations (HITL queue) ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS escalations (
    id               SERIAL PRIMARY KEY,
    escalation_id    VARCHAR(100) NOT NULL UNIQUE,
    investigation_id VARCHAR(100) NOT NULL REFERENCES investigations(investigation_id),
    tenant_id        VARCHAR(100) NOT NULL,
    reason           TEXT         NOT NULL,
    draft_report     TEXT,
    human_response   TEXT,
    reviewer_id      VARCHAR(100),
    status           VARCHAR(20)  NOT NULL DEFAULT 'pending',
    created_at       TIMESTAMP    DEFAULT NOW(),
    resolved_at      TIMESTAMP,
    CONSTRAINT chk_esc_status CHECK (status IN ('pending','resolved','rejected'))
);

CREATE INDEX IF NOT EXISTS idx_escalations_tenant_status
    ON escalations (tenant_id, status, created_at DESC);

-- ── Audit log (append-only — no UPDATE/DELETE in application) ─────────────────
-- COMMENT: In production, REVOKE UPDATE, DELETE ON audit_log FROM application_role;
CREATE TABLE IF NOT EXISTS audit_log (
    id           BIGSERIAL PRIMARY KEY,
    tenant_id    VARCHAR(100) NOT NULL,
    actor        VARCHAR(100) NOT NULL,   -- agent name or human reviewer ID
    action       VARCHAR(100) NOT NULL,
    resource_id  VARCHAR(200),
    details      JSONB        DEFAULT '{}',
    created_at   TIMESTAMP    DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_tenant_time
    ON audit_log (tenant_id, created_at DESC);
