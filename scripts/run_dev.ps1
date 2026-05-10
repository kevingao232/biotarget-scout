# Start the API + web UI for local testing.
# Option 1 (recommended): only watch our app code + web folder. That cuts down random "Reloading..."
# when OneDrive or other sync tools touch files outside those folders.

Set-Location $PSScriptRoot\..
$env:PYTHONPATH = "src"

python -m uvicorn biotarget_scout.api.app:app `
  --reload `
  --host 127.0.0.1 `
  --port 8000 `
  --reload-dir src\biotarget_scout `
  --reload-dir web

# If it STILL keeps reloading, start without --reload (no auto-restart on save):
#   python -m uvicorn biotarget_scout.api.app:app --host 127.0.0.1 --port 8000
