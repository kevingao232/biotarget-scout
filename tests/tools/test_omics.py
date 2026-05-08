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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, *args, **kwargs):
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
