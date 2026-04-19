"""
retriever.py — Multi-type search with Reciprocal Rank Fusion (RRF).

WHAT PROBLEM DOES THIS SOLVE?
We have three types of chunks: text, table, image.
A question about a bolt torque spec might be answered by:
  - A text paragraph describing the assembly procedure
  - A TABLE ROW with the exact torque value (most precise!)
  - An image caption describing the torque wrench diagram

We search all three types and merge results intelligently.

WHY RRF INSTEAD OF SORTING BY SIMILARITY SCORE?
Similarity scores from different searches are NOT comparable:
  text chunk similarity:  0.82
  table chunk similarity: 0.75

Is the text chunk "better"? Not necessarily — they come from different
distributions. The table might be far more relevant.

RRF uses only RANK POSITION (1st, 2nd, 3rd...) which is comparable
across any source. Formula: score = 1 / (rank + 60)

This means:
  Rank 1 in any source → score 1/61 = 0.016
  Rank 2 in any source → score 1/62 = 0.016
  Rank 10 in any source → score 1/70 = 0.014

A chunk appearing at rank 1 in text AND rank 3 in tables gets
a combined score much higher than one appearing at rank 1 in only one source.
"""

import logging
from collections import defaultdict

try:
    from rank_bm25 import BM25Okapi
    HAS_BM25 = True
except ImportError:
    HAS_BM25 = False

from configs.settings import TOP_K_PER_TYPE, FINAL_TOP_K, RRF_K, USE_HYDE, USE_QUERY_DECOMPOSITION
from src.ingest.vectorstore import VectorStore

logger = logging.getLogger(__name__)
from src.retrieval.hyde import expand_with_hyde
from src.retrieval.query_decomposer import decompose_query

# SDS section keywords — when detected, run an extra targeted search
# on the SDS doc_type to surface safety-specific content
_SDS_KEYWORDS = {
    "first aid", "first-aid", "hazard", "ppe", "personal protective",
    "storage", "disposal", "exposure", "flash point", "flammable",
    "ghs", "pictogram", "signal word", "h statement", "p statement",
    "skin contact", "eye contact", "inhalation", "ingestion",
    "spill", "fire fighting", "fire-fighting", "ecological",
}

def _is_sds_query(query: str) -> bool:
    q = query.lower()
    return any(kw in q for kw in _SDS_KEYWORDS)


class Retriever:
    """
    Main retrieval interface. Combines HyDE + multi-type search + BM25 + RRF.

    Hybrid search: pgvector (dense) + BM25 (sparse/keyword) merged with RRF.
    Dense search catches semantic similarity; BM25 catches exact technical
    terms like "DIN EN 13463-1", "T4", "15-20%" that dense embeddings miss.
    """

    def __init__(self, vector_store: VectorStore | None = None):
        self.vs = vector_store or VectorStore()

    def query(
        self,
        query_text: str,
        doc_type: str | None = None,
        use_hyde: bool = USE_HYDE,
        use_bm25: bool = True,
        use_decomposition: bool = USE_QUERY_DECOMPOSITION,
        limit: int = FINAL_TOP_K,
    ) -> list[dict]:
        """
        Retrieve the most relevant chunks for a query using hybrid search.

        Pipeline:
          1. Query decomposition: break multihop questions into sub-questions
          2. HyDE: expand each sub-question into hypothetical answer doc
          3. Dense search (pgvector) — text, table, image separately per sub-query
          4. BM25 keyword search — across all retrieved candidates
          5. Merge all ranked lists with Reciprocal Rank Fusion
          6. Return top-N, with sub_query label attached to each chunk

        Args:
            query_text        : the user's natural language question
            doc_type          : optional filter (e.g. 'sds', 'manual', 'datasheet')
            use_hyde          : True = HyDE expansion; False = plain dense
            use_bm25          : True = add BM25 keyword search to the mix
            use_decomposition : True = decompose multihop questions into sub-questions
            limit             : number of final results to return
        """
        logger.info("Query: '%s...' (hyde=%s bm25=%s decomp=%s)", query_text[:60], use_hyde, use_bm25, use_decomposition)
        # Step 1: Query decomposition for multihop questions
        if use_decomposition:
            try:
                sub_queries = decompose_query(query_text)
            except Exception as e:
                logger.warning("Query decomposition failed, using original query: %s", e)
                sub_queries = [query_text]
        else:
            sub_queries = [query_text]

        all_ranked_lists = []
        # Track which sub-query each chunk came from for context labelling
        sub_query_map: dict[int, str] = {}  # chunk_id → sub_query text

        for sub_query in sub_queries:
            # Step 2: HyDE expansion per sub-query
            if use_hyde:
                try:
                    search_text = expand_with_hyde(sub_query)
                except Exception as e:
                    logger.warning("HyDE expansion failed, using raw query: %s", e)
                    search_text = sub_query
            else:
                search_text = sub_query

            # Step 3: Embed and run dense search per chunk type
            query_emb = self.vs.embed_query(search_text)

            text_results  = self.vs.search(query_emb, chunk_type="text",  doc_type=doc_type, limit=TOP_K_PER_TYPE)
            table_results = self.vs.search(query_emb, chunk_type="table", doc_type=doc_type, limit=TOP_K_PER_TYPE)
            image_results = self.vs.search(query_emb, chunk_type="image", doc_type=doc_type, limit=TOP_K_PER_TYPE)
            logger.debug("Sub-query '%s...': text=%d table=%d image=%d", sub_query[:40], len(text_results), len(table_results), len(image_results))

            all_dense = text_results + table_results + image_results

            # Tag each chunk with its originating sub-query (first match wins)
            for chunk in all_dense:
                cid = chunk.get("id")
                if cid is not None and cid not in sub_query_map:
                    sub_query_map[cid] = sub_query

            all_ranked_lists.extend([text_results, table_results, image_results])

            # Step 4: BM25 over this sub-query's candidates
            if use_bm25 and HAS_BM25 and all_dense:
                bm25_results = _bm25_rerank(sub_query, all_dense, top_k=TOP_K_PER_TYPE)
                all_ranked_lists.append(bm25_results)

        # Step 4b: SDS section boost — extra targeted search on sds doc_type
        # for safety/chemical queries that tend to get buried by general text
        if _is_sds_query(query_text) and doc_type is None:
            sds_emb = self.vs.embed_query(query_text)
            sds_results = self.vs.search(sds_emb, chunk_type="text", doc_type="sds", limit=TOP_K_PER_TYPE)
            if sds_results:
                for chunk in sds_results:
                    cid = chunk.get("id")
                    if cid is not None and cid not in sub_query_map:
                        sub_query_map[cid] = query_text
                all_ranked_lists.append(sds_results)

        # Step 5: Merge all ranked lists (across all sub-queries) with RRF
        merged = _reciprocal_rank_fusion(all_ranked_lists, k=RRF_K)

        # Step 6: Attach sub_query label to each chunk for prompt context
        for chunk in merged:
            cid = chunk.get("id")
            chunk["sub_query"] = sub_query_map.get(cid, query_text)

        # Store sub_queries on first chunk so generator can access them
        if merged and len(sub_queries) > 1:
            merged[0]["_all_sub_queries"] = sub_queries

        return merged[:limit]


def _bm25_rerank(query: str, chunks: list[dict], top_k: int) -> list[dict]:
    """
    BM25 keyword ranking over a set of candidate chunks.

    Tokenises each chunk's content and the query, scores with BM25Okapi,
    returns top_k chunks sorted by BM25 score.

    Why BM25 on top of dense?
    Dense embeddings average over all tokens — exact values like "15-20%",
    "T4", "DIN EN 13463-1" get diluted. BM25 gives exact token matches
    high scores, catching facts that dense retrieval misses.
    """
    if not HAS_BM25 or not chunks:
        return []

    # Tokenise: lowercase, split on whitespace + punctuation
    # Numeric tokens are duplicated to boost their BM25 weight —
    # values like "85", "1.75", "220" are unique identifiers in engineering tables.
    import re as _re
    def tokenise(text: str) -> list[str]:
        tokens = _re.sub(r"[^\w\s\.]", " ", text.lower()).split()
        boosted = []
        for t in tokens:
            boosted.append(t)
            if _re.match(r"^\d+\.?\d*$", t):   # pure number or decimal
                boosted.append(t)               # duplicate = 2× BM25 weight
        return boosted

    corpus     = [tokenise(c["content"]) for c in chunks]
    query_toks = tokenise(query)

    bm25   = BM25Okapi(corpus)
    scores = bm25.get_scores(query_toks)

    scored = sorted(
        zip(scores, chunks),
        key=lambda x: x[0],
        reverse=True,
    )
    return [c for _, c in scored[:top_k]]


def _reciprocal_rank_fusion(
    ranked_lists: list[list[dict]],
    k: int = 60,
) -> list[dict]:
    """
    Merge multiple ranked lists using Reciprocal Rank Fusion.

    RRF formula: score(chunk) = sum over all lists of: 1 / (rank_in_list + k)

    Where:
      rank_in_list : 0-indexed rank position (first result = rank 0)
      k            : constant (60 is standard; prevents division by zero and
                     dampens the impact of very high ranks)

    Chunks appearing in multiple lists get their scores summed.
    A chunk ranked #1 in text AND #2 in tables scores higher than
    one ranked #1 in only one list.

    Args:
        ranked_lists : list of ranked result lists (each from a different search)
        k            : RRF constant (default 60)

    Returns:
        Single merged list sorted by RRF score descending.
    """
    # Use chunk 'id' as the deduplication key
    scores    = defaultdict(float)
    chunk_map = {}   # id → chunk dict (store full chunk data)

    for ranked_list in ranked_lists:
        for rank, chunk in enumerate(ranked_list):
            chunk_id = chunk["id"]
            scores[chunk_id]    += 1.0 / (rank + k)
            chunk_map[chunk_id]  = chunk   # keep latest (same chunk from diff searches)

    # Attach RRF scores and sort
    results = []
    for chunk_id, rrf_score in scores.items():
        chunk = dict(chunk_map[chunk_id])
        chunk["rrf_score"] = round(rrf_score, 6)
        results.append(chunk)

    results.sort(key=lambda x: x["rrf_score"], reverse=True)
    return results
