from biotarget_scout.tools import knowledge


class _Resp:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def json(self):
        return self._payload


class _Client:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, *args, **kwargs):
        if isinstance(self.payload, list):
            out = self.payload[self.calls]
            self.calls += 1
            return _Resp(out)
        return _Resp(self.payload)


def test_uniprot_lookup_ok(monkeypatch):
    knowledge.uniprot_lookup.cache_clear()
    payload = {
        "results": [
            {
                "primaryAccession": "P04114",
                "comments": [{"commentType": "FUNCTION", "texts": [{"value": "f"}]}],
                "keywords": [{"name": "Liver"}],
                "organism": {"scientificName": "Homo sapiens"},
                "sequence": {"length": 692},
                "proteinDescription": {"recommendedName": {"fullName": {"value": "PCSK9"}}},
            }
        ]
    }
    monkeypatch.setattr(knowledge.httpx, "Client", lambda **kwargs: _Client(payload))
    out = knowledge.uniprot_lookup("PCSK9")
    assert out.uniprot_id == "P04114"


def test_string_interactions_error(monkeypatch):
    knowledge.string_interactions.cache_clear()
    def _boom(**kwargs):
        raise RuntimeError("x")
    monkeypatch.setattr(knowledge.httpx, "Client", _boom)
    assert knowledge.string_interactions("PCSK9") == []


def test_omim_lookup_without_key(monkeypatch):
    knowledge.omim_lookup.cache_clear()
    class _S:
        omim_api_key = ""
        request_timeout_seconds = 10
    monkeypatch.setattr(knowledge, "get_settings", lambda: _S())
    assert knowledge.omim_lookup("PCSK9") == []


def test_omim_lookup_with_key(monkeypatch):
    knowledge.omim_lookup.cache_clear()
    class _S:
        omim_api_key = "demo"
        request_timeout_seconds = 10
    payload = {
        "omim": {
            "searchResponse": {
                "entryList": [
                    {
                        "entry": {
                            "mimNumber": 603776,
                            "titles": {"preferredTitle": "PROPROTEIN CONVERTASE SUBTILISIN/KEXIN TYPE 9"},
                            "geneMap": {
                                "phenotypeMapList": [
                                    {"phenotypeMap": {"phenotype": "Hypercholesterolemia, familial, 3"}}
                                ]
                            },
                        }
                    }
                ]
            }
        }
    }
    monkeypatch.setattr(knowledge, "get_settings", lambda: _S())
    monkeypatch.setattr(knowledge.httpx, "Client", lambda **kwargs: _Client(payload))
    out = knowledge.omim_lookup("PCSK9")
    assert len(out) == 1
    assert out[0].mim_number == "603776"
