"""
Orchestrator: owns asyncio.gather, per-leg retries, EvidenceBundle merge, then
parallel narrative synthesis + structured confidence scoring.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger

from biotarget_scout.agents.confidence import bundle_to_signals, score_confidence
from biotarget_scout.agents.kg_agent import run_kg
from biotarget_scout.agents.literature_agent import run_literature
from biotarget_scout.agents.omics_agent import run_omics
from biotarget_scout.agents.planner import build_structured_query
from biotarget_scout.agents.report_assembler import assemble_report
from biotarget_scout.agents.synthesis import synthesize_narrative
from biotarget_scout.core.human_log import block, line
from biotarget_scout.models.schemas import AgentFailure, EvidenceBundle, HypothesisReport, LegStatus
from biotarget_scout.retrieval.indexer import IndexMode, LiteratureIndex
from biotarget_scout.tools.drug_support import merge_literature_drugs_into_kg


def _trunc(s: str, n: int = 160) -> str:
    s = s or ""
    return s if len(s) <= n else f"{s[: n - 3]}..."


def _lit_sentence(tup: tuple[Any, ...]) -> str:
    if len(tup) < 2:
        return "Literature: unexpected empty result."
    res, status, detail = tup[0], tup[1], (tup[2] if len(tup) > 2 else "")
    n_fetch = tup[3] if len(tup) > 3 else 0
    st = status.value if hasattr(status, "value") else str(status)
    n_papers = len(res.papers) if res else 0
    tail = f" ({_trunc(detail)})" if detail else ""
    return (
        f"LITERATURE: status {st}. PubMed had {n_fetch} candidate papers; "
        f"{n_papers} made it through indexing and hybrid search.{tail}"
    )


def _kg_sentence(tup: tuple[Any, ...]) -> str:
    if len(tup) < 2:
        return "KG: unexpected empty result."
    res, status, detail = tup[0], tup[1], (tup[2] if len(tup) > 2 else "")
    st = status.value if hasattr(status, "value") else str(status)
    if res is None:
        return f"KG: status {st}. No bundle returned.{(' ' + _trunc(detail)) if detail else ''}"
    omim = res.omim_hits
    uid = res.uniprot_id or "none"
    n_int = len(res.interactors or [])
    tail = f" ({_trunc(detail)})" if detail else ""
    return f"KG: status {st}. UniProt {uid}, OMIM rows {omim}, STRING partners {n_int}.{tail}"


def _om_sentence(tup: tuple[Any, ...]) -> str:
    if len(tup) < 2:
        return "OMICS: unexpected empty result."
    res, status, detail = tup[0], tup[1], (tup[2] if len(tup) > 2 else "")
    st = status.value if hasattr(status, "value") else str(status)
    if res is None:
        return f"OMICS: status {st}. No bundle returned.{(' ' + _trunc(detail)) if detail else ''}"
    n_t = len(res.top_tissues or {})
    af = "yes" if res.structure_available else "no"
    tail = f" ({_trunc(detail)})" if detail else ""
    return f"OMICS: status {st}. GTEx tissues {n_t}, AlphaFold structure {af}.{tail}"


async def _finalize_leg(
    leg: str,
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
        logger.warning(
            "ORCH: retrying {} leg (attempt {}/{}) — {}.",
            leg,
            attempts + 1,
            extra_retries,
            _trunc(str(out[2]) if len(out) > 2 else ""),
        )
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
    block(
        "Pipeline start",
        [
            f"Gene: {target_gene}",
            f"Context: {_trunc(disease_context, 220)}",
            f"Index mode: {index_mode.value} · Retries per failing leg: {leg_retries}",
        ],
    )

    sq = build_structured_query(target_gene, disease_context)
    line(
        "ORCH",
        f"Planner ready — PubMed query line is “{_trunc(sq.pubmed_query_string, 140)}”. "
        f"NER picked genes {sq.query_entities.genes or '[]'} and diseases {sq.query_entities.diseases or '[]'}.",
    )

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

    block(
        "Parallel specialists finished",
        [
            _lit_sentence(lit_t),
            _kg_sentence(kg_t),
            _om_sentence(om_t),
        ],
    )

    extra = max(0, leg_retries - 1)
    lit_t = await _finalize_leg("literature", lit_t, lit_factory, extra)
    kg_t = await _finalize_leg("kg", kg_t, kg_factory, extra)
    om_t = await _finalize_leg("omics", om_t, om_factory, extra)

    lit_res, lit_status, lit_detail, lit_fetch = lit_t
    kg_res, kg_status, kg_detail = kg_t
    om_res, om_status, om_detail = om_t

    if kg_res is not None and lit_res is not None:
        kg_res = merge_literature_drugs_into_kg(kg_res, lit_res)
        line("ORCH", f"Merged drug hints from literature — {len(kg_res.existing_drugs or [])} drug name(s) on the KG record.")

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
    n_papers = len(bundle.literature.papers) if bundle.literature else 0
    block(
        "Evidence bundle",
        [
            f"Partial picture: {bundle.partial} · Hard failures logged: {len(bundle.agent_failures)}",
            f"Leg statuses — literature: {bundle.literature_status.value}, "
            f"KG: {bundle.kg_status.value}, omics: {bundle.omics_status.value}.",
            f"Papers in bundle: {n_papers}. UniProt on KG: {bundle.kg.uniprot_id if bundle.kg else 'n/a'}. "
            f"GTEx tissue rows: {len(bundle.omics.top_tissues) if bundle.omics else 0}.",
        ],
    )
    for f in failures:
        logger.warning("ORCH: specialist failure — {} ({}) — {}.", f.agent, f.error_code, _trunc(f.detail))

    signals = bundle_to_signals(bundle, pubmed_candidates_fetched=lit_fetch)
    conf = score_confidence(signals)
    line(
        "ORCH",
        f"Confidence score {conf:.2f} "
        f"(literature ok: {signals.literature_ok}, KG ok: {signals.kg_ok}, omics ok: {signals.omics_ok}, "
        f"{signals.paper_count} papers, any leg error: {signals.any_leg_error}).",
    )

    draft = synthesize_narrative(bundle, sq)
    line("ORCH", "Draft narrative and experiment text are ready (deterministic template for now).")

    report = assemble_report(sq, bundle, draft, signals, conf)
    block(
        "Pipeline done",
        [
            f"Report confidence: {report.confidence_score:.2f} · data_unavailable flag: {report.data_unavailable}",
            f"Caveats: {len(report.caveats)} · Supporting papers attached: {len(report.supporting_papers)}",
        ],
    )
    return report
