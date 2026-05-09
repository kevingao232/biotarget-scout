"""Deterministic narrative synthesis from EvidenceBundle (LLM can replace later)."""

from __future__ import annotations

from biotarget_scout.models.schemas import EvidenceBundle, NarrativeDraft, StructuredQuery


def synthesize_narrative(bundle: EvidenceBundle, query: StructuredQuery) -> NarrativeDraft:
    chunks: list[str] = []
    if bundle.literature and bundle.literature.papers:
        chunks.append(f"Literature leg: {len(bundle.literature.papers)} papers after hybrid retrieval.")
    if bundle.kg and bundle.kg.protein_function:
        fn = bundle.kg.protein_function
        chunks.append(f"Protein function (UniProt): {fn[:400]}{'...' if len(fn) > 400 else ''}")
    if bundle.kg and bundle.kg.diseases:
        chunks.append(f"Associated disease records: {len(bundle.kg.diseases)}.")
    if bundle.omics and bundle.omics.top_tissues:
        items = sorted(bundle.omics.top_tissues.items(), key=lambda kv: kv[1], reverse=True)[:3]
        chunks.append("Top tissues: " + ", ".join(f"{t} ({v:.2f})" for t, v in items))
    if bundle.omics and bundle.omics.structure_available:
        plddt = bundle.omics.plddt
        chunks.append(f"AlphaFold structure available (pLDDT={plddt})." if plddt else "AlphaFold structure available.")

    summary = " ".join(chunks) if chunks else "Insufficient evidence across legs for a detailed narrative."
    prop = (
        f"Design a validation study: modulate {query.target_gene or 'the target'} "
        f"in a {query.disease_context or 'disease-relevant'} model; measure primary phenotype and downstream markers."
    )
    return NarrativeDraft(evidence_summary=summary, proposed_experiment=prop)
