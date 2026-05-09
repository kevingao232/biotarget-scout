# BioTarget Scout — Documentation

This folder holds deeper design notes. **Project overview, setup, and the full module map** live in the [root README](../README.md).

## System flow

The end-to-end pipeline (orchestrator, gather/retry, **`EvidenceBundle`**, structured confidence, tracing) is diagrammed in **[`system-flow.md`](system-flow.md)**. That page is the single place we extend when the architecture changes; the root README embeds the same Mermaid for convenience.

## Quick orientation

| Topic | Location |
|--------|----------|
| Mermaid + reading guide | [`system-flow.md`](system-flow.md) |
| Install, env vars, SSL, examples | [../README.md](../README.md) |
| Orchestrator entrypoint | `src/biotarget_scout/agents/orchestrator.py` → **`run_pipeline`** |
| Schemas (`EvidenceBundle`, `HypothesisReport`, …) | `src/biotarget_scout/models/schemas.py` |
| Per-call tracing | `src/biotarget_scout/core/tooling.py` → **`traced_call`** |

## Diagram (copy of canonical flow)

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

## Tests

From the repo root:

```bash
python -m pytest -q
```

See [../README.md](../README.md) for scoped test commands.
