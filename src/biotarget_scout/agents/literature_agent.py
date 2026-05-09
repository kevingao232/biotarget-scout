"""Literature specialist: PubMed fetch, index (ephemeral or delta), hybrid retrieve, NER on docs."""

from __future__ import annotations

import asyncio

from biotarget_scout.core.tooling import traced_call
from biotarget_scout.models.schemas import EntityResult, LegStatus, LiteratureResult, StructuredQuery
from biotarget_scout.retrieval.fresh_fetcher import upsert_new_papers_only
from biotarget_scout.retrieval.hybrid import retrieve
from biotarget_scout.retrieval.indexer import IndexMode, LiteratureIndex
from biotarget_scout.tools.ner import extract_entities
from biotarget_scout.tools.pubmed import pubmed_search


def _merge_entities(base: EntityResult, extra: EntityResult) -> EntityResult:
    genes = sorted(set(base.genes) | set(extra.genes))
    diseases = sorted(set(base.diseases) | set(extra.diseases))
    chemicals = sorted(set(base.chemicals) | set(extra.chemicals))
    return EntityResult(genes=genes, diseases=diseases, chemicals=chemicals, linked_ids={})


async def run_literature(
    query: StructuredQuery,
    *,
    index_mode: IndexMode,
    shared_index: LiteratureIndex | None = None,
    max_pubmed: int = 25,
    retrieve_top_k: int = 10,
) -> tuple[LiteratureResult | None, LegStatus, str, int]:
    """
    Returns (result, status, detail, pubmed_candidates_fetched).
    Runs blocking I/O in a thread pool.
    """

    def _sync() -> tuple[LiteratureResult | None, LegStatus, str, int]:
        try:
            if index_mode == IndexMode.persistent_with_delta:
                if shared_index is None:
                    return None, LegStatus.error, "persistent_with_delta requires shared_index", 0
                idx = shared_index
            else:
                idx = LiteratureIndex()

            papers = traced_call(
                "pubmed_search",
                lambda: pubmed_search(query.pubmed_query_string, max_results=max_pubmed),
                extra={"query": query.pubmed_query_string},
            )
            fetched = len(papers)

            if index_mode == IndexMode.persistent_with_delta:
                traced_call(
                    "literature_delta_upsert",
                    lambda: upsert_new_papers_only(idx, papers),
                    extra={"new_batch": len(papers)},
                )
            else:
                traced_call(
                    "literature_full_index",
                    lambda: idx.add_papers(papers, chroma_upsert_mode="full"),
                    extra={"count": len(papers)},
                )

            hits = traced_call(
                "hybrid_retrieve",
                lambda: retrieve(idx, query.pubmed_query_string, top_k=retrieve_top_k),
                extra={"top_k": retrieve_top_k},
            )

            blob = "\n".join(f"{p.title}\n{p.abstract}" for p in hits)
            doc_entities = extract_entities(blob[:50000]) if blob else EntityResult()
            merged = _merge_entities(query.query_entities, doc_entities)

            if not hits and fetched == 0:
                return (
                    LiteratureResult(papers=[], entities=merged, reasoning_trace=["No PubMed hits."]),
                    LegStatus.empty,
                    "no_pubmed_results",
                    0,
                )

            trace = [
                f"pubmed_query={query.pubmed_query_string!r}",
                f"indexed_mode={index_mode.value}",
                f"retrieved_papers={len(hits)}",
            ]
            return (
                LiteratureResult(
                    papers=hits,
                    entities=merged,
                    summary="",
                    evidence_strength=0.0,
                    reasoning_trace=trace,
                ),
                LegStatus.ok if hits else LegStatus.empty,
                "" if hits else "retrieval_empty",
                fetched,
            )
        except Exception as exc:
            return None, LegStatus.error, str(exc), 0

    return await asyncio.to_thread(_sync)
