from __future__ import annotations

from functools import lru_cache
import httpx
from biotarget_scout.core.config import get_settings
from biotarget_scout.models.schemas import AlphaFoldResult
from biotarget_scout.tools.knowledge import uniprot_lookup


@lru_cache(maxsize=256)
def gtex_expression(gene_symbol: str) -> dict[str, float]:
    settings = get_settings()
    gene_symbol = gene_symbol.strip().upper()
    # GTEx query is done in two hops:
    # 1) map gene symbol -> GENCODE ID
    # 2) fetch tissue expression for that GENCODE ID
    try:
        with httpx.Client(timeout=settings.request_timeout_seconds) as client:
            lookup_res = client.get(
                "https://gtexportal.org/api/v2/reference/gene",
                params={"geneId": gene_symbol},
            )
            lookup_res.raise_for_status()
            lookup_payload = lookup_res.json()

            lookup_rows = lookup_payload.get("data", [])
            if not lookup_rows:
                return {}
            gencode_id = lookup_rows[0].get("gencodeId")
            if not gencode_id:
                return {}

            expr_res = client.get(
                "https://gtexportal.org/api/v2/expression/geneExpression",
                params={"gencodeId": gencode_id},
            )
            expr_res.raise_for_status()
            payload = expr_res.json()
    except Exception:
        return {}

    rows = payload.get("data", [])
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
    try:
        with httpx.Client(timeout=settings.request_timeout_seconds) as client:
            res = client.get(f"https://alphafold.ebi.ac.uk/api/prediction/{uniprot_id}")
            if res.status_code != 200:
                return AlphaFoldResult(available=False)
            payload = res.json()
    except Exception:
        return AlphaFoldResult(available=False)

    if not payload:
        return AlphaFoldResult(available=False)
    first = payload[0]
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
