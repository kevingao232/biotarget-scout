"""
Incremental literature ingestion: only upsert PMIDs not already in the index.

Chroma receives embeddings only for new documents; BM25 is rebuilt over the
full in-memory corpus (full rebuild keeps implementation simple).
"""

from __future__ import annotations

from biotarget_scout.models.schemas import PubMedPaper
from biotarget_scout.retrieval.indexer import LiteratureIndex


def papers_not_in_index(index: LiteratureIndex, papers: list[PubMedPaper]) -> list[PubMedPaper]:
    """Return papers whose PMID is absent from ``index`` (for delta upsert)."""
    known = set(index.list_pmids())
    out: list[PubMedPaper] = []
    for p in papers:
        pmid = (p.pmid or "").strip()
        if pmid and pmid not in known:
            out.append(p)
    return out


def upsert_new_papers_only(index: LiteratureIndex, papers: list[PubMedPaper]) -> int:
    """Add only PMIDs missing from the index; returns count of newly added."""
    delta = papers_not_in_index(index, papers)
    if not delta:
        return 0
    return index.add_papers(delta, replace_existing=True, chroma_upsert_mode="delta")
