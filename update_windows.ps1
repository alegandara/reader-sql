$ErrorActionPreference = "Stop"

if (-not (Test-Path ".git")) {
    throw "Este directorio no es un repositorio git."
}

if (-not (Test-Path ".venv")) {
    throw "No existe .venv. Ejecuta primero setup_windows.ps1."
}

git fetch origin
git pull --ff-only

.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\pip install -r requirements.txt

Write-Host "Actualizacion completada."
