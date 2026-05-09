"""Tests for RRF and hybrid retrieval (BM25 + mocked vector leg)."""

import re

import pytest

from biotarget_scout.models.schemas import PubMedPaper
from biotarget_scout.retrieval.hybrid import reciprocal_rank_fusion, retrieve
from biotarget_scout.retrieval.indexer import LiteratureIndex


def test_reciprocal_rank_fusion_prefers_consensus_top():
    # Appears at rank 0 in both lists -> should win overall.
    a = ["doc_a", "doc_b", "doc_c"]
    b = ["doc_a", "doc_x", "doc_y"]
    fused = reciprocal_rank_fusion([a, b], k=60)
    assert fused[0] == "doc_a"


def test_reciprocal_rank_fusion_empty_lists():
    assert reciprocal_rank_fusion([[], []]) == []


class FakeChromaCollection:
    """Minimal Chroma-shaped double: upsert stores docs; query ranks by token overlap."""

    def __init__(self) -> None:
        self._id_to_doc: dict[str, str] = {}

    def count(self) -> int:
        return len(self._id_to_doc)

    def upsert(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict] | None = None,
    ) -> None:
        for i, doc in zip(ids, documents):
            self._id_to_doc[i] = doc

    def get(self) -> dict:
        return {"ids": list(self._id_to_doc.keys())}

    def delete(self, ids: list[str] | None = None, where: dict | None = None) -> None:
        if ids:
            for i in ids:
                self._id_to_doc.pop(i, None)

    def query(self, query_texts: list[str], n_results: int) -> dict:
        q = query_texts[0].lower()
        q_tokens = set(re.findall(r"\w+", q))
        scored: list[tuple[str, int]] = []
        for pid, doc in self._id_to_doc.items():
            d_tokens = set(re.findall(r"\w+", doc.lower()))
            scored.append((pid, len(q_tokens & d_tokens)))
        scored.sort(key=lambda x: (-x[1], x[0]))
        top_ids = [p for p, _ in scored[:n_results]]
        return {"ids": [top_ids]}


@pytest.fixture
def tiny_corpus() -> list[PubMedPaper]:
    return [
        PubMedPaper(
            pmid="1",
            title="PCSK9 and LDL cholesterol",
            abstract="PCSK9 regulates LDL receptor degradation.",
            pub_year=2024,
        ),
        PubMedPaper(
            pmid="2",
            title="Diabetes management",
            abstract="Metformin and lifestyle interventions.",
            pub_year=2024,
        ),
        PubMedPaper(
            pmid="3",
            title="Lipid lowering review",
            abstract="Statins reduce cardiovascular risk; PCSK9 inhibitors are discussed.",
            pub_year=2023,
        ),
    ]


def test_retrieve_hybrid_orders_by_fusion(tiny_corpus):
    idx = LiteratureIndex(chroma_collection=FakeChromaCollection())
    idx.add_papers(tiny_corpus)
    # Query emphasizes PCSK9; BM25 and fake vector should both prefer pmid 1 / 3 over 2.
    results = retrieve(idx, "PCSK9 LDL mechanism", top_k=3, candidate_k=10)
    assert results, "expected non-empty retrieval"
    assert results[0].pmid in {"1", "3"}, "top hit should be PCSK9-related, not diabetes-only"
    assert len(results) <= 3


def test_search_bm25_returns_pmids(tiny_corpus):
    idx = LiteratureIndex(chroma_collection=FakeChromaCollection())
    idx.add_papers(tiny_corpus)
    top = idx.search_bm25("PCSK9", k=2)
    assert "1" in top or "3" in top
