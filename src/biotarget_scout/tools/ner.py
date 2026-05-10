from __future__ import annotations

from functools import lru_cache
from typing import Any

from biotarget_scout.models.schemas import EntityResult

try:
    import spacy
except Exception:  # pragma: no cover
    spacy = None

try:
    import scispacy  # noqa: F401 — registers the ``scispacy_linker`` factory with spaCy
    _SCISPACY_IMPORT_OK = True
except Exception:  # pragma: no cover
    _SCISPACY_IMPORT_OK = False

# Prefer biomedical models from the build plan; fall back to general English.
_SPACY_MODEL_ORDER: tuple[str, ...] = (
    "en_core_sci_sm",
    "en_core_web_sm",
)


def _dedupe_case_insensitive(values: set[str]) -> list[str]:
    """One canonical surface form per case-folded key (first occurrence wins)."""
    chosen: dict[str, str] = {}
    for raw in values:
        v = (raw or "").strip()
        if not v:
            continue
        key = v.lower()
        if key not in chosen:
            chosen[key] = v
    return sorted(chosen.values(), key=str.lower)


def _try_add_mesh_linker(nlp: Any) -> None:
    """Optional MESH concept IDs on entities (scispaCy); safe no-op if pipe unavailable."""
    if not _SCISPACY_IMPORT_OK:
        return
    if "scispacy_linker" in nlp.pipe_names:
        return
    try:
        nlp.add_pipe(
            "scispacy_linker",
            last=True,
            config={"resolve_abbreviations": True, "linker_name": "mesh"},
        )
    except Exception:
        return


@lru_cache(maxsize=1)
def _load_nlp():
    if spacy is None:
        return None
    nlp = None
    loaded_name = ""
    for name in _SPACY_MODEL_ORDER:
        try:
            nlp = spacy.load(name)
            loaded_name = name
            break
        except OSError:
            continue
    if nlp is None:
        return None
    if loaded_name == "en_core_sci_sm":
        _try_add_mesh_linker(nlp)
    return nlp


def _kb_ids_for_ent(ent) -> list[str]:
    out: list[str] = []
    kb_ents = getattr(ent._, "kb_ents", None) or getattr(ent._, "umls_ents", None)
    if not kb_ents:
        return out
    for item in kb_ents[:5]:
        if isinstance(item, tuple) and item:
            out.append(str(item[0]))
        elif isinstance(item, str):
            out.append(item)
    return out


def extract_entities(text: str) -> EntityResult:
    nlp = _load_nlp()
    if nlp is None:
        return EntityResult()

    doc = nlp(text[:500_000])
    genes: set[str] = set()
    diseases: set[str] = set()
    chemicals: set[str] = set()
    linked_ids: dict[str, list[str]] = {}

    for ent in doc.ents:
        label = ent.label_.upper()
        value = ent.text.strip()
        if not value:
            continue
        # en_core_sci_* : GENE, CHEMICAL, DISEASE, CELL_TYPE, …
        if "GENE" in label or label in {"GGP"}:
            genes.add(value)
        elif label in {"CHEMICAL", "DRUG", "PRODUCT"}:
            chemicals.add(value)
        elif label in {"DISEASE", "CONDITION", "CANCER"} or "DISEASE" in label:
            diseases.add(value)
        elif label in {"NORP", "ORG"}:
            diseases.add(value)
        elif "CELL" in label:
            continue
        else:
            if "CHEM" in label:
                chemicals.add(value)
            elif "DISEASE" in label or "SYNDROME" in label:
                diseases.add(value)

        ids = _kb_ids_for_ent(ent)
        if ids:
            linked_ids.setdefault(value, [])
            for i in ids:
                if i not in linked_ids[value]:
                    linked_ids[value].append(i)

    return EntityResult(
        genes=_dedupe_case_insensitive(genes),
        diseases=_dedupe_case_insensitive(diseases),
        chemicals=_dedupe_case_insensitive(chemicals),
        linked_ids=linked_ids,
    )
