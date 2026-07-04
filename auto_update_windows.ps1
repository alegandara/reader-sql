param(
    [int]$Minutes = 10
)

$ErrorActionPreference = "Continue"

if ($Minutes -lt 1) {
    throw "Minutes debe ser mayor o igual a 1."
}

Write-Host "Auto-actualizacion iniciada. Intervalo: $Minutes minuto(s)."
Write-Host "Presiona Ctrl + C para detener."

while ($true) {
    $now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$now] Ejecutando update_windows.ps1..."
    & .\update_windows.ps1
    Start-Sleep -Seconds ($Minutes * 60)
}
