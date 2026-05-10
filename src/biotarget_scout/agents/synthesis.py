"""Deterministic narrative synthesis from EvidenceBundle (LLM can replace later)."""

from __future__ import annotations

from biotarget_scout.models.schemas import EvidenceBundle, NarrativeDraft, StructuredQuery


def _model_context_label(query: StructuredQuery) -> str:
    """Short disease/model phrase for templates (avoid dumping the full user question)."""
    if query.query_entities.diseases:
        return ", ".join(d.strip() for d in query.query_entities.diseases[:3] if d.strip())
    raw = (query.disease_context or "").replace("\n", " ").strip()
    if not raw:
        return "disease-relevant"
    lowered = raw.lower()
    if lowered.startswith(
        ("what ", "how ", "why ", "does ", "is ", "are ", "explain ", "describe ", "tell me ", "summarize ")
    ):
        return "relevant human disease model"
    if len(raw) > 100:
        return raw[:97].rstrip() + "..."
    return raw


def _gtex_expression_nuance(top: dict[str, float]) -> str:
    """
    When a secondary tissue reaches a large fraction of the top TPM, spell out the caveat
    (extrahepatic PCSK9 / brain debate, etc.) so downstream text does not over-read liability.
    """
    if not top or len(top) < 2:
        return ""
    ranked = sorted(top.items(), key=lambda kv: kv[1], reverse=True)
    primary_name, primary_v = ranked[0]
    if primary_v <= 0:
        return ""
    threshold = 0.5 * primary_v
    cohigh = [(n, v) for n, v in ranked[1:] if v >= threshold]
    if not cohigh:
        return ""
    bits = ", ".join(f"{n} ({v:.2f})" for n, v in cohigh[:4])
    return (
        f"GTEx nuance: besides top tissue {primary_name} ({primary_v:.2f}), "
        f"{bits} reach at least half of that signal—interpret with literature context "
        f"(e.g. some targets show strong secondary-tissue TPM without implying equal pharmacology or toxicity)."
    )


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
        nuance = _gtex_expression_nuance(bundle.omics.top_tissues)
        if nuance:
            chunks.append(nuance)
    if bundle.omics and bundle.omics.structure_available:
        plddt = bundle.omics.plddt
        chunks.append(f"AlphaFold structure available (pLDDT={plddt})." if plddt else "AlphaFold structure available.")

    summary = " ".join(chunks) if chunks else "Insufficient evidence across legs for a detailed narrative."
    disease_label = _model_context_label(query)
    prop = (
        f"Design a validation study: modulate {query.target_gene or 'the target'} "
        f"in a {disease_label}; measure primary lipid or functional phenotype and downstream markers "
        f"(align endpoints with the disease context above). "
        f"When GTEx shows a non–classically targeted tissue within ~50% of the highest TPM, "
        f"discuss mechanism and human data (reviews/clinical phenotype) before inferring organ-specific risk."
    )
    return NarrativeDraft(evidence_summary=summary, proposed_experiment=prop)
