"""
Orchestrator: owns asyncio.gather, per-leg retries, EvidenceBundle merge, then
parallel narrative synthesis + structured confidence scoring.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from biotarget_scout.agents.confidence import bundle_to_signals, score_confidence
from biotarget_scout.agents.kg_agent import run_kg
from biotarget_scout.agents.literature_agent import run_literature
from biotarget_scout.agents.omics_agent import run_omics
from biotarget_scout.agents.planner import build_structured_query
from biotarget_scout.agents.report_assembler import assemble_report
from biotarget_scout.agents.synthesis import synthesize_narrative
from biotarget_scout.models.schemas import AgentFailure, EvidenceBundle, HypothesisReport, LegStatus
from biotarget_scout.retrieval.indexer import IndexMode, LiteratureIndex


async def _finalize_leg(
    initial: tuple[Any, ...],
    factory: Callable[[], Awaitable[tuple[Any, ...]]],
    extra_retries: int,
) -> tuple[Any, ...]:
    """Re-run a specialist if the first attempt returned LegStatus.error."""
    out: tuple[Any, ...] = initial
    if len(out) < 2:
        return out
    attempts = 0
    while out[1] == LegStatus.error and attempts < extra_retries:
        await asyncio.sleep(0.15 * (attempts + 1))
        out = await factory()
        attempts += 1
    return out


async def run_pipeline(
    target_gene: str,
    disease_context: str,
    *,
    shared_index: LiteratureIndex | None = None,
    index_mode: IndexMode = IndexMode.ephemeral_per_request,
    leg_retries: int = 2,
) -> HypothesisReport:
    sq = build_structured_query(target_gene, disease_context)

    async def lit_factory():
        return await run_literature(
            sq,
            index_mode=index_mode,
            shared_index=shared_index,
        )

    async def kg_factory():
        return await run_kg(sq)

    async def om_factory():
        return await run_omics(sq)

    lit_t, kg_t, om_t = await asyncio.gather(
        lit_factory(),
        kg_factory(),
        om_factory(),
    )

    extra = max(0, leg_retries - 1)
    lit_t = await _finalize_leg(lit_t, lit_factory, extra)
    kg_t = await _finalize_leg(kg_t, kg_factory, extra)
    om_t = await _finalize_leg(om_t, om_factory, extra)

    lit_res, lit_status, lit_detail, lit_fetch = lit_t
    kg_res, kg_status, kg_detail = kg_t
    om_res, om_status, om_detail = om_t

    failures: list[AgentFailure] = []
    if lit_status == LegStatus.error:
        failures.append(AgentFailure(agent="literature", error_code="literature_failed", detail=lit_detail))
    if kg_status == LegStatus.error:
        failures.append(AgentFailure(agent="kg", error_code="kg_failed", detail=kg_detail))
    if om_status == LegStatus.error:
        failures.append(AgentFailure(agent="omics", error_code="omics_failed", detail=om_detail))

    any_ok = any(s == LegStatus.ok for s in (lit_status, kg_status, om_status))
    any_bad = any(s in (LegStatus.error, LegStatus.empty) for s in (lit_status, kg_status, om_status))
    partial = any_ok and any_bad

    bundle = EvidenceBundle(
        literature=lit_res,
        literature_status=lit_status,
        literature_detail=lit_detail,
        kg=kg_res,
        kg_status=kg_status,
        kg_detail=kg_detail,
        omics=om_res,
        omics_status=om_status,
        omics_detail=om_detail,
        agent_failures=failures,
        partial=partial or bool(failures),
    )

    signals = bundle_to_signals(bundle, pubmed_candidates_fetched=lit_fetch)
    conf = score_confidence(signals)
    draft = synthesize_narrative(bundle, sq)
    return assemble_report(sq, bundle, draft, signals, conf)
