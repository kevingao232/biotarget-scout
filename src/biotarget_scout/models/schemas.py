from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class LegStatus(str, Enum):
    """Per-specialist outcome for orchestration and confidence."""

    ok = "ok"
    empty = "empty"
    error = "error"
    skipped = "skipped"


class AgentFailure(BaseModel):
    """Typed failure from a specialist leg after retries."""

    agent: str
    error_code: str
    retryable: bool = False
    detail: str = ""


class PubMedPaper(BaseModel):
    pmid: str
    title: str
    abstract: str
    pub_year: int | None = None
    authors: list[str] = Field(default_factory=list)


class UniprotResult(BaseModel):
    gene_symbol: str
    uniprot_id: str | None = None
    protein_name: str | None = None
    function: str | None = None
    organism: str | None = None
    length: int | None = None
    keywords: list[str] = Field(default_factory=list)


class OmimEntry(BaseModel):
    mim_number: str
    title: str
    diseases: list[str] = Field(default_factory=list)


class Interaction(BaseModel):
    partner: str
    score: float


class AlphaFoldResult(BaseModel):
    available: bool = False
    pdb_url: str | None = None
    plddt_score: float | None = None


class EntityResult(BaseModel):
    genes: list[str] = Field(default_factory=list)
    diseases: list[str] = Field(default_factory=list)
    chemicals: list[str] = Field(default_factory=list)
    linked_ids: dict[str, list[str]] = Field(default_factory=dict)


class LiteratureResult(BaseModel):
    papers: list[PubMedPaper] = Field(default_factory=list)
    entities: EntityResult = Field(default_factory=EntityResult)
    summary: str = ""
    evidence_strength: float = 0.0
    reasoning_trace: list[str] = Field(default_factory=list)


class KGResult(BaseModel):
    uniprot_id: str | None = None
    protein_function: str | None = None
    diseases: list[str] = Field(default_factory=list)
    interactors: list[Interaction] = Field(default_factory=list)
    existing_drugs: list[str] = Field(default_factory=list)
    omim_hits: int = 0


class OmicsResult(BaseModel):
    top_tissues: dict[str, float] = Field(default_factory=dict)
    structure_available: bool = False
    plddt: float | None = None


class StructuredQuery(BaseModel):
    """Planner output: raw text, extracted entities, and a PubMed query string."""

    target_gene: str
    disease_context: str
    raw_text: str = ""
    query_entities: EntityResult = Field(default_factory=EntityResult)
    pubmed_query_string: str = ""


class EvidenceBundle(BaseModel):
    """
    Orchestrator merge: optional partial results plus per-leg status.
    Synthesis and ConfidenceScorer both read this; never bypass the orchestrator.
    """

    literature: LiteratureResult | None = None
    literature_status: LegStatus = LegStatus.skipped
    literature_detail: str = ""

    kg: KGResult | None = None
    kg_status: LegStatus = LegStatus.skipped
    kg_detail: str = ""

    omics: OmicsResult | None = None
    omics_status: LegStatus = LegStatus.skipped
    omics_detail: str = ""

    agent_failures: list[AgentFailure] = Field(default_factory=list)
    partial: bool = False


class EvidenceSignals(BaseModel):
    """Structured inputs for ConfidenceScorer (not LLM prose)."""

    literature_ok: bool = False
    kg_ok: bool = False
    omics_ok: bool = False
    paper_count: int = 0
    pubmed_candidates_fetched: int = 0
    has_uniprot_id: bool = False
    omim_entry_count: int = 0
    string_edge_count: int = 0
    has_gtex_data: bool = False
    alphafold_available: bool = False
    plddt: float | None = None
    newest_pub_year: int | None = None
    any_leg_error: bool = False
    partial_bundle: bool = False


class NarrativeDraft(BaseModel):
    """Synthesizer output before ReportAssembler merges scores."""

    evidence_summary: str
    proposed_experiment: str


class HypothesisReport(BaseModel):
    target_gene: str
    disease_context: str
    evidence_summary: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    supporting_papers: list[PubMedPaper] = Field(default_factory=list)
    kg_facts: dict[str, Any] = Field(default_factory=dict)
    expression_profile: dict[str, float] = Field(default_factory=dict)
    proposed_experiment: str
    caveats: list[str] = Field(default_factory=list)
    data_unavailable: bool = False
