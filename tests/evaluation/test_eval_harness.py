"""
Build-plan evaluation harness: eight canonical (gene, disease) pairs.

Fast path (default): mocks ``run_pipeline`` via dependency override and asserts
structural guarantees from the original plan (confidence bands, paper counts).

Real APIs: set ``RUN_E2E=1`` and ``pytest -m e2e`` (slow; needs keys and network).
"""

from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient

from biotarget_scout.api.app import create_app
from biotarget_scout.api.deps import get_run_pipeline
from biotarget_scout.models.schemas import HypothesisReport, PubMedPaper

# Eight canonical targets from the original 7-day build plan (expanded with common drug targets).
EVAL_CASES: list[tuple[str, str, str]] = [
    ("PCSK9", "cardiovascular disease and LDL lowering", "well_known"),
    ("GLP1R", "type 2 diabetes and obesity", "well_known"),
    ("IL6R", "rheumatoid arthritis and inflammation", "well_known"),
    ("LDLR", "familial hypercholesterolemia", "well_known"),
    ("BRCA1", "breast cancer susceptibility", "well_known"),
    ("TP53", "cancer biology and tumor suppression", "well_known"),
    ("APOE", "Alzheimer disease and lipids", "well_known"),
    ("XYZABC123", "fictional disease context for negative control", "unknown_gene"),
]


def _stub_report(gene: str, disease_context: str) -> HypothesisReport:
    if gene.upper() == "XYZABC123":
        return HypothesisReport(
            target_gene=gene,
            disease_context=disease_context,
            evidence_summary="No reliable biomedical hits for this symbol.",
            proposed_experiment="No experiment proposed until a valid human gene symbol is provided.",
            confidence_score=0.0,
            supporting_papers=[],
            caveats=["No data found for unknown gene symbol."],
            data_unavailable=True,
        )
    papers = [
        PubMedPaper(pmid=str(i), title=f"Trial on {gene}", abstract="Abstract " * 20, pub_year=2023)
        for i in range(1, 5)
    ]
    long_exp = (
        f"Intervention study: modulate {gene} in primary cells or organoids relevant to {disease_context[:40]}; "
        f"measure mechanistic and disease-relevant readouts with appropriate controls."
    )
    return HypothesisReport(
        target_gene=gene,
        disease_context=disease_context,
        evidence_summary=f"Stub summary for {gene} with literature and structured legs.",
        proposed_experiment=long_exp,
        confidence_score=0.78,
        supporting_papers=papers,
        caveats=[],
        data_unavailable=False,
    )


@pytest.fixture
def eval_client() -> TestClient:
    async def fake_runner(
        target_gene: str,
        disease_context: str,
        *,
        shared_index=None,
        index_mode=None,
        leg_retries: int = 2,
    ) -> HypothesisReport:
        return _stub_report(target_gene, disease_context)

    app = create_app()
    app.dependency_overrides[get_run_pipeline] = lambda: fake_runner
    return TestClient(app)


@pytest.mark.eval
@pytest.mark.parametrize("gene,disease,kind", EVAL_CASES, ids=[c[0] for c in EVAL_CASES])
def test_eval_report_structure_mocked(eval_client: TestClient, gene: str, disease: str, kind: str) -> None:
    r = eval_client.post(
        "/api/v1/hypothesis",
        json={"target_gene": gene, "disease_context": disease, "leg_retries": 1},
    )
    assert r.status_code == 200
    rep = r.json()
    assert rep["target_gene"] == gene
    assert 0.0 <= rep["confidence_score"] <= 1.0
    assert rep["proposed_experiment"] is not None

    if kind == "unknown_gene":
        assert rep["confidence_score"] == 0.0
        assert rep["data_unavailable"] is True
        assert len(rep.get("caveats", [])) >= 1
    else:
        assert rep["confidence_score"] > 0.7
        assert len(rep.get("supporting_papers", [])) >= 3
        assert len(rep["proposed_experiment"]) > 50


@pytest.mark.eval
def test_eval_analyze_alias_matches_hypothesis(eval_client: TestClient) -> None:
    r = eval_client.post(
        "/api/v1/analyze",
        json={"gene": "PCSK9", "disease_context": "cardiovascular", "leg_retries": 1},
    )
    assert r.status_code == 200
    assert r.json()["target_gene"] == "PCSK9"
    assert r.json()["confidence_score"] > 0.7


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.skipif(os.getenv("RUN_E2E") != "1", reason="Set RUN_E2E=1 to run live pipeline eval")
@pytest.mark.parametrize("gene,disease,kind", [EVAL_CASES[0]], ids=["PCSK9_live"])
def test_eval_one_live_pipeline_smoke(gene: str, disease: str, kind: str) -> None:
    """Single live call (PCSK9); extend locally if you want all eight against real APIs."""
    app = create_app()
    c = TestClient(app)
    r = c.post("/api/v1/analyze", json={"gene": gene, "disease_context": disease, "leg_retries": 1})
    assert r.status_code == 200
    data = r.json()
    assert data["target_gene"] == gene
    assert isinstance(data.get("supporting_papers"), list)
