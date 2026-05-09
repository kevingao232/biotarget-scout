"""Delta upsert only indexes PMIDs not yet in the store."""

from biotarget_scout.models.schemas import PubMedPaper
from biotarget_scout.retrieval.fresh_fetcher import papers_not_in_index, upsert_new_papers_only
from biotarget_scout.retrieval.indexer import LiteratureIndex


def test_papers_not_in_index_filters():
    idx = LiteratureIndex(chroma_collection=_FakeChroma())
    idx.add_papers(
        [PubMedPaper(pmid="1", title="a", abstract="x")],
        chroma_upsert_mode="full",
    )
    batch = [
        PubMedPaper(pmid="1", title="a", abstract="x"),
        PubMedPaper(pmid="2", title="b", abstract="y"),
    ]
    new_only = papers_not_in_index(idx, batch)
    assert len(new_only) == 1
    assert new_only[0].pmid == "2"


def test_upsert_new_papers_only_adds_delta():
    idx = LiteratureIndex(chroma_collection=_FakeChroma())
    idx.add_papers([PubMedPaper(pmid="1", title="a", abstract="x")], chroma_upsert_mode="full")
    n = upsert_new_papers_only(
        idx,
        [
            PubMedPaper(pmid="1", title="a", abstract="x"),
            PubMedPaper(pmid="2", title="b", abstract="y"),
        ],
    )
    assert n == 1
    assert "2" in idx.list_pmids()


class _FakeChroma:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def count(self) -> int:
        return len(self._store)

    def get(self) -> dict:
        return {"ids": list(self._store.keys())}

    def delete(self, ids: list[str] | None = None, where: dict | None = None) -> None:
        if ids:
            for i in ids:
                self._store.pop(i, None)

    def upsert(self, ids: list[str], documents: list[str], metadatas: list[dict] | None = None) -> None:
        for i, d in zip(ids, documents):
            self._store[i] = d

    def query(self, query_texts: list[str], n_results: int) -> dict:
        return {"ids": [list(self._store.keys())[:n_results]]}
