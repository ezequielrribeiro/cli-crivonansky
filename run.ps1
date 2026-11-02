Set-ExecutionPolicy Bypass -Scope Process

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Error "Venv nao encontrado: $py. Rode o instalador primeiro."
    exit 1
}

& $py (Join-Path $root "crivonansky.py") @args
exit $LASTEXITCODE
