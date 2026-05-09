"""Orchestrator: partial legs, all-empty unknown gene, and confidence assembly."""

from __future__ import annotations

import asyncio

import pytest

from biotarget_scout.agents import orchestrator as orch
from biotarget_scout.models.schemas import KGResult, LegStatus, LiteratureResult, OmicsResult, PubMedPaper


@pytest.mark.asyncio
async def test_pipeline_partial_one_literature_leg_ok(monkeypatch):
    async def fake_lit(*_a, **_k):
        return (
            LiteratureResult(
                papers=[PubMedPaper(pmid="1", title="t", abstract="PCSK9 lipid")],
                reasoning_trace=["ok"],
            ),
            LegStatus.ok,
            "",
            3,
        )

    async def fake_kg(*_a, **_k):
        return None, LegStatus.error, "uni_down"

    async def fake_om(*_a, **_k):
        return OmicsResult(), LegStatus.empty, "no_tissue"

    monkeypatch.setattr(orch, "run_literature", fake_lit)
    monkeypatch.setattr(orch, "run_kg", fake_kg)
    monkeypatch.setattr(orch, "run_omics", fake_om)

    report = await orch.run_pipeline("PCSK9", "cardiovascular", leg_retries=1)
    assert len(report.supporting_papers) == 1
    assert report.confidence_score > 0.0
    assert not report.data_unavailable
    assert any("Partial evidence" in c or "errors" in c for c in report.caveats)


@pytest.mark.asyncio
async def test_pipeline_all_empty_data_unavailable(monkeypatch):
    async def fake_lit(*_a, **_k):
        return LiteratureResult(), LegStatus.empty, "none", 0

    async def fake_kg(*_a, **_k):
        return KGResult(), LegStatus.empty, "none"

    async def fake_om(*_a, **_k):
        return OmicsResult(), LegStatus.empty, "none"

    monkeypatch.setattr(orch, "run_literature", fake_lit)
    monkeypatch.setattr(orch, "run_kg", fake_kg)
    monkeypatch.setattr(orch, "run_omics", fake_om)

    report = await orch.run_pipeline("XYZABC123", "unknown disease", leg_retries=1)
    assert report.confidence_score == 0.0
    assert report.data_unavailable


def test_pipeline_runs_via_asyncio_run(monkeypatch):
    """Smoke: asyncio.run works without pytest-asyncio."""

    async def fake_lit(*_a, **_k):
        return LiteratureResult(), LegStatus.empty, "none", 0

    async def fake_kg(*_a, **_k):
        return KGResult(), LegStatus.empty, "none"

    async def fake_om(*_a, **_k):
        return OmicsResult(), LegStatus.empty, "none"

    monkeypatch.setattr(orch, "run_literature", fake_lit)
    monkeypatch.setattr(orch, "run_kg", fake_kg)
    monkeypatch.setattr(orch, "run_omics", fake_om)

    report = asyncio.run(orch.run_pipeline("XYZABC123", "x", leg_retries=1))
    assert report.data_unavailable
