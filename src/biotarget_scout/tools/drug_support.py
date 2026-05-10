"""Heuristic drug mentions from literature text (fallback when no structured drug DB)."""

from __future__ import annotations

import re

from biotarget_scout.models.schemas import EntityResult, KGResult, LiteratureResult

# Case-insensitive tokens for well-known PCSK9 / LDL-lowering biologics (demo-grade list).
_DRUG_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("evolocumab", re.compile(r"\bevolocumab\b", re.I)),
    ("alirocumab", re.compile(r"\balirocumab\b", re.I)),
    ("inclisiran", re.compile(r"\binclisiran\b", re.I)),
    ("repatha", re.compile(r"\brepatha\b", re.I)),
    ("praluent", re.compile(r"\bpraluent\b", re.I)),
    ("bococizumab", re.compile(r"\bbococizumab\b", re.I)),
    ("atorvastatin", re.compile(r"\batorvastatin\b", re.I)),
    ("rosuvastatin", re.compile(r"\brosuvastatin\b", re.I)),
    ("simvastatin", re.compile(r"\bsimvastatin\b", re.I)),
    ("pravastatin", re.compile(r"\bpravastatin\b", re.I)),
    ("lovastatin", re.compile(r"\blovastatin\b", re.I)),
    ("fluvastatin", re.compile(r"\bfluvastatin\b", re.I)),
    ("pitavastatin", re.compile(r"\bpitavastatin\b", re.I)),
)

# NER or abstracts often surface drug *classes*; keep list tight so KG stays compound-level.
_DRUG_CLASS_LEMMAS = frozenset(
    {
        "statin",
        "statins",
        "antibiotic",
        "antibiotics",
        "nsaid",
        "nsaids",
        "chemotherapy",
        "immunosuppressant",
        "immunosuppressants",
        "corticosteroid",
        "corticosteroids",
    }
)


def _is_drug_class_token(name: str) -> bool:
    n = (name or "").strip().lower()
    return n in _DRUG_CLASS_LEMMAS or n.rstrip("s") in _DRUG_CLASS_LEMMAS


def extract_drug_candidates(text: str, entities: EntityResult | None) -> list[str]:
    """Union of NER chemicals (if any) and regex hits on full text."""
    found: dict[str, None] = {}
    blob = text or ""
    for name, pat in _DRUG_PATTERNS:
        if pat.search(blob):
            found[name] = None
    if entities:
        for c in entities.chemicals:
            c = (c or "").strip()
            if len(c) >= 3 and not _is_drug_class_token(c):
                found.setdefault(c, None)
    return sorted(found.keys(), key=str.lower)


def merge_literature_drugs_into_kg(kg: KGResult, lit: LiteratureResult | None) -> KGResult:
    """Append literature-derived drug name hints when ``existing_drugs`` is empty or sparse."""
    if lit is None or not lit.papers:
        return kg
    blob = " ".join(f"{p.title} {p.abstract}" for p in lit.papers)
    found = extract_drug_candidates(blob, lit.entities)
    if not found:
        return kg
    cleaned = [d for d in found if not _is_drug_class_token(d)]
    merged = list(dict.fromkeys([*(kg.existing_drugs or []), *cleaned]))
    if merged == (kg.existing_drugs or []):
        return kg
    return kg.model_copy(update={"existing_drugs": merged})
