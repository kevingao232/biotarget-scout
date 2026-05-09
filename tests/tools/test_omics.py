from biotarget_scout.tools import omics


class _Resp:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http")

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
        if isinstance(self.payload, tuple):
            out = self.payload[self.calls]
            self.calls += 1
            return _Resp(out)
        return _Resp(self.payload)


def test_alphafold_check(monkeypatch):
    omics.alphafold_check.cache_clear()
    payload = [{"pdbUrl": "u", "globalMetricValue": 75.3}]
    monkeypatch.setattr(omics.httpx, "Client", lambda **kwargs: _Client(payload))
    result = omics.alphafold_check("P0")
    assert result.available is True
    assert result.pdb_url == "u"


def test_gtex_expression_empty_on_error(monkeypatch):
    omics.gtex_expression.cache_clear()
    monkeypatch.setattr(omics.httpx, "Client", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("x")))
    assert omics.gtex_expression("PCSK9") == {}


def test_gtex_expression_two_hop_lookup(monkeypatch):
    omics.gtex_expression.cache_clear()
    payloads = (
        {"data": [{"gencodeId": "ENSG00000169174.12"}]},
        {
            "data": [
                {"tissueSiteDetailId": "Liver", "median": 30.1},
                {"tissueSiteDetailId": "Artery_Aorta", "median": 5.4},
            ]
        },
    )
    monkeypatch.setattr(omics.httpx, "Client", lambda **kwargs: _Client(payloads))
    result = omics.gtex_expression("PCSK9")
    assert "Liver" in result
    assert result["Liver"] == 30.1
