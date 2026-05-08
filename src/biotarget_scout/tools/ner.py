from __future__ import annotations

from functools import lru_cache
from biotarget_scout.models.schemas import EntityResult

try:
    import spacy
except Exception:  # pragma: no cover
    spacy = None


@lru_cache(maxsize=1)
def _load_nlp():
    if spacy is None:
        return None
    # A lightweight default keeps setup simple; can be swapped for scispaCy models.
    try:
        return spacy.load("en_core_web_sm")
    except Exception:
        return None


def extract_entities(text: str) -> EntityResult:
    nlp = _load_nlp()
    if nlp is None:
        return EntityResult()

    doc = nlp(text)
    genes: set[str] = set()
    diseases: set[str] = set()
    chemicals: set[str] = set()

    for ent in doc.ents:
        label = ent.label_.upper()
        value = ent.text.strip()
        if not value:
            continue
        if "GENE" in label:
            genes.add(value)
        elif label in {"DISEASE", "NORP", "CONDITION"}:
            diseases.add(value)
        elif label in {"CHEMICAL", "DRUG", "PRODUCT"}:
            chemicals.add(value)

    return EntityResult(
        genes=sorted(genes),
        diseases=sorted(diseases),
        chemicals=sorted(chemicals),
        linked_ids={},
    )
