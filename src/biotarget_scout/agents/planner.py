"""Planner: query NER first, then build a structured PubMed query string."""

from __future__ import annotations

from biotarget_scout.models.schemas import StructuredQuery
from biotarget_scout.tools.ner import extract_entities


def build_structured_query(target_gene: str, disease_context: str) -> StructuredQuery:
    tg = (target_gene or "").strip()
    dc = (disease_context or "").strip()
    raw = f"{tg} {dc}".strip()
    qe = extract_entities(raw)

    parts: list[str] = []
    if tg:
        parts.append(tg)
    if dc:
        parts.append(dc)
    for g in qe.genes:
        gs = (g or "").strip()
        if gs and gs.upper() != tg.upper():
            parts.append(gs)
    for d in qe.diseases:
        ds = (d or "").strip()
        if ds and ds.lower() != dc.lower():
            parts.append(ds)

    seen: set[str] = set()
    uniq: list[str] = []
    for p in parts:
        key = p.strip().lower()
        if key and key not in seen:
            seen.add(key)
            uniq.append(p.strip())

    pubmed_q = " AND ".join(uniq) if uniq else raw
    return StructuredQuery(
        target_gene=tg,
        disease_context=dc,
        raw_text=raw,
        query_entities=qe,
        pubmed_query_string=pubmed_q or raw,
    )
