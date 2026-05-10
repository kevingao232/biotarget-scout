# Frontend ↔ FastAPI architecture

## Layers

| Layer | Responsibility | Location |
|--------|----------------|----------|
| **Web UI** | HTML/CSS/JS only; calls JSON HTTP API; no business logic | `web/` |
| **HTTP API** | Request validation, status codes, maps to orchestrator | `src/biotarget_scout/api/` |
| **Domain** | `run_pipeline`, agents, tools, retrieval | `src/biotarget_scout/` (existing) |

The API package **does not** embed retrieval or PubMed; it only invokes `run_pipeline` and returns `HypothesisReport` as JSON.

## URL layout

| Path | Purpose |
|------|---------|
| `GET /` | Test UI (`index.html`) |
| `GET /static/*` | JS/CSS for the UI |
| `GET /api/v1/health` | Liveness + **`version`** (package version string) |
| `POST /api/v1/hypothesis` | Body: **`query`** (natural language, preferred for the test UI) **or** `target_gene` + `disease_context`; optional `index_mode`, `leg_retries` → full pipeline |
| `POST /api/v1/analyze` | Same pipeline as structured hypothesis; body **`gene`** + **`disease_context`** (build-plan / curl-friendly alias) |

The server calls `resolve_pipeline_inputs(query)` to infer a **gene symbol** (spaCy NER when it tags genes, else a conservative all-caps token scan) and passes the **full user text** as `disease_context` into `run_pipeline` so PubMed and the report keep the user’s wording.

OpenAPI: `GET /docs` (Swagger UI).

## Run locally

From repo root, with `PYTHONPATH=src` (or editable install):

```bash
cd biotarget-scout
python -m pip install -r requirements.txt
python -m pip install -e .
```

**Windows:** from the repo root, prefer **`.\scripts\run_dev.ps1`** so `--reload` only watches `src\biotarget_scout` and `web` (fewer stray reloads when OneDrive syncs other paths).

**Manual:**

```bash
python -m uvicorn biotarget_scout.api.app:app --reload --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000/** in a browser. The form posts to the same origin (`/api/v1/hypothesis`), so no CORS is required for this default setup.

## Logging

Startup runs **`configure_logging()`** (Loguru on stderr). During **`POST /api/v1/hypothesis`** you get:

- **`HTTP`** — resolved gene (if natural language), pipeline start, completion with **run_id** and elapsed ms.
- **`ORCH`** + **blocks** — inside **`run_pipeline`**: planner summary, parallel leg outcomes, evidence bundle, confidence, done.
- **`api_request` / `api_response`** — each external HTTP / Entrez hop (PubMed esearch/efetch, UniProt, OMIM, STRING, GTEx, AlphaFold).
- **Tool lines** — `traced_call` (LITERATURE / KG / OMICS) with timing.

`GET /favicon.ico` returns **204** so the browser does not generate a misleading 404 while the POST is still running. Set **`LOG_JSON=1`** for JSON lines; **`LOG_LEVEL`** defaults to `INFO`.

## CORS

`CORSMiddleware` allows common dev origins (`localhost` / `127.0.0.1` on various ports) so you can later serve a **separate** dev server (e.g. Vite on `:5173`) that calls this API. Same-origin static hosting does not need CORS.

## Future extensions

- **Split repo / monorepo:** move `web/` to a Vite/React app; point `VITE_API_BASE` at `http://127.0.0.1:8000` and keep CORS origins in sync.
- **Auth:** add dependencies in `api/deps.py` and protect `POST /api/v1/hypothesis`.
- **Streaming:** SSE or WebSocket route if the orchestrator exposes token streams.
- **Persistent index:** extend request body with `index_mode: persistent_with_delta` and inject a server-side `shared_index` (singleton or per-session) in a future dependency.
