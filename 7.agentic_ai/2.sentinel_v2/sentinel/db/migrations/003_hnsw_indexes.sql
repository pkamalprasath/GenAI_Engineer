-- Phase 3: HNSW indexes for O(log n) vector similarity search
-- HNSW provides faster semantic search over large regulation datasets
-- Replaces ivfflat index with superior performance characteristics
--
-- Parameters (from pgvector best practices):
--   m = 16       — max connections per node (memory vs quality tradeoff)
--   ef_construction = 64  — search extent during index creation
--
-- Apply manually:
--   psql $DATABASE_URL -f sentinel/db/migrations/003_hnsw_indexes.sql

-- Primary index: regulation documents (1536-dim embeddings from text-embedding-3-small)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_regulation_docs_hnsw
    ON regulation_documents USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Drop old ivfflat index if it exists (after HNSW is built, CONCURRENTLY prevents locks)
-- Uncomment after verifying HNSW index is working:
-- DROP INDEX CONCURRENTLY IF EXISTS reg_docs_embedding_idx;

-- Optional: investigation_patterns table if compliance pattern ML is enabled
-- Uncomment if investigation_patterns table confirmed in 001_initial_schema.sql:
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_investigation_patterns_hnsw
--     ON investigation_patterns USING hnsw (embedding vector_cosine_ops)
--     WITH (m = 16, ef_construction = 64);
