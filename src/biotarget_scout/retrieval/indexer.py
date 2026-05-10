"""
Index PubMed papers for local hybrid search.

We store each paper twice in complementary forms:
- **Chroma**: embedding of title+abstract (semantic / paraphrase-friendly).
- **BM25**: bag-of-words over the same text (exact token matches, e.g. gene symbols).

Both lists are aligned by PMID so we can fuse rankings in ``hybrid.retrieve``.
"""

from __future__ import annotations

import os
import re
from enum import Enum
from typing import Any, Literal

import chromadb
from chromadb.utils import embedding_functions
from rank_bm25 import BM25Okapi

from biotarget_scout.core.config import ensure_hf_hub_token
from biotarget_scout.models.schemas import PubMedPaper

# Chroma collection names must be 3–512 chars from [a-zA-Z0-9._-].
_DEFAULT_COLLECTION = "bio_literature"

# Build plan default: PubMed-tuned embeddings; override via env for CI/speed.
_DEFAULT_EMBEDDING_MODEL = os.getenv(
    "BIOTARGET_EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)


class IndexMode(str, Enum):
    """
    Ephemeral: rebuild or isolate index per request (dev / demos).
    Persistent + delta: long-lived Chroma store; upsert only touched PMIDs per fetch.
    """

    ephemeral_per_request = "ephemeral_per_request"
    persistent_with_delta = "persistent_with_delta"


def _tokenize(text: str) -> list[str]:
    """BM25 tokenization: lowercase word tokens (simple, fast, good enough for bio acronyms)."""
    return re.findall(r"\w+", text.lower())


def _doc_text(paper: PubMedPaper) -> str:
    """Single string we embed and index lexically (title carries strong keyword signal)."""
    return f"{paper.title}\n{paper.abstract}".strip()


class LiteratureIndex:
    """
    In-memory PMID → paper map plus Chroma vector store and BM25 lexical index.

    Parameters
    ----------
    persist_directory
        If set, Chroma persists to disk so you do not re-embed on every run.
    collection_name
        Chroma collection name (must satisfy Chroma naming rules).
    embedding_model_name
        Sentence-Transformers model id. Default is small/fast; swap for
        ``pritamdeka/S-PubMedBert-MS-MARCO`` when you want PubMed-tuned embeddings.
    chroma_collection
        Optional pre-built collection (e.g. test double). If set, ``persist_directory``
        and client creation are skipped.
    """

    def __init__(
        self,
        persist_directory: str | None = None,
        collection_name: str = _DEFAULT_COLLECTION,
        embedding_model_name: str = _DEFAULT_EMBEDDING_MODEL,
        chroma_collection: Any | None = None,
    ) -> None:
        self._collection_name = collection_name
        self._embedding_model_name = embedding_model_name
        self._embedding_fn: Any = None

        if chroma_collection is None:
            ensure_hf_hub_token()

        if chroma_collection is not None:
            # Tests can inject a fake collection; no SentenceTransformer download.
            self._client = None
            self._collection = chroma_collection
        else:
            # Chroma applies this model on add() and query(); same space for both.
            self._embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=embedding_model_name
            )
            if persist_directory:
                self._client = chromadb.PersistentClient(path=persist_directory)
            else:
                self._client = chromadb.Client()
            self._collection = self._client.get_or_create_collection(
                name=collection_name,
                embedding_function=self._embedding_fn,
            )

        self._papers: dict[str, PubMedPaper] = {}
        # Parallel arrays: same order so BM25 row i ↔ PMID i ↔ Chroma id i.
        self._pmids: list[str] = []
        self._texts: list[str] = []
        self._bm25: BM25Okapi | None = None

    def __len__(self) -> int:
        return len(self._papers)

    def get_paper(self, pmid: str) -> PubMedPaper | None:
        return self._papers.get(pmid)

    def list_pmids(self) -> list[str]:
        return sorted(self._papers.keys())

    def _rebuild_bm25(self) -> None:
        if not self._texts:
            self._bm25 = None
            return
        tokenized_corpus = [_tokenize(t) for t in self._texts]
        # BM25Okapi expects a list of token lists; one row per document.
        self._bm25 = BM25Okapi(tokenized_corpus)

    def clear(self) -> None:
        """Remove all indexed papers from memory and Chroma (BM25 reset)."""
        if self._collection is not None and self._collection.count() > 0:
            # Fetch all IDs Chroma knows about, then delete in batch.
            batch = self._collection.get()
            ids = batch.get("ids") or []
            if ids:
                self._collection.delete(ids=ids)
        self._papers.clear()
        self._pmids.clear()
        self._texts.clear()
        self._bm25 = None

    def add_papers(
        self,
        papers: list[PubMedPaper],
        replace_existing: bool = True,
        chroma_upsert_mode: Literal["full", "delta"] = "full",
    ) -> int:
        """
        Merge papers into the in-memory map, then refresh Chroma + BM25 in one pass.

        Rebuilding ``_pmids`` / ``_texts`` from ``_papers`` keeps BM25 rows and
        Chroma ids in lockstep (one row per PMID).

        Returns number of papers accepted from this batch (skipped if duplicate and
        ``replace_existing`` is False).
        """
        # Last paper wins if the same PMID appears twice in one batch.
        batch: dict[str, PubMedPaper] = {}
        for paper in papers:
            pmid = (paper.pmid or "").strip()
            if not pmid:
                continue
            if not _doc_text(paper):
                continue
            batch[pmid] = paper

        accepted = 0
        for pmid, paper in batch.items():
            if pmid in self._papers and not replace_existing:
                continue
            self._papers[pmid] = paper
            accepted += 1

        if not self._papers:
            self._pmids.clear()
            self._texts.clear()
            self._bm25 = None
            return accepted

        # Stable order: same PMID always maps to same BM25 row index.
        self._pmids = sorted(self._papers.keys())
        self._texts = [_doc_text(self._papers[pid]) for pid in self._pmids]

        if chroma_upsert_mode == "delta":
            candidate_ids = sorted(batch.keys())
        else:
            candidate_ids = list(self._pmids)

        upsert_ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []
        for pid in candidate_ids:
            p = self._papers.get(pid)
            if p is None:
                continue
            upsert_ids.append(pid)
            documents.append(_doc_text(p))
            metadatas.append(
                {
                    "title": (p.title or "")[:2000],
                    "pub_year": int(p.pub_year) if p.pub_year is not None else -1,
                }
            )
        if upsert_ids:
            self._collection.upsert(ids=upsert_ids, documents=documents, metadatas=metadatas)
        self._rebuild_bm25()
        return accepted

    def search_bm25(self, query: str, k: int) -> list[str]:
        """Top-k PMIDs by lexical BM25 score."""
        if not query.strip() or self._bm25 is None:
            return []
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []
        scores = self._bm25.get_scores(q_tokens)
        # Argsort descending; numpy-free for fewer deps.
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        top = ranked[:k]
        return [self._pmids[i] for i in top]

    def search_vector(self, query: str, k: int) -> list[str]:
        """Top-k PMIDs by embedding similarity (Chroma handles encoding the query)."""
        if not query.strip():
            return []
        if self._collection.count() == 0:
            return []
        result = self._collection.query(query_texts=[query], n_results=min(k, self._collection.count()))
        ids = result.get("ids") or []
        return list(ids[0]) if ids else []
