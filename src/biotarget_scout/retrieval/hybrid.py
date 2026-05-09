"""
Fuse dense and sparse retrieval with **Reciprocal Rank Fusion (RRF)**.

Why not only vectors? Exact tokens (gene names, drug names, trial IDs) often match
better with BM25. Why not only BM25? Synonyms and paraphrases match better with
embeddings. RRF combines ranked lists without needing score calibration.
"""

from __future__ import annotations

from biotarget_scout.models.schemas import PubMedPaper
from biotarget_scout.retrieval.indexer import LiteratureIndex


def reciprocal_rank_fusion(ranked_lists: list[list[str]], k: int = 60) -> list[str]:
    """
    Merge multiple ordered ID lists into one ranking.

    Each document receives score sum_i 1 / (k + rank_i) across lists where it appears;
    unseen in a list → no contribution from that list. ``k`` dampens the impact of
    top ranks (typical values 20–80; many papers use 60).

    Parameters
    ----------
    ranked_lists
        Each inner list is PMIDs from best to worst for one retriever.
    k
        RRF constant; higher k → flatter weights across ranks.
    """
    scores: dict[str, float] = {}
    for ids in ranked_lists:
        for rank, doc_id in enumerate(ids):
            if not doc_id:
                continue
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.keys(), key=lambda x: scores[x], reverse=True)


def retrieve(
    index: LiteratureIndex,
    query: str,
    top_k: int = 10,
    candidate_k: int = 50,
    rrf_k: int = 60,
) -> list[PubMedPaper]:
    """
    Hybrid retrieval over an already-built ``LiteratureIndex``.

    1. Ask BM25 and Chroma for ``candidate_k`` PMIDs each.
    2. Fuse with RRF.
    3. Return up to ``top_k`` ``PubMedPaper`` objects in fused order (skip missing).
    """
    q = query.strip()
    if not q or len(index) == 0:
        return []

    bm25_ids = index.search_bm25(q, candidate_k)
    vec_ids = index.search_vector(q, candidate_k)
    fused_pmids = reciprocal_rank_fusion([bm25_ids, vec_ids], k=rrf_k)

    out: list[PubMedPaper] = []
    for pmid in fused_pmids:
        if len(out) >= top_k:
            break
        paper = index.get_paper(pmid)
        if paper is not None:
            out.append(paper)
    return out
