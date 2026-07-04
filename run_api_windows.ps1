$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    throw "No existe .venv. Ejecuta primero setup_windows.ps1."
}

.\.venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
