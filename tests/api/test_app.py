"""FastAPI app: health, static root, hypothesis route with dependency override."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from biotarget_scout.api.app import create_app
from biotarget_scout.api.deps import get_run_pipeline
from biotarget_scout.models.schemas import HypothesisReport


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_health(client: TestClient) -> None:
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "version" in data and isinstance(data["version"], str)


def test_root_serves_ui(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "BioTarget Scout" in r.text


def test_hypothesis_with_override(client: TestClient) -> None:
    async def fake_run(
        target_gene: str,
        disease_context: str,
        *,
        shared_index=None,
        index_mode=None,
        leg_retries: int = 2,
    ) -> HypothesisReport:
        return HypothesisReport(
            target_gene=target_gene,
            disease_context=disease_context,
            evidence_summary="stub",
            proposed_experiment="stub experiment",
            confidence_score=0.42,
        )

    app = create_app()
    app.dependency_overrides[get_run_pipeline] = lambda: fake_run
    c = TestClient(app)
    r = c.post(
        "/api/v1/hypothesis",
        json={
            "target_gene": "TEST1",
            "disease_context": "test disease",
            "index_mode": "ephemeral_per_request",
            "leg_retries": 1,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["target_gene"] == "TEST1"
    assert data["confidence_score"] == 0.42


def test_hypothesis_natural_query_resolves_gene(client: TestClient) -> None:
    async def fake_run(
        target_gene: str,
        disease_context: str,
        *,
        shared_index=None,
        index_mode=None,
        leg_retries: int = 2,
    ) -> HypothesisReport:
        return HypothesisReport(
            target_gene=target_gene,
            disease_context=disease_context,
            evidence_summary="stub",
            proposed_experiment="stub experiment",
            confidence_score=0.1,
        )

    app = create_app()
    app.dependency_overrides[get_run_pipeline] = lambda: fake_run
    c = TestClient(app)
    r = c.post(
        "/api/v1/hypothesis",
        json={
            "query": "Explain BRCA1 in breast cancer risk.",
            "leg_retries": 1,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["target_gene"] == "BRCA1"
    assert "breast cancer" in data["disease_context"].lower()


def test_hypothesis_rejects_mixed_input_modes(client: TestClient) -> None:
    r = client.post(
        "/api/v1/hypothesis",
        json={
            "query": "PCSK9 and lipids",
            "target_gene": "PCSK9",
            "disease_context": "lipids",
        },
    )
    assert r.status_code == 422


def test_hypothesis_rejects_empty_payload(client: TestClient) -> None:
    r = client.post("/api/v1/hypothesis", json={"leg_retries": 1})
    assert r.status_code == 422
