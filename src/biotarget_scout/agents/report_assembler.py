"""Merge narrative draft + structured confidence + evidence bundle into HypothesisReport."""

from __future__ import annotations

from biotarget_scout.models.schemas import (
    EvidenceBundle,
    EvidenceSignals,
    HypothesisReport,
    LegStatus,
    NarrativeDraft,
    StructuredQuery,
)


def assemble_report(
    query: StructuredQuery,
    bundle: EvidenceBundle,
    draft: NarrativeDraft,
    signals: EvidenceSignals,
    confidence: float,
) -> HypothesisReport:
    caveats: list[str] = []
    if bundle.partial:
        caveats.append("Partial evidence: at least one specialist leg failed or returned empty results.")
    if signals.any_leg_error:
        caveats.append("One or more legs reported errors; check logs and upstream API availability.")
    if bundle.literature_detail:
        caveats.append(f"Literature leg: {bundle.literature_detail}")
    if bundle.kg_detail:
        caveats.append(f"KG leg: {bundle.kg_detail}")
    if bundle.omics_detail:
        caveats.append(f"Omics leg: {bundle.omics_detail}")

    kg = bundle.kg
    om = bundle.omics
    if kg and bundle.kg_status == LegStatus.ok and kg.omim_hits == 0:
        caveats.append(
            "OMIM returned no rows for this gene: verify OMIM_API_KEY and network access "
            "(geneMap + entry search are both attempted in logs)."
        )
    if om and bundle.omics_status == LegStatus.ok and not om.top_tissues:
        caveats.append(
            "GTEx median tissue expression was empty after symbol → gencode resolution; "
            "tissue context may be missing (see api_request logs for gtexportal.org)."
        )
    if (
        kg
        and bundle.kg_status == LegStatus.ok
        and not (kg.existing_drugs or [])
        and bundle.literature
        and len(bundle.literature.papers) > 0
    ):
        caveats.append(
            "No drug names were inferred from retrieved abstracts; add a drug database or richer chemical NER "
            "for structured pharmacology."
        )

    supporting = bundle.literature.papers if bundle.literature else []
    kg_facts: dict = {}
    if bundle.kg:
        kg_facts = bundle.kg.model_dump()
    expression = bundle.omics.top_tissues if bundle.omics else {}

    conf = float(confidence)
    if signals.paper_count == 0:
        conf = min(conf, 0.12)

    data_unavailable = not (signals.literature_ok or signals.kg_ok or signals.omics_ok) or conf <= 0.0
    if data_unavailable:
        conf = 0.0
        caveats.append("data_unavailable: insufficient structured evidence across literature, KG, and omics legs.")

    return HypothesisReport(
        target_gene=query.target_gene,
        disease_context=query.disease_context,
        evidence_summary=draft.evidence_summary,
        confidence_score=conf,
        supporting_papers=supporting,
        kg_facts=kg_facts,
        expression_profile=expression,
        proposed_experiment=draft.proposed_experiment,
        caveats=caveats,
        data_unavailable=data_unavailable,
    )
