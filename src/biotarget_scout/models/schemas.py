from typing import Any
from pydantic import BaseModel, Field


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
    protein_function: str | None = None
    diseases: list[str] = Field(default_factory=list)
    interactors: list[Interaction] = Field(default_factory=list)
    existing_drugs: list[str] = Field(default_factory=list)


class OmicsResult(BaseModel):
    top_tissues: dict[str, float] = Field(default_factory=dict)
    structure_available: bool = False
    plddt: float | None = None


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
