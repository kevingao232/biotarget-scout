from biotarget_scout.tools import ner


def test_extract_entities_graceful_when_model_missing(monkeypatch):
    monkeypatch.setattr(ner, "_load_nlp", lambda: None)
    out = ner.extract_entities("Semaglutide treats type 2 diabetes.")
    assert out.genes == []
    assert out.diseases == []
