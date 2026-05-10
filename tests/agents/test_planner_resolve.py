"""resolve_pipeline_inputs: NER-first gene, fallback caps token, full text as context."""

from __future__ import annotations

import pytest

from biotarget_scout.agents import planner
from biotarget_scout.models.schemas import EntityResult


def test_resolve_uses_ner_gene(monkeypatch):
    def fake_ner(_: str) -> EntityResult:
        return EntityResult(genes=["PCSK9"], diseases=["heart disease"])

    monkeypatch.setattr(planner, "extract_entities", fake_ner)
    g, ctx = planner.resolve_pipeline_inputs("Tell me about PCSK9")
    assert g == "PCSK9"
    assert "Tell me about PCSK9" in ctx


def test_resolve_caps_fallback_when_no_ner_gene(monkeypatch):
    monkeypatch.setattr(planner, "extract_entities", lambda _: EntityResult())
    g, ctx = planner.resolve_pipeline_inputs("What is TP53 doing in cancer pathways?")
    assert g == "TP53"
    assert ctx.startswith("What is TP53")


def test_resolve_empty_raises():
    with pytest.raises(ValueError, match="empty"):
        planner.resolve_pipeline_inputs("   ")


def test_resolve_no_gene_raises(monkeypatch):
    monkeypatch.setattr(planner, "extract_entities", lambda _: EntityResult())
    with pytest.raises(ValueError, match="gene symbol"):
        planner.resolve_pipeline_inputs("What is cardiovascular disease?")
