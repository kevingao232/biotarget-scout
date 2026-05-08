from __future__ import annotations

from functools import lru_cache
import httpx
from biotarget_scout.core.config import get_settings
from biotarget_scout.models.schemas import Interaction, OmimEntry, UniprotResult


@lru_cache(maxsize=256)
def uniprot_lookup(gene_symbol: str) -> UniprotResult:
    settings = get_settings()
    gene_symbol = gene_symbol.upper().strip()
    url = "https://rest.uniprot.org/uniprotkb/search"
    params = {"query": f"gene_exact:{gene_symbol} AND reviewed:true", "format": "json", "size": 1}
    try:
        with httpx.Client(timeout=settings.request_timeout_seconds) as client:
            res = client.get(url, params=params)
            res.raise_for_status()
            payload = res.json()
    except Exception:
        return UniprotResult(gene_symbol=gene_symbol)

    items = payload.get("results", [])
    if not items:
        return UniprotResult(gene_symbol=gene_symbol)

    item = items[0]
    comments = item.get("comments", [])
    function = None
    for c in comments:
        if c.get("commentType") == "FUNCTION":
            texts = c.get("texts", [])
            if texts:
                function = texts[0].get("value")
                break

    keywords = [k.get("name") for k in item.get("keywords", []) if k.get("name")]
    return UniprotResult(
        gene_symbol=gene_symbol,
        uniprot_id=item.get("primaryAccession"),
        protein_name=item.get("proteinDescription", {}).get("recommendedName", {}).get("fullName", {}).get("value"),
        function=function,
        organism=item.get("organism", {}).get("scientificName"),
        length=item.get("sequence", {}).get("length"),
        keywords=keywords,
    )


@lru_cache(maxsize=256)
def omim_lookup(gene_symbol: str) -> list[OmimEntry]:
    # OMIM API is paid/restricted for full use. This placeholder returns empty data gracefully.
    _ = gene_symbol
    return []


@lru_cache(maxsize=256)
def string_interactions(gene_symbol: str, limit: int = 10) -> list[Interaction]:
    settings = get_settings()
    try:
        with httpx.Client(timeout=settings.request_timeout_seconds) as client:
            res = client.get(
                "https://string-db.org/api/json/network",
                params={"identifiers": gene_symbol, "species": 9606},
            )
            res.raise_for_status()
            rows = res.json()
    except Exception:
        return []

    interactions: list[Interaction] = []
    for row in rows[:limit]:
        preferred_a = row.get("preferredName_A")
        preferred_b = row.get("preferredName_B")
        score = float(row.get("score", 0.0))
        partner = preferred_b if preferred_a == gene_symbol else preferred_a
        if partner:
            interactions.append(Interaction(partner=partner, score=score))
    return interactions
