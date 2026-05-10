from __future__ import annotations

from functools import lru_cache

import httpx
from loguru import logger

from biotarget_scout.core.config import get_settings
from biotarget_scout.models.schemas import Interaction, OmimEntry, UniprotResult


def _ensembl_gene_id_from_uniprot_item(item: dict) -> str | None:
    """First Ensembl **gene** id (ENSG…), version stripped for GTEx."""
    for ref in item.get("uniProtKBCrossReferences", []) or []:
        if ref.get("database") != "Ensembl":
            continue
        props = ref.get("properties") or []
        for p in props:
            if p.get("key") == "GeneId" and p.get("value"):
                raw = str(p["value"]).strip()
                if raw.startswith("ENSG"):
                    return raw.split(".")[0]
        rid = ref.get("id")
        if isinstance(rid, str) and rid.startswith("ENSG"):
            return rid.split(".")[0]
    return None


@lru_cache(maxsize=256)
def uniprot_lookup(gene_symbol: str) -> UniprotResult:
    settings = get_settings()
    gene_symbol = gene_symbol.upper().strip()
    url = "https://rest.uniprot.org/uniprotkb/search"
    # Reviewed Swiss-Prot human only; avoids TrEMBL fragments (e.g. wrong accession for PCSK9).
    q = f"(gene:{gene_symbol}) AND (reviewed:true) AND (organism_id:9606)"
    params = {"query": q, "format": "json", "size": 1}
    logger.debug(
        "api_request service=uniprot method=GET path=/uniprotkb/search gene={} reviewed=human format=json",
        gene_symbol,
    )
    try:
        with httpx.Client(timeout=settings.request_timeout_seconds) as client:
            res = client.get(url, params=params)
            res.raise_for_status()
            payload = res.json()
    except Exception as exc:
        logger.warning(
            "api_response service=uniprot status=error gene={} err={}",
            gene_symbol,
            exc,
        )
        return UniprotResult(gene_symbol=gene_symbol)

    items = payload.get("results", [])
    logger.debug(
        "api_response service=uniprot status=ok gene={} result_count={}",
        gene_symbol,
        len(items),
    )
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
    ensembl = _ensembl_gene_id_from_uniprot_item(item)
    return UniprotResult(
        gene_symbol=gene_symbol,
        uniprot_id=item.get("primaryAccession"),
        protein_name=item.get("proteinDescription", {}).get("recommendedName", {}).get("fullName", {}).get("value"),
        function=function,
        organism=item.get("organism", {}).get("scientificName"),
        length=item.get("sequence", {}).get("length"),
        keywords=keywords,
        ensembl_gene_id=ensembl,
    )


def _omim_headers(api_key: str) -> dict[str, str]:
    """OMIM validates keys before processing; canonical header name is ``ApiKey`` (see omim.org/help/api)."""
    return {
        "Accept": "application/json",
        "ApiKey": api_key.strip(),
    }


def _parse_omim_gene_map_json(payload: dict) -> list[OmimEntry]:
    """Parse OMIM ``geneMap`` JSON (geneMapList); avoids broad tree walks that duplicate MIMs."""
    out: list[OmimEntry] = []
    seen: set[str] = set()
    om = payload.get("omim")
    if not isinstance(om, dict):
        return []
    gml = om.get("geneMapList")
    if gml is None and isinstance(om.get("listResponse"), dict):
        gml = om["listResponse"].get("geneMapList")
    if not isinstance(gml, list):
        return []
    for wrap in gml:
        gm = None
        if isinstance(wrap, dict):
            gm = wrap.get("geneMap")
            if gm is None and "mimNumber" in wrap:
                gm = wrap
        if not isinstance(gm, dict):
            continue
        mim = gm.get("mimNumber")
        if mim is None:
            continue
        mim_s = str(mim).strip()
        title = ""
        titles = gm.get("titles")
        if isinstance(titles, dict):
            title = str(titles.get("preferredTitle", "")).strip()
        if not title:
            title = str(gm.get("geneName") or gm.get("geneSymbol") or f"MIM {mim_s}").strip()
        phenotypes: list[str] = []
        for pm in gm.get("phenotypeMapList", []) or []:
            if not isinstance(pm, dict):
                continue
            pmap = pm.get("phenotypeMap")
            if isinstance(pmap, dict) and pmap.get("phenotype"):
                phenotypes.append(str(pmap["phenotype"]))
        if mim_s and mim_s not in seen:
            seen.add(mim_s)
            out.append(OmimEntry(mim_number=mim_s, title=title, diseases=phenotypes))
    return out


@lru_cache(maxsize=256)
def omim_lookup(gene_symbol: str) -> list[OmimEntry]:
    settings = get_settings()
    api_key = getattr(settings, "omim_api_key", "")
    if not api_key:
        logger.info("KG: OMIM is skipped — add OMIM_API_KEY to your environment if you want gene–disease links.")
        return []

    query = gene_symbol.strip().upper()
    headers = _omim_headers(api_key)

    def _gene_map_attempt(
        client: httpx.Client, params: dict[str, str | int], label: str
    ) -> list[OmimEntry]:
        logger.debug(
            "api_request service=omim method=GET path=/api/geneMap gene={} mode={} format=json",
            query,
            label,
        )
        res = client.get("https://api.omim.org/api/geneMap", params=params, headers=headers)
        res.raise_for_status()
        payload = res.json()
        if not isinstance(payload, dict):
            return []
        out = _parse_omim_gene_map_json(payload)
        logger.debug(
            "api_response service=omim geneMap gene={} mode={} parsed_entries={}",
            query,
            label,
            len(out),
        )
        if not out:
            om_keys = list((payload.get("omim") or {}).keys())[:12]
            logger.debug(
                "api_empty service=omim step=geneMap gene={} mode={} omim_json_keys={}",
                query,
                label,
                om_keys,
            )
        return out

    entries: list[OmimEntry] = []
    try:
        with httpx.Client(timeout=settings.request_timeout_seconds) as client:
            for label, gm_params in (
                ("geneSymbol", {"geneSymbol": query, "format": "json"}),
                ("geneSymbols", {"geneSymbols": query, "format": "json"}),
            ):
                try:
                    entries = _gene_map_attempt(client, gm_params, label)
                except Exception as exc:
                    logger.warning(
                        "api_response service=omim geneMap status=error gene={} mode={} err={}",
                        query,
                        label,
                        exc,
                    )
                    entries = []
                if entries:
                    return entries

            logger.debug(
                "api_request service=omim method=GET path=/api/geneMap/search gene={} (approved_gene_symbol)",
                query,
            )
            try:
                res = client.get(
                    "https://api.omim.org/api/geneMap/search",
                    params={
                        "search": f"approved_gene_symbol:{query}",
                        "start": 0,
                        "limit": 25,
                        "format": "json",
                    },
                    headers=headers,
                )
                res.raise_for_status()
                payload = res.json()
                if isinstance(payload, dict):
                    entries = _parse_omim_gene_map_json(payload)
                    logger.debug(
                        "api_response service=omim geneMap/search gene={} parsed_entries={}",
                        query,
                        len(entries),
                    )
            except Exception as exc:
                logger.warning("api_response service=omim geneMap/search status=error gene={} err={}", query, exc)
                entries = []

            if entries:
                return entries

            logger.debug(
                "api_request service=omim method=GET path=/api/entry/search gene={} approved_gene_symbol",
                query,
            )
            res = client.get(
                "https://api.omim.org/api/entry/search",
                params={
                    "search": f"approved_gene_symbol:{query}",
                    "format": "json",
                    "limit": 10,
                    "include": "geneMap",
                },
                headers=headers,
            )
            res.raise_for_status()
            payload = res.json()
    except Exception as exc:
        logger.warning("api_response service=omim entry_search status=error gene={} err={}", query, exc)
        return []

    if not isinstance(payload, dict):
        return []

    entry_list = payload.get("omim", {}).get("searchResponse", {}).get("entryList", [])
    logger.debug("api_response service=omim entry_search gene={} entry_list_count={}", query, len(entry_list))
    if not entry_list:
        logger.warning(
            "api_empty service=omim step=entry_search gene={} detail=http_ok_but_entryList_empty",
            query,
        )

    entries = []
    for row in entry_list:
        entry = row.get("entry", {})
        mim_number = str(entry.get("mimNumber", ""))
        title = str(entry.get("titles", {}).get("preferredTitle", "")).strip()
        phenotypes: list[str] = []
        gmap = entry.get("geneMap")
        pmap_list = gmap.get("phenotypeMapList", []) if isinstance(gmap, dict) else []
        for phenotype in pmap_list or []:
            if not isinstance(phenotype, dict):
                continue
            pmap = phenotype.get("phenotypeMap")
            phenotype_text = pmap.get("phenotype") if isinstance(pmap, dict) else None
            if phenotype_text:
                phenotypes.append(str(phenotype_text))
        if mim_number and title:
            entries.append(OmimEntry(mim_number=mim_number, title=title, diseases=phenotypes))

    if not entries:
        logger.warning(
            "api_empty service=omim step=combined gene={} detail=no_rows_after_geneMap_and_entry_search_check_api_key_and_format",
            query,
        )
    return entries


def _is_immunoglobulin_variable_region_symbol(symbol: str) -> bool:
    """
    STRING often links therapeutic antibodies (e.g. evolocumab) to IG variable genes;
    those edges are not physiologic protein–protein partners for target biology.
    """
    u = (symbol or "").strip().upper()
    if len(u) < 5:
        return False
    return u.startswith(("IGHV", "IGKV", "IGLV", "IGLL"))


def _dedupe_string_edges(rows: list[dict], gene_symbol: str, limit: int) -> list[Interaction]:
    """One edge per STRING partner; keep max(score) across evidence channels."""
    best: dict[str, float] = {}
    for row in rows:
        preferred_a = row.get("preferredName_A")
        preferred_b = row.get("preferredName_B")
        score = float(row.get("score", 0.0))
        partner = preferred_b if preferred_a == gene_symbol else preferred_a
        if not partner:
            continue
        p = str(partner).upper()
        if _is_immunoglobulin_variable_region_symbol(p):
            continue
        prev = best.get(p)
        if prev is None or score > prev:
            best[p] = score
    ranked = sorted(best.items(), key=lambda kv: kv[1], reverse=True)
    return [Interaction(partner=a, score=s) for a, s in ranked[:limit]]


@lru_cache(maxsize=256)
def string_interactions(gene_symbol: str, limit: int = 10) -> list[Interaction]:
    settings = get_settings()
    gene_symbol = gene_symbol.upper().strip()
    logger.debug(
        "api_request service=string method=GET path=/api/json/network species=9606 gene={} limit={}",
        gene_symbol,
        limit,
    )
    try:
        with httpx.Client(timeout=settings.request_timeout_seconds) as client:
            res = client.get(
                "https://string-db.org/api/json/network",
                params={"identifiers": gene_symbol, "species": 9606},
            )
            res.raise_for_status()
            rows = res.json()
    except Exception as exc:
        logger.warning("api_response service=string status=error gene={} err={}", gene_symbol, exc)
        return []

    if not isinstance(rows, list):
        rows = []
    logger.debug("api_response service=string status=ok gene={} edge_rows={}", gene_symbol, len(rows))

    return _dedupe_string_edges(rows, gene_symbol, limit)
