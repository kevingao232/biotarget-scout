# BioTarget Scout System Flow

Target architecture: orchestrator-owned `asyncio.gather`, per-leg retries, explicit tool failures surfaced in `EvidenceBundle`, hybrid literature **IndexMode**, query NER before dispatch, parallel narrative synthesis + structured confidence scoring, and per-tool tracing.

Canonical diagram (also embedded in the [root README](../README.md)):

```mermaid
flowchart TB
  subgraph entry["1. Entry and planning"]
    U[("Gene + disease")]
    U --> API["FastAPI / CLI / script (optional)"]
    API --> RP["run_pipeline (async orchestrator)"]
    RP --> PL["build_structured_query"]
    PL --> NER["NER on raw query → EntityResult"]
    NER --> SQ["StructuredQuery + pubmed_query_string"]
  end

  subgraph legs["2. Parallel specialists — asyncio.gather"]
    SQ --> GATHER{{"asyncio.gather"}}
    GATHER --> LIT["LiteratureAgent"]
    GATHER --> KG["KGAgent"]
    GATHER --> OM["OmicsAgent"]
  end

  subgraph litpath["Literature path"]
    LIT --> PM["pubmed_search (traced)"]
    PM --> MODE{{"IndexMode"}}
    MODE -->|"ephemeral"| EPH["New LiteratureIndex per request"]
    MODE -->|"persistent + delta"| DELTA["shared_index + upsert_new_papers_only (traced)"]
    EPH --> IDX["index papers (Chroma + BM25)"]
    DELTA --> IDX
    IDX --> HYB["hybrid retrieve: BM25 + vector, RRF (traced)"]
    HYB --> NERD["NER merge on retrieved text"]
    NERD --> LR["LiteratureResult + LegStatus"]
  end

  subgraph kgpath["Knowledge graph path"]
    KG --> UP["UniProt (traced)"]
    KG --> OMIM["OMIM (traced)"]
    KG --> ST["STRING (traced)"]
    UP --> KR["KGResult + LegStatus"]
    OMIM --> KR
    ST --> KR
  end

  subgraph ompath["Omics path"]
    OM --> GT["GTEx (traced)"]
    OM --> AF["AlphaFold (traced)"]
    GT --> OR["OmicsResult + LegStatus"]
    AF --> OR
  end

  subgraph merge["3. Merge, retry, bundle"]
    LR --> FIN["finalize_leg: retry if LegStatus.error"]
    KR --> FIN
    OR --> FIN
    FIN --> EB["EvidenceBundle (+ partial, AgentFailure list)"]
  end

  subgraph out["4. Narrative + confidence (both read bundle)"]
    EB --> SYN["synthesize_narrative (deterministic draft)"]
    EB --> SIG["bundle_to_signals → EvidenceSignals"]
    SIG --> SC["score_confidence (structured only)"]
    SYN --> ASM["assemble_report"]
    SC --> ASM
    ASM --> HR["HypothesisReport (caveats, data_unavailable)"]
  end

  PM -.->|"exception / empty"| EB
  UP -.->|"failure"| EB
  OMIM -.->|"failure"| EB
  ST -.->|"failure"| EB
  GT -.->|"failure"| EB
  AF -.->|"failure"| EB
  HYB -.->|"failure"| EB
```

## Reading The Diagram

- **Orchestrator** is implemented as **`run_pipeline`** in Python (`asyncio`), not a LangGraph graph yet. LangGraph remains in dependencies for future graph-based composition or LangSmith callbacks.
- **`asyncio.gather`** launches all three legs concurrently; **`finalize_leg`** re-runs only legs that returned `LegStatus.error` (bounded retries).
- **Planner** runs **query NER first**; entities are merged again after literature retrieval from document text.
- **IndexMode**: *ephemeral* builds a fresh in-memory index per request; *persistent_with_delta* reuses `shared_index` and upserts only PMIDs not yet stored (`fresh_fetcher`).
- **Tool failures** do not bypass the merge: they show up as `LegStatus.error`, optional `AgentFailure` rows, and a **partial** `EvidenceBundle`. **ReportAssembler** still runs; it may set **`data_unavailable`** and zero confidence when structured evidence is insufficient.
- **ConfidenceScorer** uses **`EvidenceSignals` only** (counts, UniProt id, OMIM hits, STRING edges, GTEx, AlphaFold pLDDT, error/partial flags)—not LLM prose.
- **Per-tool tracing**: `traced_call` in `core/tooling.py` logs latency and ok/error for PubMed, indexing, hybrid retrieve, and each database tool.
- **Orchestration logs**: `run_pipeline` in `agents/orchestrator.py` emits **phase** lines (`start`, `structured_query`, `gather_begin` / `gather_done`, `finalize` / `after_retry`, `merged` **evidence_bundle**, `scored`, `narrative_draft`, `complete`) so you can see how each leg contributes before the report is assembled.
- **Outbound API logs**: `tools/pubmed.py`, `knowledge.py`, and `omics.py` log **`api_request`** / **`api_response`** for NCBI Entrez (PubMed), UniProt REST, OMIM (gene only—no API key in logs), STRING, GTEx, and AlphaFold so slow “hanging” UIs correlate with a specific network hop in the terminal.
- **HTTP + favicon**: FastAPI startup calls `configure_logging()` (Loguru). `GET /favicon.ico` returns **204** so browsers do not spam 404 while the long-running **`POST /api/v1/hypothesis`** is in flight.
