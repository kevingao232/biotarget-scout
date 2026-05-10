from __future__ import annotations

import time
import urllib.error
import ssl
from Bio import Entrez
from loguru import logger

from biotarget_scout.core.config import get_settings
from biotarget_scout.models.schemas import PubMedPaper


def _trunc(q: str, n: int = 400) -> str:
    q = q or ""
    return q if len(q) <= n else f"{q[: n - 3]}..."


def pubmed_search(query: str, max_results: int = 10) -> list[PubMedPaper]:
    settings = get_settings()
    Entrez.email = settings.ncbi_email
    if settings.ncbi_api_key:
        Entrez.api_key = settings.ncbi_api_key

    logger.debug(
        "api_request service=pubmed step=esearch db=pubmed retmax={} term={}",
        max_results,
        _trunc(query),
    )

    try:
        with Entrez.esearch(db="pubmed", term=query, retmax=max_results) as handle:
            result = Entrez.read(handle)
            ids = result.get("IdList", [])
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, ssl.SSLCertVerificationError):
            logger.warning(
                "LITERATURE: PubMed esearch hit an SSL problem (often a corporate proxy). Check SSL_CERT_FILE. ({})",
                str(exc)[:200],
            )
        else:
            logger.warning("LITERATURE: PubMed esearch network error. ({})", str(exc)[:200])
        return []
    except Exception:
        logger.exception("LITERATURE: PubMed esearch failed for query={}", _trunc(query, 120))
        return []

    logger.debug(
        "api_response service=pubmed step=esearch status=ok id_count={} sample_ids={}",
        len(ids),
        ids[:5],
    )

    if not ids:
        logger.warning("LITERATURE: PubMed returned no article IDs for this search (empty result).")
        return []

    time.sleep(0.1)
    id_param = ",".join(ids)
    logger.debug(
        "api_request service=pubmed step=efetch db=pubmed retmode=xml id_count={}",
        len(ids),
    )

    try:
        with Entrez.efetch(db="pubmed", id=id_param, retmode="xml") as handle:
            records = Entrez.read(handle)
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, ssl.SSLCertVerificationError):
            logger.warning("LITERATURE: PubMed efetch SSL error. ({})", str(exc)[:200])
        else:
            logger.warning("LITERATURE: PubMed efetch network error. ({})", str(exc)[:200])
        return []
    except Exception:
        logger.exception("LITERATURE: PubMed efetch failed.")
        return []

    raw_articles = records.get("PubmedArticle", [])
    if isinstance(raw_articles, dict):
        articles: list = [raw_articles]
    elif isinstance(raw_articles, list):
        articles = raw_articles
    else:
        articles = []
    logger.debug("api_response service=pubmed step=efetch status=ok article_nodes={}", len(articles))

    papers: list[PubMedPaper] = []
    for article in articles:
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
    logger.debug("api_response service=pubmed step=parse status=ok papers_built={}", len(papers))
    return papers
