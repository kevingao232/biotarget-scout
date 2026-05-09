from __future__ import annotations

import time
import urllib.error
import ssl
import logging
from Bio import Entrez
from biotarget_scout.core.config import get_settings
from biotarget_scout.models.schemas import PubMedPaper

logger = logging.getLogger(__name__)


def pubmed_search(query: str, max_results: int = 10) -> list[PubMedPaper]:
    settings = get_settings()
    # NCBI asks clients to provide a real contact email for API usage.
    Entrez.email = settings.ncbi_email
    if settings.ncbi_api_key:
        # API key raises the per-second allowance compared with anonymous calls.
        Entrez.api_key = settings.ncbi_api_key

    try:
        # Step 1: search only for PubMed IDs (fast and lightweight).
        with Entrez.esearch(db="pubmed", term=query, retmax=max_results) as handle:
            result = Entrez.read(handle)
            ids = result.get("IdList", [])
    except urllib.error.URLError as exc:
        # Common in corporate/proxied environments: SSL inspection injects a custom cert.
        if isinstance(exc.reason, ssl.SSLCertVerificationError):
            logger.warning(
                "PubMed TLS verification failed during esearch. "
                "Likely missing corporate root CA. Configure SSL_CERT_FILE or install the org CA certificate. "
                "error=%s",
                str(exc),
            )
        else:
            logger.warning("PubMed esearch URL error: %s", str(exc))
        return []
    except Exception:
        logger.exception("PubMed esearch failed unexpectedly for query=%s", query)
        return []

    if not ids:
        return []

    # Basic pacing between calls to reduce burst pressure on NCBI endpoints.
    time.sleep(0.1)
    try:
        # Step 2: fetch full records for the candidate PMID list.
        with Entrez.efetch(db="pubmed", id=",".join(ids), retmode="xml") as handle:
            records = Entrez.read(handle)
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, ssl.SSLCertVerificationError):
            logger.warning(
                "PubMed TLS verification failed during efetch. "
                "Likely missing corporate root CA. Configure SSL_CERT_FILE or install the org CA certificate. "
                "error=%s",
                str(exc),
            )
        else:
            logger.warning("PubMed efetch URL error: %s", str(exc))
        return []
    except Exception:
        logger.exception("PubMed efetch failed unexpectedly for query=%s", query)
        return []

    papers: list[PubMedPaper] = []
    for article in records.get("PubmedArticle", []):
        medline = article.get("MedlineCitation", {})
        pmid = str(medline.get("PMID", ""))
        article_data = medline.get("Article", {})
        title = str(article_data.get("ArticleTitle", ""))
        abstract_items = article_data.get("Abstract", {}).get("AbstractText", [])
        # PubMed often stores abstract sections as a list; join into one searchable string.
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
