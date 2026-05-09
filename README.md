# BioTarget Scout

BioTarget Scout is an educational multi-agent biomedical discovery project for analyzing target genes and generating therapeutic hypotheses.

Current focus is foundational tooling and retrieval:
- Day 1: project scaffold, config/logging, PubMed retrieval.
- Day 2: UniProt/OMIM (knowledge) and GTEx/AlphaFold (omics) tools.
- Retrieval: local hybrid search over indexed literature (BM25 + vector + RRF).

## Why This Project Exists

Interview framing:
- Demonstrate agentic architecture with reliable tool integration.
- Combine unstructured literature + structured biomedical databases.
- Show robust engineering practices: typed schemas, graceful failures, tests.

## Concepts (Plain English)

- **PubMed**: literature source for papers/abstracts.
- **UniProt**: curated protein knowledge (function, sequence metadata).
- **OMIM**: gene-disease genetics catalog (requires API key for full access).
- **GTEx**: tissue expression atlas for genes.
- **AlphaFold**: predicted protein structure availability.
- **Hybrid retrieval**: combine lexical BM25 and semantic vector search.
- **RRF (Reciprocal Rank Fusion)**: merges multiple ranked lists without score calibration.

## Implemented Code Structure

```text
biotarget-scout/
  src/biotarget_scout/
    core/
      config.py
      logging.py
    models/
      schemas.py
    tools/
      pubmed.py
      knowledge.py
      omics.py
      ner.py
    retrieval/
      __init__.py
      indexer.py
      hybrid.py
  tests/
    test_smoke.py
    tools/
      test_pubmed.py
      test_knowledge.py
      test_omics.py
      test_ner.py
    retrieval/
      test_hybrid.py
  requirements.txt
  .env.example
```

## What Each Implemented Module Does

### `src/biotarget_scout/core/config.py`
- Centralized environment-backed settings (`NCBI_API_KEY`, `OMIM_API_KEY`, timeout, etc.).
- Keeps tool code cleaner and easier to test.

### `src/biotarget_scout/core/logging.py`
- Structured logging setup via Loguru.
- Used to make external API behavior observable.

### `src/biotarget_scout/models/schemas.py`
- Typed Pydantic contracts for all tool outputs.
- Key models currently used:
  - `PubMedPaper`
  - `UniprotResult`
  - `OmimEntry`
  - `Interaction`
  - `AlphaFoldResult`

### `src/biotarget_scout/tools/pubmed.py`
- Fetches papers using Entrez `esearch` (PMIDs) then `efetch` (record details).
- Returns `list[PubMedPaper]`.
- Includes SSL/TLS-aware warning messages for corporate proxy certificate issues.

### `src/biotarget_scout/tools/knowledge.py`
- `uniprot_lookup(gene_symbol)` -> `UniprotResult`
- `omim_lookup(gene_symbol)` -> `list[OmimEntry]`
- `string_interactions(gene_symbol)` -> `list[Interaction]`
- Uses caching and graceful fallbacks to avoid pipeline crashes.

### `src/biotarget_scout/tools/omics.py`
- `gtex_expression(gene_symbol)` -> top tissue expression map.
- `alphafold_check(uniprot_id)` -> structure availability details.
- `omics_snapshot(gene_symbol)` combines expression + structure lookup.

### `src/biotarget_scout/retrieval/indexer.py`
- `LiteratureIndex` stores and searches local indexed corpus:
  - Chroma vector collection
  - BM25 lexical corpus
- Supports add/search/clear/get-paper operations.

### `src/biotarget_scout/retrieval/hybrid.py`
- `reciprocal_rank_fusion(...)`
- `retrieve(index, query, ...)` for hybrid retrieval workflow.

## Retrieval Workflow (What Happens)

1. Collect papers (e.g., PubMed results).
2. Add papers to `LiteratureIndex`.
3. Query BM25 and vector store in parallel.
4. Fuse ranked PMIDs with RRF.
5. Return final ordered `PubMedPaper` results.

## Environment Setup

1. Create virtual environment and activate it.
2. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and fill values you need.
4. Ensure required API keys are set for relevant tools:
   - `NCBI_EMAIL` (required for Entrez etiquette)
   - `NCBI_API_KEY` (optional but recommended)
   - `OMIM_API_KEY` (needed for OMIM results)

## SSL Certificate Note (Common on Windows/Corporate Networks)

If PubMed queries return empty because of TLS verification failures, set:

```powershell
$env:SSL_CERT_FILE="C:\path\to\cacert.pem"
```

To persist across new shells:

```powershell
setx SSL_CERT_FILE "C:\path\to\cacert.pem"
```

## Quick Usage Examples

### 1) PubMed search

```python
from biotarget_scout.tools.pubmed import pubmed_search
papers = pubmed_search("PCSK9 cardiovascular", max_results=5)
print(len(papers))
```

### 2) Build local index and run hybrid retrieval

```python
from biotarget_scout.retrieval import LiteratureIndex, retrieve
from biotarget_scout.tools.pubmed import pubmed_search

papers = pubmed_search("PCSK9 cardiovascular", max_results=50)
index = LiteratureIndex(persist_directory=".chroma_data")
index.add_papers(papers)

hits = retrieve(index, "LDL lowering PCSK9 mechanism", top_k=10)
print([p.pmid for p in hits])
```

## Tests

Run all tests:

```bash
python -m pytest -q
```

Run retrieval tests only:

```bash
python -m pytest tests/retrieval/test_hybrid.py -q
```

## Current Status

- Completed:
  - scaffold/config/logging/schemas
  - PubMed tool
  - Day 2 knowledge + omics tools
  - hybrid retrieval over indexed corpus
- Next:
  - literature agent node over retrieval
  - orchestrator and structured `HypothesisReport` synthesis
