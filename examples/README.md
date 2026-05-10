# Example API calls

Health (includes package version):

```bash
curl -s http://127.0.0.1:8000/api/v1/health
```

Structured hypothesis (same body as the test UI’s structured mode):

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/hypothesis -H "Content-Type: application/json" -d "{\"target_gene\":\"PCSK9\",\"disease_context\":\"cardiovascular disease\"}"
```

Build-plan alias (`gene` + `disease_context`):

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/analyze -H "Content-Type: application/json" -d "{\"gene\":\"PCSK9\",\"disease_context\":\"cardiovascular disease\"}"
```
