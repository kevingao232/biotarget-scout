from __future__ import annotations

import time
from Bio import Entrez
from biotarget_scout.core.config import get_settings
from biotarget_scout.models.schemas import PubMedPaper


def pubmed_search(query: str, max_results: int = 10) -> list[PubMedPaper]:
    settings = get_settings()
    Entrez.email = settings.ncbi_email
    if settings.ncbi_api_key:
        Entrez.api_key = settings.ncbi_api_key

    try:
        with Entrez.esearch(db="pubmed", term=query, retmax=max_results) as handle:
            result = Entrez.read(handle)
            ids = result.get("IdList", [])
    except Exception:
        return []

    if not ids:
        return []

    time.sleep(0.1)
    try:
        with Entrez.efetch(db="pubmed", id=",".join(ids), retmode="xml") as handle:
            records = Entrez.read(handle)
    except Exception:
        return []

    papers: list[PubMedPaper] = []
    for article in records.get("PubmedArticle", []):
        medline = article.get("MedlineCitation", {})
        pmid = str(medline.get("PMID", ""))
        article_data = medline.get("Article", {})
        title = str(article_data.get("ArticleTitle", ""))
        abstract_items = article_data.get("Abstract", {}).get("AbstractText", [])
        abstract = " ".join(str(x) for x in abstract_items) if abstract_items else ""
        year_raw = (
            article_data.get("Journal", {})
            .get("JournalIssue", {})
            .get("PubDate", {})
            .get("Year")
        )
        pub_year = int(year_raw) if isinstance(year_raw, str) and year_raw.isdigit() else None
        authors = []
        for author in article_data.get("AuthorList", []):
            last = author.get("LastName")
            fore = author.get("ForeName")
            name = " ".join([x for x in [fore, last] if x])
            if name:
                authors.append(name)
        papers.append(
            PubMedPaper(
                pmid=pmid,
                title=title,
                abstract=abstract,
                pub_year=pub_year,
                authors=authors,
            )
        )
    return papers
