"""Structured confidence scoring (no LLM): operates on EvidenceSignals only."""

from __future__ import annotations

from biotarget_scout.models.schemas import EvidenceBundle, EvidenceSignals, LegStatus


def bundle_to_signals(bundle: EvidenceBundle, *, pubmed_candidates_fetched: int = 0) -> EvidenceSignals:
    lit = bundle.literature
    kg = bundle.kg
    om = bundle.omics

    paper_count = len(lit.papers) if lit else 0
    years = [p.pub_year for p in (lit.papers if lit else []) if p.pub_year]
    newest = max(years) if years else None

    lit_ok = bundle.literature_status == LegStatus.ok and paper_count > 0
    kg_ok = bundle.kg_status == LegStatus.ok and kg is not None and bool(
        kg.uniprot_id or kg.protein_function or kg.diseases or kg.interactors
    )
    om_ok = bundle.omics_status == LegStatus.ok and om is not None and (bool(om.top_tissues) or om.structure_available)

    omim_n = int(kg.omim_hits) if kg else 0
    string_n = len(kg.interactors) if kg else 0
    has_uid = bool(kg and kg.uniprot_id)

    any_err = LegStatus.error in (
        bundle.literature_status,
        bundle.kg_status,
        bundle.omics_status,
    )

    return EvidenceSignals(
        literature_ok=lit_ok,
        kg_ok=kg_ok,
        omics_ok=om_ok,
        paper_count=paper_count,
        pubmed_candidates_fetched=pubmed_candidates_fetched,
        has_uniprot_id=has_uid,
        omim_entry_count=omim_n,
        string_edge_count=string_n,
        has_gtex_data=bool(om and om.top_tissues),
        alphafold_available=bool(om and om.structure_available),
        plddt=om.plddt if om else None,
        newest_pub_year=newest,
        any_leg_error=any_err,
        partial_bundle=bundle.partial,
    )


def score_confidence(signals: EvidenceSignals) -> float:
    score = 0.0
    if signals.paper_count:
        score += min(0.35, 0.07 * signals.paper_count)
    if signals.has_uniprot_id:
        score += 0.15
    if signals.omim_entry_count:
        score += min(0.15, 0.04 * signals.omim_entry_count)
    if signals.string_edge_count:
        score += min(0.1, 0.02 * signals.string_edge_count)
    if signals.has_gtex_data:
        score += 0.1
    if signals.alphafold_available and signals.plddt is not None and signals.plddt >= 70:
        score += 0.1
    elif signals.alphafold_available:
        score += 0.05
    if signals.any_leg_error:
        score *= 0.65
    if signals.partial_bundle:
        score *= 0.85
    if signals.paper_count == 0:
        score = min(score, 0.12)
    return float(max(0.0, min(1.0, score)))
