"""Confidence scorer uses structured signals, not narrative text."""

from biotarget_scout.agents.confidence import score_confidence
from biotarget_scout.models.schemas import EvidenceSignals


def test_zero_papers_caps_score():
    s = EvidenceSignals(paper_count=0, has_uniprot_id=False)
    assert score_confidence(s) <= 0.12


def test_rich_signals_increase_score():
    low = EvidenceSignals(paper_count=1, has_uniprot_id=False)
    high = EvidenceSignals(
        paper_count=5,
        has_uniprot_id=True,
        omim_entry_count=2,
        string_edge_count=5,
        has_gtex_data=True,
        alphafold_available=True,
        plddt=85.0,
    )
    assert score_confidence(high) > score_confidence(low)
