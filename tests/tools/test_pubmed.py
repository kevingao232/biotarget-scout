from biotarget_scout.tools import pubmed


class _Handle:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_pubmed_search_returns_typed_data(monkeypatch):
    monkeypatch.setattr(pubmed.Entrez, "esearch", lambda **kwargs: _Handle())
    monkeypatch.setattr(pubmed.Entrez, "efetch", lambda **kwargs: _Handle())
    payloads = [
        {"IdList": ["1"]},
        {
            "PubmedArticle": [
                {
                    "MedlineCitation": {
                        "PMID": "1",
                        "Article": {
                            "ArticleTitle": "T",
                            "Abstract": {"AbstractText": ["A"]},
                            "Journal": {"JournalIssue": {"PubDate": {"Year": "2024"}}},
                            "AuthorList": [{"ForeName": "A", "LastName": "B"}],
                        },
                    }
                }
            ]
        },
    ]
    monkeypatch.setattr(pubmed.Entrez, "read", lambda h: payloads.pop(0))
    papers = pubmed.pubmed_search("pcsk9", 1)
    assert len(papers) == 1
    assert papers[0].abstract == "A"


def test_pubmed_search_handles_error(monkeypatch):
    monkeypatch.setattr(pubmed.Entrez, "esearch", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    papers = pubmed.pubmed_search("x", 1)
    assert papers == []
