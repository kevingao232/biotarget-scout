"""Hybrid literature retrieval: dense (Chroma) + sparse (BM25) + rank fusion."""

from biotarget_scout.retrieval.hybrid import reciprocal_rank_fusion, retrieve
from biotarget_scout.retrieval.indexer import LiteratureIndex

__all__ = ["LiteratureIndex", "reciprocal_rank_fusion", "retrieve"]
