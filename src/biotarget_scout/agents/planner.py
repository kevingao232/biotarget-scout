"""Planner: query NER first, then build a structured PubMed query string."""

from __future__ import annotations

import re

from biotarget_scout.models.schemas import StructuredQuery
from biotarget_scout.tools.ner import extract_entities

_GENE_BLOCKLIST = frozenset(
    {
        "AND",
        "OR",
        "NOT",
        "THE",
        "RNA",
        "DNA",
        "PCR",
        "FDA",
        "USA",
        "UK",
        "EU",
        "IV",
        "IM",
        "SC",
    }
)


def resolve_pipeline_inputs(user_query: str) -> tuple[str, str]:
    """
    Derive (target_gene, disease_context) from a single natural-language question.

    Uses NER genes when present, otherwise a conservative all-caps token heuristic.
    disease_context is the full user text so reports and PubMed context keep intent.
    """
    raw = (user_query or "").strip()
    if not raw:
        raise ValueError("Query cannot be empty.")

    qe = extract_entities(raw)
    gene: str | None = None
    if qe.genes:
        gene = qe.genes[0].strip().upper()

    if not gene:
        for m in re.finditer(r"\b([A-Z][A-Z0-9]{1,14})\b", raw):
            token = m.group(1).upper()
            if token in _GENE_BLOCKLIST or len(token) < 2:
                continue
            gene = token
            break

    if not gene:
        raise ValueError(
            "Could not infer a gene symbol from your question. Mention a gene such as PCSK9 or TP53."
        )

    return gene, raw


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
