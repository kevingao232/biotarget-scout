from __future__ import annotations

from functools import lru_cache

import httpx
from loguru import logger

from biotarget_scout.core.config import get_settings
from biotarget_scout.models.schemas import AlphaFoldResult
from biotarget_scout.tools.knowledge import uniprot_lookup

_GTEX_DATASET = "gtex_v8"


def _gtex_resolve_gencode_id(client: httpx.Client, gene_symbol: str, timeout: float) -> str | None:
    """Resolve HGNC symbol (or bare ENSG) to GTEx ``gencodeId`` (versioned)."""
    sym = gene_symbol.strip().upper()
    res = client.get(
        "https://gtexportal.org/api/v2/reference/gene",
        params={"geneId": sym},
        timeout=timeout,
    )
    if res.status_code == 200:
        rows = res.json().get("data") or []
        if rows and rows[0].get("gencodeId"):
            return str(rows[0]["gencodeId"])
    uni = uniprot_lookup(sym)
    if uni.ensembl_gene_id:
        res = client.get(
            "https://gtexportal.org/api/v2/reference/gene",
            params={"geneId": uni.ensembl_gene_id},
            timeout=timeout,
        )
        if res.status_code == 200:
            rows = res.json().get("data") or []
            if rows and rows[0].get("gencodeId"):
                return str(rows[0]["gencodeId"])
    return None


@lru_cache(maxsize=256)
def gtex_expression(gene_symbol: str) -> dict[str, float]:
    settings = get_settings()
    gene_symbol = gene_symbol.strip().upper()
    logger.debug(
        "api_request service=gtex step=resolve_gencode method=GET host=gtexportal.org path=/api/v2/reference/gene geneId={}",
        gene_symbol,
    )
    try:
        with httpx.Client(timeout=settings.request_timeout_seconds) as client:
            gencode_id = _gtex_resolve_gencode_id(client, gene_symbol, settings.request_timeout_seconds)
            if not gencode_id:
                logger.warning(
                    "OMICS: GTEx could not resolve a gencode id for {} (check symbol / UniProt Ensembl xref).",
                    gene_symbol,
                )
                return {}

            logger.debug(
                "api_request service=gtex step=medianGeneExpression method=GET gencodeId={} datasetId={}",
                gencode_id,
                _GTEX_DATASET,
            )
            expr_res = client.get(
                "https://gtexportal.org/api/v2/expression/medianGeneExpression",
                params={"gencodeId": gencode_id, "datasetId": _GTEX_DATASET},
            )
            expr_res.raise_for_status()
            payload = expr_res.json()
    except Exception as exc:
        logger.warning("OMICS: GTEx request failed for {} — {}.", gene_symbol, str(exc)[:160])
        return {}

    rows = payload.get("data", [])
    logger.debug(
        "api_response service=gtex status=ok gene={} median_tissue_rows={}",
        gene_symbol,
        len(rows),
    )

    tissue_to_expr: dict[str, float] = {}
    for row in rows:
        tissue = row.get("tissueSiteDetailId") or row.get("tissueSiteDetail")
        value = row.get("median")
        if tissue and value is not None:
            tissue_to_expr[str(tissue)] = float(value)

    return dict(sorted(tissue_to_expr.items(), key=lambda kv: kv[1], reverse=True)[:10])


@lru_cache(maxsize=256)
def alphafold_check(uniprot_id: str) -> AlphaFoldResult:
    settings = get_settings()
    uniprot_id = uniprot_id.strip().upper()
    url = f"https://alphafold.ebi.ac.uk/api/prediction/{uniprot_id}"
    logger.debug(
        "api_request service=alphafold method=GET host=alphafold.ebi.ac.uk path=/api/prediction/ accession={}",
        uniprot_id,
    )
    try:
        with httpx.Client(timeout=settings.request_timeout_seconds) as client:
            res = client.get(url)
            if res.status_code != 200:
                logger.debug(
                    "api_response service=alphafold status=http_{} accession={}",
                    res.status_code,
                    uniprot_id,
                )
                return AlphaFoldResult(available=False)
            payload = res.json()
    except Exception as exc:
        logger.warning("OMICS: AlphaFold request failed for {} — {}.", uniprot_id, str(exc)[:160])
        return AlphaFoldResult(available=False)

    if not payload:
        logger.debug("api_response service=alphafold status=empty_payload accession={}", uniprot_id)
        return AlphaFoldResult(available=False)
    first = payload[0]
    logger.debug("api_response service=alphafold status=ok accession={} available=true", uniprot_id)
    return AlphaFoldResult(
        available=True,
        pdb_url=first.get("pdbUrl"),
        plddt_score=float(first.get("globalMetricValue")) if first.get("globalMetricValue") is not None else None,
    )


def omics_snapshot(gene_symbol: str) -> tuple[dict[str, float], AlphaFoldResult]:
    expr = gtex_expression(gene_symbol)
    uni = uniprot_lookup(gene_symbol)
    if not uni.uniprot_id:
        return expr, AlphaFoldResult(available=False)
    return expr, alphafold_check(uni.uniprot_id)
