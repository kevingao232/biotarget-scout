# BioTarget Scout

Multi-agent biomedical hypothesis pipeline (literature + KG + omics), with an optional **local FastAPI server** and **test UI**.

## Quick start (API + browser UI)

```bash
cd biotarget-scout
python -m pip install -r requirements.txt
python -m pip install -e .
```

**Windows (recommended):** use the dev script so reload only watches app + web code (stops most “Reloading…” loops with OneDrive):

```powershell
.\scripts\run_dev.ps1
```

**Any OS / manual:**

```bash
python -m uvicorn biotarget_scout.api.app:app --reload --host 127.0.0.1 --port 8000
```

- **UI:** http://127.0.0.1:8000/
- **OpenAPI:** http://127.0.0.1:8000/docs  
- **Health:** `GET http://127.0.0.1:8000/api/v1/health`  
- **Analyze:** `POST …/api/v1/hypothesis` with JSON **`{ "query": "…natural language…" }`** (UI default), or structured `{ "target_gene", "disease_context" }`; optional `index_mode`, `leg_retries`

Frontend ↔ API layout and CORS notes: [`docs/frontend-api.md`](docs/frontend-api.md).  
Broader project docs: [`docs/README.md`](docs/README.md), system flow: [`docs/system-flow.md`](docs/system-flow.md).

**Logs:** On API startup, Loguru is configured (see `core/logging.py`). Runs emit short **ORCH** / **HTTP** sentences, star-bordered blocks for big steps, **`api_request` / `api_response`** for outbound calls, and one line per **`traced_call`** tool. Use `LOG_LEVEL=DEBUG` or `LOG_JSON=1` if needed. Set **`HF_TOKEN`** in `.env` for Hugging Face Hub downloads (embedding model) to avoid unauthenticated-hub warnings.

**Reload loop:** If the server keeps restarting over and over, something else is changing files on disk (often **OneDrive**). **First fix:** run **`.\scripts\run_dev.ps1`** instead of plain `uvicorn --reload`—it only watches **`src\biotarget_scout`** and **`web`**. If it still loops, drop `--reload` (see comment in the script) or move the project out of a synced folder.

## Docker

```bash
docker compose build
docker compose up
```

Then open http://127.0.0.1:8000/ . Copy `.env.example` to `.env` before `docker compose up` so required keys exist.

## Tests

```bash
python -m pytest -q
```

Evaluation harness (eight canonical genes from the build plan, mocked pipeline): `python -m pytest tests/evaluation -m eval -q`. Live API smoke (PCSK9 only): `set RUN_E2E=1` then `python -m pytest tests/evaluation -m e2e -q`.
