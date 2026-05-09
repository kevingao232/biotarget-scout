"""Knowledge-graph specialist: UniProt, OMIM, STRING."""

from __future__ import annotations

import asyncio

from biotarget_scout.core.tooling import traced_call
from biotarget_scout.models.schemas import KGResult, LegStatus, StructuredQuery
from biotarget_scout.tools import knowledge


async def run_kg(query: StructuredQuery) -> tuple[KGResult | None, LegStatus, str]:
    def _sync() -> tuple[KGResult | None, LegStatus, str]:
        try:
            uni = traced_call("uniprot_lookup", lambda: knowledge.uniprot_lookup(query.target_gene))
            omim = traced_call("omim_lookup", lambda: knowledge.omim_lookup(query.target_gene))
            edges = traced_call("string_interactions", lambda: knowledge.string_interactions(query.target_gene))

            diseases: list[str] = []
            for e in omim:
                diseases.append(e.title)
                diseases.extend(e.diseases)

            kg = KGResult(
                uniprot_id=uni.uniprot_id,
                protein_function=uni.function,
                diseases=sorted({d for d in diseases if d}),
                interactors=edges,
                existing_drugs=[],
                omim_hits=len(omim),
            )
            if not uni.uniprot_id and not omim and not edges:
                return kg, LegStatus.empty, "no_kg_hits"
            return kg, LegStatus.ok, ""
        except Exception as exc:
            return None, LegStatus.error, str(exc)

    return await asyncio.to_thread(_sync)
