param(
    [string]$RepoUrl = "git@github.com:alegandara/reader-sql.git",
    [string]$TargetDir = "reader-sql"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git no esta instalado. Instala Git for Windows e intenta de nuevo."
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python no esta instalado. Instala Python 3.10+ e intenta de nuevo."
}

if (-not (Test-Path $TargetDir)) {
    git clone $RepoUrl $TargetDir
}

Set-Location $TargetDir

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
    Write-Host "Se creo .env. Editalo con tus credenciales SQL Server."
}

Write-Host "Listo. Proyecto configurado en Windows."
