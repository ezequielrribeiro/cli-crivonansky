<#
.SYNOPSIS
  Instala o plugin harness dentro de commands\complements\harness.

.DESCRIPTION
  Verifica Python 3.13+, Git e Docker; clona/atualiza as dependências externas
  em <plugin>\vendor; cria o venv do plugin com os requirements e o codeknow;
  cria o venv do RAG; e gera <plugin>\workspace\harness.yaml a partir de
  harness.example.yaml.

  Tudo fica dentro do plugin:
    .venv\      dependências Python do plugin + codeknow (editável)
    vendor\     local-rag-system + codeknow (gitignored)
    workspace\  harness.yaml, knowledge\ e runs\ (gitignored)
    fixture\    exemplo-locadora (versionada)

.PARAMETER CheckOnly
  Apenas verifica as dependências e o estado dos diretórios, sem instalar.

.PARAMETER SkipDocker
  Não exige o Docker (útil em máquinas sem Docker Desktop).

.PARAMETER ForceConfig
  Sobrescreve workspace\harness.yaml mesmo se ele já existir.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 -CheckOnly
#>
[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$SkipDocker,
    [switch]$ForceConfig
)

$ErrorActionPreference = "Stop"

$pluginRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$vendorRoot = Join-Path $pluginRoot "vendor"
$workspaceRoot = Join-Path $pluginRoot "workspace"
$fixtureRoot = Join-Path $pluginRoot "fixture\exemplo-locadora"
$requirements = Join-Path $pluginRoot "requirements.txt"
$writeConfig = Join-Path $pluginRoot "scripts\write_config.py"

# Dependências externas clonadas dentro do plugin.
$projects = @(
    @{ Name = "local-rag-system"; Remote = "https://github.com/ezequielrribeiro/local-rag-system.git"; Kind = "rag" },
    @{ Name = "codeknow"; Remote = "https://github.com/asalsali/codeknow.git"; Kind = "codeknow" }
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Write-Step([string]$msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Write-Ok([string]$msg) {
    Write-Host "    [OK] $msg" -ForegroundColor Green
}

function Write-Warn([string]$msg) {
    Write-Host "    [!!] $msg" -ForegroundColor Yellow
}

function Test-Command([string]$name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Find-Python {
    if (Test-Path "C:\Python313\python.exe") { return "C:\Python313\python.exe" }

    if (Test-Command "py") {
        $exe = & py -3.13 -c "import sys; print(sys.executable)" 2>$null
        if ($exe) { return $exe.Trim() }
    }

    if (Test-Command "python") {
        $ok = & python -c "import sys; sys.exit(0 if sys.version_info >= (3,13) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) { return (Get-Command python).Source }
    }

    return $null
}

function Sync-Repo([string]$name, [string]$remote) {
    $dir = Join-Path $vendorRoot $name
    if (Test-Path (Join-Path $dir ".git")) {
        Write-Host "    atualizando vendor\$name ..."
        git -C $dir pull --ff-only 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "falha no pull de vendor\$name (mantendo a copia local)"
        } else {
            Write-Ok "vendor\$name atualizado"
        }
    } else {
        Write-Host "    clonando vendor\$name ..."
        git clone --depth 1 $remote $dir 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Falha ao clonar $name ($remote)"
        }
        Write-Ok "vendor\$name clonado"
    }
}

function Ensure-Venv([string]$dir) {
    $venv = Join-Path $dir ".venv"
    if (Test-Path (Join-Path $venv "Scripts\python.exe")) {
        Write-Ok "venv ja existe em $dir"
        return Join-Path $venv "Scripts\python.exe"
    }
    Write-Host "    criando venv em $dir ..."
    & $script:Python -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw "Falha ao criar venv em $dir" }
    Write-Ok "venv criado em $dir"
    return Join-Path $venv "Scripts\python.exe"
}

function Install-Pip([string]$pip, [string[]]$pipArgs) {
    & $pip -m pip install --upgrade pip 2>&1 | Out-Null
    & $pip -m pip install @pipArgs
    if ($LASTEXITCODE -ne 0) { throw "Falha no pip install: $($pipArgs -join ' ')" }
}

# ---------------------------------------------------------------------------
# 1. Verificacao de dependencias
# ---------------------------------------------------------------------------
Write-Step "Verificando dependencias"

$missing = @()

if (-not (Test-Command "git")) { $missing += "Git" }
if (-not $SkipDocker -and -not (Test-Command "docker")) { $missing += "Docker Desktop" }

$Python = Find-Python
if (-not $Python) {
    $missing += "Python 3.13+ (esperado em C:\Python313)"
} else {
    $pyVer = & $Python --version 2>&1
    Write-Ok "Python: $pyVer ($Python)"
}

if (Test-Command "git") { Write-Ok "Git: $(git --version)" }
if (Test-Command "docker") { Write-Ok "Docker: $(docker --version)" }
elseif ($SkipDocker) { Write-Warn "Docker ignorado (-SkipDocker)" }

if (-not (Test-Path $requirements)) { $missing += "requirements.txt do plugin ($requirements)" }
if (-not (Test-Path $fixtureRoot)) { $missing += "fixture em $fixtureRoot" }

Write-Host ""
Write-Host "    plugin:    $pluginRoot"
Write-Host "    vendor:    $vendorRoot"
Write-Host "    workspace: $workspaceRoot"
Write-Host "    fixture:   $fixtureRoot"

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "Dependencias ausentes:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    Write-Host ""
    Write-Host "Instale-as e rode novamente. Sugestoes:" -ForegroundColor Yellow
    if ($missing -contains "Git") { Write-Host "  Git: https://git-scm.com/download/win" }
    if ($missing -contains "Docker Desktop") { Write-Host "  Docker: https://www.docker.com/products/docker-desktop/" }
    if ($missing -match "Python") { Write-Host "  Python 3.13: https://www.python.org/downloads/ (instale em C:\Python313)" }
    exit 1
}

if ($CheckOnly) {
    Write-Host ""
    Write-Host "Dependencias OK. Modo -CheckOnly: nada sera instalado." -ForegroundColor Green
    exit 0
}

# ---------------------------------------------------------------------------
# 2. Sincronizar dependencias externas dentro do plugin
# ---------------------------------------------------------------------------
Write-Step "Sincronizando dependencias em vendor"

New-Item -ItemType Directory -Force -Path $vendorRoot | Out-Null
New-Item -ItemType Directory -Force -Path $workspaceRoot | Out-Null

foreach ($project in $projects) {
    Sync-Repo $project.Name $project.Remote
}

# ---------------------------------------------------------------------------
# 3. Venv do plugin (requirements + codeknow editavel)
# ---------------------------------------------------------------------------
Write-Step "Instalando o venv do plugin"

$pluginPip = Ensure-Venv $pluginRoot
Write-Host "    instalando requirements do plugin ..."
Install-Pip $pluginPip @("-r", $requirements)

$codeknowDir = Join-Path $vendorRoot "codeknow"
if (Test-Path (Join-Path $codeknowDir "pyproject.toml")) {
    Write-Host "    instalando codeknow (editavel) no venv do plugin ..."
    Install-Pip $pluginPip @("-e", $codeknowDir)
} else {
    Write-Warn "codeknow nao encontrado em vendor; code:index ficara indisponivel"
}

# ---------------------------------------------------------------------------
# 4. Venv do RAG
# ---------------------------------------------------------------------------
Write-Step "Instalando o RAG"

$ragDir = Join-Path $vendorRoot "local-rag-system"
if (Test-Path (Join-Path $ragDir "requirements.txt")) {
    $ragPip = Ensure-Venv $ragDir
    Write-Host "    instalando requirements do RAG ..."
    Install-Pip $ragPip @("-r", (Join-Path $ragDir "requirements.txt"))
    Install-Pip $ragPip @("scikit-learn", "requests", "pytest", "httpx")
} else {
    Write-Warn "local-rag-system nao encontrado em vendor"
}

# ---------------------------------------------------------------------------
# 5. Config do workspace
# ---------------------------------------------------------------------------
Write-Step "Gerando workspace\harness.yaml"

if ((Test-Path $writeConfig) -and (Test-Path $pluginPip)) {
    $configArgs = @($writeConfig)
    if ($ForceConfig) { $configArgs += "--force" }
    & $pluginPip @configArgs
    if ($LASTEXITCODE -ne 0) { throw "Falha ao gerar workspace\harness.yaml" }
} else {
    Write-Warn "scripts\write_config.py nao encontrado; harness.yaml nao foi gerado"
}

# ---------------------------------------------------------------------------
# 6. Resumo
# ---------------------------------------------------------------------------
Write-Step "Instalacao concluida"

Write-Host ""
Write-Host "Tudo dentro de: $pluginRoot" -ForegroundColor Cyan
Write-Host "Proximos passos:" -ForegroundColor Cyan
Write-Host "  1. Suba o ambiente:  python crivonansky.py harness start"
Write-Host "  2. Prepare a base:   python crivonansky.py harness prepare"
Write-Host "  3. Abra a TUI:       python crivonansky.py"
Write-Host ""
