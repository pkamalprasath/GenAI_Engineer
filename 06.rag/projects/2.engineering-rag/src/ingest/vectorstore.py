"""
vectorstore.py — PostgreSQL + pgvector: schema init, incremental upsert, similarity search.

WHY POSTGRESQL + PGVECTOR OVER CHROMA?
  Chroma scored 5.0 in our experiments (best quality). However for production:
  - pgvector lives in the same Postgres DB as our document metadata
  - Filtering by doc_type, date, page uses standard SQL (WHERE clauses)
  - Incremental updates use UPDATE/DELETE/INSERT natively
  - One Docker container manages everything
  - Data is fully inspectable: SELECT * FROM chunks WHERE chunk_type='table'

SCHEMA:
  documents table  — one row per file, stores file_hash for change detection
  chunks table     — many rows per document, stores content + embedding
  CASCADE DELETE   — deleting a document auto-deletes all its chunks

INCREMENTAL INDEXING:
  Before ingesting any file, we compute its SHA-256 hash.
  If the hash is unchanged since last ingest: SKIP.
  If the hash changed: DELETE old chunks + re-ingest.
  This handles 500 new docs/day (case study requirement) efficiently.
"""

import hashlib
import logging
import re
from pathlib import Path

import psycopg2
import psycopg2.extras
from sentence_transformers import SentenceTransformer

from configs.settings import DATABASE_URL, EMBED_MODEL, EMBED_DIM, TOP_K_PER_TYPE, POSTGRES_SSL

logger = logging.getLogger(__name__)


# ── Schema SQL ────────────────────────────────────────────────────────────

SCHEMA_SQL = f"""
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id          SERIAL PRIMARY KEY,
    filename    TEXT NOT NULL,
    doc_type    TEXT,
    file_hash   TEXT UNIQUE NOT NULL,
    ingested_at TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chunks (
    id          SERIAL PRIMARY KEY,
    doc_id      INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    parent_id   INTEGER REFERENCES chunks(id) ON DELETE CASCADE,
    content     TEXT NOT NULL,
    parent_content TEXT,
    chunk_type  TEXT NOT NULL CHECK (chunk_type IN ('text', 'table', 'image')),
    page        INTEGER,
    section     TEXT,
    image_path  TEXT,
    embedding   vector({EMBED_DIM})
);

CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS chunks_doc_id_idx
    ON chunks (doc_id);

CREATE INDEX IF NOT EXISTS chunks_type_idx
    ON chunks (chunk_type);
"""


class VectorStore:
    """
    Manages the PostgreSQL + pgvector store.

    Usage:
        vs = VectorStore()
        vs.init_schema()               # run once on startup
        vs.upsert_document(...)        # ingest or update a document
        vs.search(query_emb, ...)      # find similar chunks
    """

    def __init__(self):
        kwargs = {"dsn": DATABASE_URL}
        if POSTGRES_SSL:
            kwargs["sslmode"] = POSTGRES_SSL
        try:
            self._conn = psycopg2.connect(**kwargs)
            self._conn.autocommit = False
            logger.info("PostgreSQL connection established")
        except psycopg2.OperationalError as e:
            logger.critical("Cannot connect to PostgreSQL: %s", e, exc_info=True)
            raise
        try:
            self._embedder = SentenceTransformer(EMBED_MODEL, device="cpu")
            logger.info("Embedding model loaded: %s", EMBED_MODEL)
        except Exception as e:
            logger.critical("Failed to load embedding model '%s': %s", EMBED_MODEL, e, exc_info=True)
            raise

    # ── Schema ─────────────────────────────────────────────────────────────

    def init_schema(self) -> None:
        """Create tables and indexes if they don't exist. Safe to call repeatedly."""
        try:
            with self._conn.cursor() as cur:
                cur.execute(SCHEMA_SQL)
            self._conn.commit()
            logger.info("DB schema ready (documents + chunks + pgvector indexes)")
        except Exception as e:
            self._conn.rollback()
            logger.error("Schema initialization failed: %s", e, exc_info=True)
            raise

    # ── Incremental Ingestion ─────────────────────────────────────────────

    def check_file_status(self, filepath: Path) -> tuple[str, int | None]:
        """
        Check whether a file needs to be ingested.

        Returns:
            ('new', None)          — file not in DB, ingest it
            ('unchanged', doc_id)  — file unchanged, skip it
            ('changed', doc_id)    — file changed, delete old + re-ingest
        """
        file_hash = _compute_hash(filepath)

        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT id, file_hash FROM documents WHERE filename = %s",
                [filepath.name],
            )
            row = cur.fetchone()

        if row is None:
            return "new", None

        existing_id, existing_hash = row
        if existing_hash == file_hash:
            return "unchanged", existing_id
        else:
            return "changed", existing_id

    def upsert_document(
        self,
        filepath: Path,
        doc_type: str,
        chunks: list[dict],
    ) -> int:
        """
        Insert or update a document and all its chunks.

        If the file already exists (changed), old chunks are deleted first
        (CASCADE DELETE handles this automatically when we delete the document row).

        Args:
            filepath : path to the source file
            doc_type : 'manual' | 'sds' | 'datasheet' | 'compliance' | 'other'
            chunks   : list of chunk dicts from chunker.chunk_document()

        Returns:
            doc_id of the newly inserted document row
        """
        file_hash = _compute_hash(filepath)
        logger.info("Upserting '%s' (%d chunks)", filepath.name, len(chunks))

        try:
            with self._conn.cursor() as cur:
                cur.execute("DELETE FROM documents WHERE filename = %s", [filepath.name])
                cur.execute(
                    """INSERT INTO documents (filename, doc_type, file_hash, updated_at)
                       VALUES (%s, %s, %s, NOW()) RETURNING id""",
                    [filepath.name, doc_type, file_hash],
                )
                doc_id = cur.fetchone()[0]

                contents = [c["content"] for c in chunks]
                try:
                    embeddings = self._embedder.encode(
                        contents, batch_size=64, normalize_embeddings=True,
                        show_progress_bar=len(contents) > 50,
                    )
                except Exception as e:
                    logger.error("Embedding failed for '%s': %s", filepath.name, e, exc_info=True)
                    raise

                chunk_records = [
                    (doc_id, c["content"], c.get("parent_content"), c["chunk_type"],
                     c.get("page"), c.get("section", ""), c.get("image_path"), emb.tolist())
                    for c, emb in zip(chunks, embeddings)
                ]
                psycopg2.extras.execute_values(
                    cur,
                    """INSERT INTO chunks
                       (doc_id, content, parent_content, chunk_type, page, section, image_path, embedding)
                       VALUES %s""",
                    chunk_records,
                    template="(%s, %s, %s, %s, %s, %s, %s, %s::vector)",
                )

            self._conn.commit()
            logger.info("Upserted '%s' → doc_id=%d, %d chunks", filepath.name, doc_id, len(chunks))
            return doc_id
        except Exception as e:
            self._conn.rollback()
            logger.error("Upsert failed for '%s', rolled back: %s", filepath.name, e, exc_info=True)
            raise

    # ── Search ─────────────────────────────────────────────────────────────

    def search(
        self,
        query_embedding: list[float],
        chunk_type: str | None = None,
        doc_type: str | None = None,
        limit: int = TOP_K_PER_TYPE,
    ) -> list[dict]:
        """
        Find the most similar chunks to a query embedding.

        Uses pgvector's cosine distance operator <=> for approximate nearest-neighbor.

        Args:
            query_embedding : 384-dim vector (from sentence-transformers)
            chunk_type      : filter to 'text', 'table', or 'image' (None = all types)
            doc_type        : filter to specific document type (None = all docs)
            limit           : number of results to return

        Returns:
            list of chunk dicts with added 'similarity' score (0.0 to 1.0)
        """
        # Build WHERE clause dynamically
        where_clauses = []
        params = []

        if chunk_type:
            where_clauses.append("c.chunk_type = %s")
            params.append(chunk_type)

        if doc_type:
            where_clauses.append("d.doc_type = %s")
            params.append(doc_type)

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        # 1 - cosine_distance converts distance to similarity (higher = more similar)
        query_sql = f"""
            SELECT
                c.id,
                c.content,
                COALESCE(c.parent_content, c.content) AS parent_content,
                c.chunk_type,
                c.page,
                c.section,
                c.image_path,
                d.filename,
                d.doc_type,
                1 - (c.embedding <=> %s::vector) AS similarity
            FROM chunks c
            JOIN documents d ON c.doc_id = d.id
            {where_sql}
            ORDER BY c.embedding <=> %s::vector
            LIMIT %s
        """

        vec_str = _list_to_pgvector(query_embedding)
        params  = [vec_str] + params + [vec_str, limit]

        try:
            with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SET ivfflat.probes = 10")
                cur.execute("SET hnsw.ef_search = 200")
                cur.execute(query_sql, params)
                rows = cur.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error("Vector search failed (chunk_type=%s, doc_type=%s): %s", chunk_type, doc_type, e, exc_info=True)
            raise

    def embed_query(self, text: str) -> list[float]:
        try:
            emb = self._embedder.encode(text, normalize_embeddings=True)
            return emb.tolist()
        except Exception as e:
            logger.error("embed_query failed for text='%s...': %s", text[:50], e, exc_info=True)
            raise

    def get_stats(self) -> dict:
        try:
            with self._conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM documents")
                doc_count = cur.fetchone()[0]
                cur.execute("SELECT chunk_type, COUNT(*) FROM chunks GROUP BY chunk_type")
                type_counts = dict(cur.fetchall())
            return {"documents": doc_count, "chunks_by_type": type_counts, "total_chunks": sum(type_counts.values())}
        except Exception as e:
            logger.error("get_stats failed: %s", e, exc_info=True)
            return {"documents": 0, "chunks_by_type": {}, "total_chunks": 0}

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass


# ── Utilities ─────────────────────────────────────────────────────────────

def _compute_hash(filepath: Path) -> str:
    """
    Compute SHA-256 hash of a file's content.

    This is the key to incremental indexing:
    - Same file content → same hash → SKIP (no re-processing)
    - Changed content   → different hash → DELETE + RE-INDEX

    SHA-256 is used because:
    - Collision probability is negligible (1 in 2^256)
    - Fast to compute even for large files
    - 64-character hex string is easy to store
    """
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _list_to_pgvector(vec: list[float]) -> str:
    """Convert a Python list to pgvector's string format: '[0.1, 0.2, ...]'"""
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"
