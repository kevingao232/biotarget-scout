"""Hypothesis pipeline HTTP mapping."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field, model_validator

from biotarget_scout.agents.planner import resolve_pipeline_inputs
from biotarget_scout.api.deps import get_run_pipeline
from biotarget_scout.core.human_log import line
from biotarget_scout.models.schemas import HypothesisReport
from biotarget_scout.retrieval.indexer import IndexMode

router = APIRouter(tags=["hypothesis"])


class HypothesisAnalyzeRequest(BaseModel):
    """
    Send either a natural-language `query` **or** both structured fields.

    The web UI uses `query` only; structured fields remain for scripts and tests.
    """

    query: str | None = Field(
        default=None,
        max_length=4000,
        description="Natural-language question (e.g. role of PCSK9 in heart disease).",
    )
    target_gene: str | None = Field(default=None, max_length=64)
    disease_context: str | None = Field(default=None, max_length=2000)
    index_mode: IndexMode = IndexMode.ephemeral_per_request
    leg_retries: int = Field(2, ge=0, le=5)

    @model_validator(mode="after")
    def require_one_input_style(self) -> HypothesisAnalyzeRequest:
        has_nl = bool(self.query and self.query.strip())
        has_struct = bool(
            (self.target_gene and self.target_gene.strip())
            and (self.disease_context and self.disease_context.strip())
        )
        if has_nl and has_struct:
            raise ValueError("Send either `query` or both `target_gene` and `disease_context`, not both.")
        if not has_nl and not has_struct:
            raise ValueError("Send a natural-language `query`, or both `target_gene` and `disease_context`.")
        return self


class LegacyAnalyzeRequest(BaseModel):
    """Build-plan shape: explicit gene + disease (maps to the same pipeline as structured ``/hypothesis``)."""

    gene: str = Field(..., max_length=64, description="HGNC-style gene symbol.")
    disease_context: str = Field(..., max_length=2000)
    index_mode: IndexMode = IndexMode.ephemeral_per_request
    leg_retries: int = Field(2, ge=0, le=5)


async def _run_pipeline_http(
    *,
    run_id: str,
    target_gene: str,
    disease_context: str,
    index_mode: IndexMode,
    leg_retries: int,
    runner: Callable[..., Awaitable[HypothesisReport]],
) -> HypothesisReport:
    line(
        "HTTP",
        f"run {run_id}: starting pipeline (index_mode={index_mode.value}, leg_retries={leg_retries}).",
    )
    t0 = time.perf_counter()
    try:
        report = await runner(
            target_gene,
            disease_context,
            shared_index=None,
            index_mode=index_mode,
            leg_retries=leg_retries,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        line(
            "HTTP",
            f"run {run_id}: finished in {elapsed_ms:.0f} ms — confidence {report.confidence_score:.2f}, "
            f"data_unavailable={report.data_unavailable}.",
        )
        return report
    except ValueError as e:
        logger.bind(run_id=run_id).warning("HTTP run {}: validation error — {}.", run_id, str(e))
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as exc:
        logger.exception(
            "HTTP run {}: pipeline error after {:.0f} ms.",
            run_id,
            (time.perf_counter() - t0) * 1000.0,
        )
        raise HTTPException(status_code=500, detail="Pipeline failed; see server logs.") from exc


@router.post("/hypothesis", response_model=HypothesisReport)
async def analyze_hypothesis(
    body: HypothesisAnalyzeRequest,
    runner: Annotated[Callable[..., Awaitable[HypothesisReport]], Depends(get_run_pipeline)],
) -> HypothesisReport:
    run_id = str(uuid.uuid4())

    if body.query and body.query.strip():
        target_gene, disease_context = resolve_pipeline_inputs(body.query)
        line(
            "HTTP",
            f"run {run_id}: resolved natural-language query → gene {target_gene!r}, "
            f"context length {len(disease_context)} chars.",
        )
    else:
        assert body.target_gene is not None and body.disease_context is not None
        target_gene = body.target_gene.strip()
        disease_context = body.disease_context.strip()
        line(
            "HTTP",
            f"run {run_id}: structured body — gene {target_gene!r}, context length {len(disease_context)} chars.",
        )

    return await _run_pipeline_http(
        run_id=run_id,
        target_gene=target_gene,
        disease_context=disease_context,
        index_mode=body.index_mode,
        leg_retries=body.leg_retries,
        runner=runner,
    )


@router.post("/analyze", response_model=HypothesisReport)
async def analyze_legacy_body(
    body: LegacyAnalyzeRequest,
    runner: Annotated[Callable[..., Awaitable[HypothesisReport]], Depends(get_run_pipeline)],
) -> HypothesisReport:
    run_id = str(uuid.uuid4())
    target_gene = body.gene.strip()
    disease_context = body.disease_context.strip()
    line(
        "HTTP",
        f"run {run_id}: POST /analyze — gene {target_gene!r}, context length {len(disease_context)} chars.",
    )
    return await _run_pipeline_http(
        run_id=run_id,
        target_gene=target_gene,
        disease_context=disease_context,
        index_mode=body.index_mode,
        leg_retries=body.leg_retries,
        runner=runner,
    )
