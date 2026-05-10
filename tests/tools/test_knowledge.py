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


def test_string_interactions_dedupes_partner_max_score(monkeypatch):
    knowledge.string_interactions.cache_clear()
    rows = [
        {"preferredName_A": "PCSK9", "preferredName_B": "APOB", "score": 0.5},
        {"preferredName_A": "PCSK9", "preferredName_B": "APOB", "score": 0.99},
        {"preferredName_A": "PCSK9", "preferredName_B": "GOLPH3", "score": 0.7},
    ]

    class _StringClient:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, *a, **k):
            return _Resp(rows)

    monkeypatch.setattr(knowledge.httpx, "Client", lambda **kwargs: _StringClient())
    out = knowledge.string_interactions("PCSK9", limit=10)
    by_partner = {i.partner.upper(): i.score for i in out}
    assert by_partner["APOB"] == 0.99
    assert len(out) == 2


def test_string_interactions_drop_immunoglobulin_variable_genes(monkeypatch):
    knowledge.string_interactions.cache_clear()
    rows = [
        {"preferredName_A": "PCSK9", "preferredName_B": "APOB", "score": 0.9},
        {"preferredName_A": "PCSK9", "preferredName_B": "IGHV3-16", "score": 0.95},
        {"preferredName_A": "PCSK9", "preferredName_B": "IGKV1-33", "score": 0.94},
    ]

    class _StringClient:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, *a, **k):
            return _Resp(rows)

    monkeypatch.setattr(knowledge.httpx, "Client", lambda **kwargs: _StringClient())
    out = knowledge.string_interactions("PCSK9", limit=10)
    partners = {i.partner.upper() for i in out}
    assert "APOB" in partners
    assert "IGHV3-16" not in partners
    assert "IGKV1-33" not in partners


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

    class _OmimClient:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, **kwargs):
            if "/api/entry/search" in url:
                return _Resp(payload)
            if "/api/geneMap/search" in url:
                return _Resp({"omim": {"listResponse": {"geneMapList": []}}})
            return _Resp({"omim": {"geneMapList": []}})

    monkeypatch.setattr(knowledge, "get_settings", lambda: _S())
    monkeypatch.setattr(knowledge.httpx, "Client", lambda **kwargs: _OmimClient())
    out = knowledge.omim_lookup("PCSK9")
    assert len(out) == 1
    assert out[0].mim_number == "603776"


def test_omim_gene_map_parsed_when_present(monkeypatch):
    knowledge.omim_lookup.cache_clear()
    class _S:
        omim_api_key = "demo"
        request_timeout_seconds = 10

    gm = {
        "omim": {
            "geneMapList": [
                {
                    "geneMap": {
                        "mimNumber": 607786,
                        "geneSymbol": "PCSK9",
                        "titles": {"preferredTitle": "PCSK9 GENE"},
                        "phenotypeMapList": [{"phenotypeMap": {"phenotype": "Hypercholesterolemia"}}],
                    }
                }
            ]
        }
    }

    class _GmOnly:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, **kwargs):
            assert "geneMap" in url
            return _Resp(gm)

    monkeypatch.setattr(knowledge, "get_settings", lambda: _S())
    monkeypatch.setattr(knowledge.httpx, "Client", lambda **kwargs: _GmOnly())
    out = knowledge.omim_lookup("PCSK9")
    assert len(out) == 1
    assert out[0].mim_number == "607786"
