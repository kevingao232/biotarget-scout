"""Omics specialist: GTEx expression + AlphaFold (via UniProt id resolution)."""

from __future__ import annotations

import asyncio

from biotarget_scout.core.tooling import traced_call
from biotarget_scout.models.schemas import LegStatus, OmicsResult, StructuredQuery
from biotarget_scout.tools import knowledge, omics


async def run_omics(query: StructuredQuery) -> tuple[OmicsResult | None, LegStatus, str]:
    def _sync() -> tuple[OmicsResult | None, LegStatus, str]:
        try:
            expr = traced_call("gtex_expression", lambda: omics.gtex_expression(query.target_gene))
            uni = traced_call("uniprot_lookup", lambda: knowledge.uniprot_lookup(query.target_gene))
            af = None
            if uni.uniprot_id:
                af = traced_call("alphafold_check", lambda: omics.alphafold_check(uni.uniprot_id))
            else:
                af = None
            res = OmicsResult(
                top_tissues=expr,
                structure_available=bool(af and af.available),
                plddt=af.plddt_score if af else None,
            )
            if not expr and not (af and af.available):
                return res, LegStatus.empty, "no_omics_hits"
            return res, LegStatus.ok, ""
        except Exception as exc:
            return None, LegStatus.error, str(exc)

    return await asyncio.to_thread(_sync)
