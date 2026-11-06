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

  O instalador é idempotente: se uma etapa falhar no meio (clone interrompido,
  venv pela metade, arquivo travado pelo antivírus), rode de novo — o estado
  parcial é detectado e refeito. As etapas que tocam o disco têm retry.

  A escolha do Python considera o compilador C++: com Visual Studio Build Tools
  usa a versão mais nova (hoje 3.15, compilando tree-sitter/zstandard do fonte);
  sem compilador usa a mais nova com wheels prontas (hoje 3.14).

.PARAMETER CheckOnly
  Apenas verifica as dependências e o estado dos diretórios, sem instalar.

.PARAMETER SkipDocker
  Não exige o Docker (útil em máquinas sem Docker Desktop).

.PARAMETER ForceConfig
  Sobrescreve workspace\harness.yaml mesmo se ele já existir.

.PARAMETER PythonExe
  Caminho explícito do python.exe (3.13+). Também aceito via HARNESS_PYTHON.
  Use quando a detecção automática não encontrar o interpretador.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 -CheckOnly
  powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 -PythonExe C:\Python313\python.exe
#>
[CmdletBinding()]
param(
    [switch]$CheckOnly,
    [switch]$SkipDocker,
    [switch]$ForceConfig,
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

$script:StartedAt = Get-Date

$pluginRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$vendorRoot = Join-Path $pluginRoot "vendor"
$workspaceRoot = Join-Path $pluginRoot "workspace"
$fixtureRoot = Join-Path $pluginRoot "fixture\exemplo-locadora"
$requirements = Join-Path $pluginRoot "requirements.txt"
$writeConfig = Join-Path $pluginRoot "scripts\write_config.py"

# Versão mínima exigida (o RAG usa recursos de 3.13+).
$minimumPython = [version]"3.13"
# Última versão em que todas as dependências (torch, tree-sitter, zstandard,
# pyyaml) têm wheel binária no PyPI; acima dela alguns pacotes são compilados
# do fonte e exigem Visual Studio Build Tools (C++).
$lastWheelPython = [version]"3.14"

# Dependências externas clonadas dentro do plugin.
$projects = @(
    @{ Name = "local-rag-system"; Remote = "https://github.com/ezequielrribeiro/local-rag-system.git"; Kind = "rag" },
    @{ Name = "codeknow"; Remote = "https://github.com/asalsali/codeknow.git"; Kind = "codeknow" }
)

# ---------------------------------------------------------------------------
# Helpers de saída
# ---------------------------------------------------------------------------
function Write-Step([string]$msg) {
    $elapsed = (Get-Date) - $script:StartedAt
    Write-Host ""
    Write-Host ("==> [{0:hh\:mm\:ss}] {1}" -f $elapsed, $msg) -ForegroundColor Cyan
}

function Write-Ok([string]$msg) {
    Write-Host "    [OK] $msg" -ForegroundColor Green
}

function Write-Warn([string]$msg) {
    Write-Host "    [!!] $msg" -ForegroundColor Yellow
}

function Write-Fail([string]$msg) {
    Write-Host "    [XX] $msg" -ForegroundColor Red
}

function Test-Command([string]$name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

# ---------------------------------------------------------------------------
# Execução de programas externos
#
# Gotcha do PowerShell 5.1: com $ErrorActionPreference = "Stop", redirecionar o
# stderr de um programa nativo (git/pip escrevem progresso em stderr) cria
# ErrorRecords que abortam o script ("NativeCommandError"). Por isso todo
# programa externo passa por Invoke-Native, que suspende o Stop durante a
# execução e devolve código de saída + saída combinada.
# ---------------------------------------------------------------------------
function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)][string[]]$Command,
        [string]$WorkingDirectory,
        [switch]$Echo
    )

    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $lines = New-Object System.Collections.Generic.List[string]
    $exit = 1
    $pushed = $false

    try {
        if ($WorkingDirectory) {
            Push-Location -LiteralPath $WorkingDirectory
            $pushed = $true
        }

        $exe = $Command[0]
        $rest = @()
        if ($Command.Count -gt 1) {
            $rest = $Command[1..($Command.Count - 1)]
        }

        & $exe @rest 2>&1 | ForEach-Object {
            $text = "$_"
            $lines.Add($text)
            if ($Echo) { Write-Host "      $text" }
        }
        $exit = $LASTEXITCODE
        if ($null -eq $exit) { $exit = 0 }
    }
    finally {
        if ($pushed) { Pop-Location }
        $ErrorActionPreference = $previous
    }

    return [pscustomobject]@{ ExitCode = $exit; Output = ($lines -join "`n") }
}

function Invoke-WithRetry {
    param(
        [Parameter(Mandatory = $true)][scriptblock]$Action,
        [Parameter(Mandatory = $true)][string]$Description,
        [int]$Attempts = 3,
        [int]$DelaySeconds = 2
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            & $Action
            return
        }
        catch {
            if ($attempt -ge $Attempts) {
                throw "$Description falhou apos $Attempts tentativa(s): $($_.Exception.Message)"
            }
            Write-Warn "$Description falhou (tentativa $attempt/$Attempts): $($_.Exception.Message)"
            Start-Sleep -Seconds ($DelaySeconds * $attempt)
        }
    }
}

function Remove-PathWithRetry([string]$path) {
    if (-not (Test-Path -LiteralPath $path)) { return }
    Invoke-WithRetry -Description "remover $path" -Action {
        Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction Stop
    }
}

function Ensure-Dir([string]$path) {
    Invoke-WithRetry -Description "criar $path" -Action {
        if (-not (Test-Path -LiteralPath $path)) {
            New-Item -ItemType Directory -Force -Path $path -ErrorAction Stop | Out-Null
        }
    }
}

function Test-Writable([string]$path) {
    try {
        Ensure-Dir $path
        $probe = Join-Path $path (".harness-write-{0}.tmp" -f $PID)
        Set-Content -LiteralPath $probe -Value "ok" -Encoding UTF8 -ErrorAction Stop
        Remove-Item -LiteralPath $probe -Force -ErrorAction Stop
        return $true
    }
    catch {
        Write-Fail "sem permissao para escrever em ${path}: $($_.Exception.Message)"
        Write-Host "         Verifique se a pasta nao esta dentro de OneDrive/Program Files" -ForegroundColor Yellow
        Write-Host "         ou se o antivirus esta bloqueando a criacao de arquivos." -ForegroundColor Yellow
        return $false
    }
}

# ---------------------------------------------------------------------------
# Descoberta do Python
# ---------------------------------------------------------------------------
function Test-Compiler {
    # Detecta um compilador C/C++ (cl.exe ou Visual Studio Build Tools).
    if (Test-Command "cl") { return $true }

    $vswhere = Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio\Installer\vswhere.exe"
    if (-not (Test-Path -LiteralPath $vswhere)) { return $false }

    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $install = & $vswhere -latest -products * `
            -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 `
            -property installationPath 2>$null
    }
    finally {
        $ErrorActionPreference = $previous
    }

    return [bool]($install -and (Test-Path -LiteralPath $install))
}

function Get-PythonVersion([string]$exe) {
    if (-not $exe) { return $null }
    if (-not (Test-Path -LiteralPath $exe)) { return $null }

    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $out = & $exe -c "import sys; print('%d.%d.%d' % sys.version_info[:3]); sys.exit(0 if sys.version_info >= (3, 13) else 1)" 2>$null
        $code = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previous
    }

    if ($code -ne 0) { return $null }
    $text = @($out) | Select-Object -First 1
    if ($text -and $text -match '^\d+\.\d+\.\d+$') { return $text }
    return $null
}

function Add-PythonCandidate {
    param(
        [System.Collections.Generic.List[object]]$List,
        [string]$Path,
        [string]$Source
    )
    if (-not $Path) { return }
    if ($List | Where-Object { $_.Path -eq $Path }) { return }
    $List.Add([pscustomobject]@{ Path = $Path; Source = $Source })
}

function Get-PythonCandidates {
    $list = New-Object System.Collections.Generic.List[object]

    Add-PythonCandidate $list $PythonExe "-PythonExe"
    Add-PythonCandidate $list $env:HARNESS_PYTHON "HARNESS_PYTHON"

    # py launcher (instalações "para todos os usuários" e por usuário).
    if (Test-Command "py") {
        $previous = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            $versions = & py -0p 2>$null
        }
        finally {
            $ErrorActionPreference = $previous
        }
        foreach ($line in @($versions)) {
            if ("$line" -match '([A-Za-z]:\\.+?python\.exe)\s*$') {
                Add-PythonCandidate $list $matches[1] "py launcher"
            }
        }
    }

    # Instalações oficiais e por usuário.
    $roots = @(
        "C:\",
        (Join-Path $env:LOCALAPPDATA "Programs\Python"),
        (Join-Path $env:LOCALAPPDATA "Python"),
        (Join-Path $env:LOCALAPPDATA "Python\bin")
    )
    foreach ($root in $roots) {
        if (-not $root -or -not (Test-Path -LiteralPath $root)) { continue }
        $exe = Join-Path $root "python.exe"
        if (Test-Path -LiteralPath $exe) {
            Add-PythonCandidate $list $exe "instalacao em $root"
        }
        Get-ChildItem -LiteralPath $root -Filter "Python3*" -Directory -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending |
            ForEach-Object {
                Add-PythonCandidate $list (Join-Path $_.FullName "python.exe") "instalacao em $($_.FullName)"
            }
    }

    # Registro (inclui instalações fora dos caminhos padrão).
    $hives = @(
        "HKLM:\SOFTWARE\Python\PythonCore",
        "HKCU:\SOFTWARE\Python\PythonCore",
        "HKLM:\SOFTWARE\WOW6432Node\Python\PythonCore"
    )
    foreach ($hive in $hives) {
        if (-not (Test-Path $hive)) { continue }
        Get-ChildItem $hive -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending |
            ForEach-Object {
                $install = Get-ItemProperty (Join-Path $_.PSPath "InstallPath") -ErrorAction SilentlyContinue
                if ($install -and $install.ExecutablePath) {
                    Add-PythonCandidate $list $install.ExecutablePath "registro ($($_.PSChildName))"
                }
            }
    }

    # PATH (ignorando o atalho da Microsoft Store, que abre a loja).
    foreach ($name in @("python", "python3")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source -and $cmd.Source -notmatch 'WindowsApps') {
            Add-PythonCandidate $list $cmd.Source "PATH"
        }
    }

    return $list
}

function Find-Python {
    # Um caminho informado explicitamente não pode cair silenciosamente em
    # outro interpretador: se estiver errado, falhe com mensagem clara.
    $explicit = @()
    if ($PythonExe) { $explicit += @{ Path = $PythonExe; Source = "-PythonExe" } }
    if ($env:HARNESS_PYTHON) { $explicit += @{ Path = $env:HARNESS_PYTHON; Source = "HARNESS_PYTHON" } }
    foreach ($item in $explicit) {
        $version = Get-PythonVersion $item.Path
        if (-not $version) {
            throw "$($item.Source) aponta para um Python invalido ou anterior a $minimumPython`: $($item.Path)"
        }
        return [pscustomobject]@{
            Path    = $item.Path
            Version = $version
            Source  = $item.Source
        }
    }

    $found = New-Object System.Collections.Generic.List[object]
    $rejected = New-Object System.Collections.Generic.List[object]

    foreach ($candidate in (Get-PythonCandidates)) {
        $version = Get-PythonVersion $candidate.Path
        if ($version) {
            $found.Add([pscustomobject]@{
                    Path    = $candidate.Path
                    Version = $version
                    Source  = $candidate.Source
                })
        }
        else {
            $rejected.Add($candidate)
        }
    }

    if ($found.Count -eq 0) {
        if ($rejected.Count -gt 0) {
            Write-Host "    Interpretadores encontrados, mas nenhum atende Python $minimumPython+:" -ForegroundColor Yellow
            foreach ($item in $rejected) {
                $raw = Invoke-Native @($item.Path, "--version")
                $version = ($raw.Output -split "`n" | Select-Object -First 1)
                Write-Host "      - $($item.Path) [$version]" -ForegroundColor DarkGray
            }
        }
        return $null
    }

    $newest = $found | Sort-Object { [version]$_.Version } -Descending | Select-Object -First 1

    # Com compilador C++ instalado, a versão mais recente funciona (alguns
    # pacotes são compilados do fonte). Sem compilador, prefira a mais nova
    # que tem wheel binária para todo o stack (hoje, 3.14).
    if ($script:HasCompiler) {
        return $newest
    }

    $withWheels = $found |
        Where-Object { [version]$_.Version -le $lastWheelPython } |
        Sort-Object { [version]$_.Version } -Descending |
        Select-Object -First 1

    if ($withWheels) {
        if ([version]$newest.Version -gt $lastWheelPython) {
            Write-Warn "Python $($newest.Version) encontrado, mas sem compilador C++: usando $($withWheels.Version) (wheels prontas)."
        }
        return $withWheels
    }

    if ([version]$newest.Version -gt $lastWheelPython) {
        Write-Warn "Sem compilador C++ e sem Python ${lastWheelPython}: usando $($newest.Version)."
        Write-Warn "A instalacao do RAG pode falhar ao compilar zstandard; instale Build Tools C++."
    }
    return $newest
}

# ---------------------------------------------------------------------------
# Git / venv / pip
# ---------------------------------------------------------------------------
function Test-GitRepo([string]$dir) {
    if (-not (Test-Path (Join-Path $dir ".git"))) { return $false }
    $result = Invoke-Native @("git", "-C", $dir, "rev-parse", "--verify", "HEAD")
    return $result.ExitCode -eq 0
}

function Sync-Repo([string]$name, [string]$remote) {
    $dir = Join-Path $vendorRoot $name

    if (Test-GitRepo $dir) {
        Write-Host "    atualizando vendor\$name ..."
        $pull = Invoke-Native @("git", "-C", $dir, "pull", "--ff-only")
        if ($pull.ExitCode -ne 0) {
            Write-Warn "falha no pull de vendor\$name (mantendo a copia local)"
        }
        else {
            Write-Ok "vendor\$name atualizado"
        }
        return
    }

    if (Test-Path -LiteralPath $dir) {
        Write-Warn "vendor\$name incompleto (clone interrompido); refazendo"
        Remove-PathWithRetry $dir
    }

    Write-Host "    clonando vendor\$name ..."
    Invoke-WithRetry -Description "clonar vendor\$name" -Attempts 3 -Action {
        if (Test-Path -LiteralPath $dir) { Remove-PathWithRetry $dir }
        $clone = Invoke-Native @("git", "clone", "--depth", "1", $remote, $dir)
        if ($clone.ExitCode -ne 0) {
            $tail = ($clone.Output -split "`n" | Select-Object -Last 3) -join " "
            throw "git clone: $tail"
        }
    }
    Write-Ok "vendor\$name clonado"
}

function Test-Venv([string]$venv) {
    $python = Join-Path $venv "Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $python)) { return $false }

    $probe = Invoke-Native @($python, "-I", "-c", "import sys; print(sys.version_info[:2])")
    if ($probe.ExitCode -ne 0) { return $false }

    $pip = Invoke-Native @($python, "-I", "-m", "pip", "--version")
    return $pip.ExitCode -eq 0
}

function Ensure-Venv([string]$dir) {
    $venv = Join-Path $dir ".venv"

    if (Test-Venv $venv) {
        Write-Ok "venv ja existe e esta funcional em $dir"
        return (Join-Path $venv "Scripts\python.exe")
    }

    if (Test-Path -LiteralPath $venv) {
        Write-Warn "venv incompleto em $dir (execucao anterior interrompida); recriando"
        Remove-PathWithRetry $venv
    }

    Write-Host "    criando venv em $dir ..."
    Invoke-WithRetry -Description "criar venv em $dir" -Action {
        $created = Invoke-Native @($script:Python.Path, "-I", "-m", "venv", $venv)
        if ($created.ExitCode -ne 0) {
            $tail = ($created.Output -split "`n" | Select-Object -Last 5) -join " "
            throw "python -m venv: $tail"
        }
    }

    if (-not (Test-Venv $venv)) {
        throw "venv criado em $dir, mas o pip nao esta funcional. Verifique antivirus/permissao na pasta."
    }

    Write-Ok "venv criado em $dir"
    return (Join-Path $venv "Scripts\python.exe")
}

function Upgrade-Pip([string]$python) {
    # Best-effort: um pip desatualizado não impede a instalação.
    $result = Invoke-Native @($python, "-I", "-m", "pip", "install", "--upgrade", "pip", "--disable-pip-version-check", "--no-input")
    if ($result.ExitCode -ne 0) {
        Write-Warn "nao foi possivel atualizar o pip (seguindo com a versao atual)"
    }
}

function Install-Pip([string]$python, [string[]]$pipArgs) {
    $label = "pip install $($pipArgs -join ' ')"
    Write-Host "    $label"

    for ($attempt = 1; $attempt -le 3; $attempt++) {
        $result = Invoke-Native (@($python, "-I", "-m", "pip", "install", "--disable-pip-version-check", "--no-input") + $pipArgs)
        if ($result.ExitCode -eq 0) { return }

        $tail = ($result.Output -split "`n" | Select-Object -Last 15) -join "`n"

        # Erros de resolução/wheel não melhoram com retry (ex.: Python novo sem
        # wheel do torch): falha na hora, com a mensagem do pip.
        if ($result.Output -match "No matching distribution|Could not find a version|is not a supported wheel") {
            throw "$label falhou (sem wheel/distribuicao compativel com o Python $($script:Python.Version)):`n$tail"
        }

        # Falha ao compilar um pacote sem wheel (precisa de compilador C++).
        if ($result.Output -match "Microsoft Visual C\+\+|error: subprocess-exited-with-error|Failed building wheel") {
            throw "$label falhou ao compilar uma dependencia sem wheel para o Python $($script:Python.Version).`nInstale o Visual Studio Build Tools (C++) ou rode com -PythonExe apontando para o Python $lastWheelPython (que tem wheels prontas).`n$tail"
        }

        if ($attempt -ge 3) {
            throw "$label falhou apos 3 tentativa(s):`n$tail"
        }

        Write-Warn "$label falhou (tentativa $attempt/3); tentando de novo em $($attempt * 2)s"
        Start-Sleep -Seconds ($attempt * 2)
    }
}

# ---------------------------------------------------------------------------
# 1. Verificacao de dependencias
# ---------------------------------------------------------------------------
Write-Step "Verificando dependencias"

$missing = @()

if (-not (Test-Command "git")) { $missing += "Git" }
if (-not $SkipDocker -and -not (Test-Command "docker")) { $missing += "Docker Desktop" }

$script:HasCompiler = Test-Compiler
if ($script:HasCompiler) {
    Write-Ok "Compilador C++ detectado (pacotes sem wheel podem ser compilados)"
}
else {
    Write-Warn "Sem compilador C++: sera escolhido o Python mais novo com wheels prontas"
}

$script:Python = $null
try {
    $script:Python = Find-Python
}
catch {
    Write-Fail $_.Exception.Message
}
if (-not $script:Python) {
    $missing += "Python $minimumPython+ (nao encontrado)"
}
else {
    $pyVer = & $script:Python.Path --version 2>&1
    Write-Ok "$pyVer ($($script:Python.Path)) - origem: $($script:Python.Source)"
    if ([version]$script:Python.Version -gt $lastWheelPython) {
        Write-Warn "Python $($script:Python.Version) e mais novo que $lastWheelPython."
        Write-Warn "tree-sitter e zstandard serao compilados do fonte (requer Build Tools C++)."
    }
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
    if ($missing -match "Python") {
        Write-Host "  Python 3.13: https://www.python.org/downloads/"
        Write-Host "  Se o Python ja esta instalado, informe o caminho: -PythonExe C:\caminho\python.exe"
        Write-Host "  (ou defina a variavel de ambiente HARNESS_PYTHON)"
    }
    exit 1
}

if ($CheckOnly) {
    Write-Host ""
    Write-Host "Verificando escrita em vendor/ e workspace/ ..."
    $writable = (Test-Writable $vendorRoot) -and (Test-Writable $workspaceRoot)
    if (-not $writable) {
        Write-Host ""
        Write-Host "Sem permissao de escrita; a instalacao vai falhar." -ForegroundColor Red
        exit 1
    }
    Write-Host ""
    Write-Host "Dependencias OK. Modo -CheckOnly: nada sera instalado." -ForegroundColor Green
    exit 0
}

# ---------------------------------------------------------------------------
# 2. Sincronizar dependencias externas dentro do plugin
# ---------------------------------------------------------------------------
Write-Step "Preparando vendor e workspace"

Ensure-Dir $vendorRoot
Ensure-Dir $workspaceRoot
if (-not (Test-Writable $vendorRoot)) { throw "sem permissao de escrita em $vendorRoot" }

foreach ($project in $projects) {
    Sync-Repo $project.Name $project.Remote
}

# ---------------------------------------------------------------------------
# 3. Venv do plugin (requirements + codeknow editavel)
# ---------------------------------------------------------------------------
Write-Step "Instalando o venv do plugin"

$pluginPip = Ensure-Venv $pluginRoot
Upgrade-Pip $pluginPip
Write-Host "    instalando requirements do plugin ..."
Install-Pip $pluginPip @("-r", $requirements)

$script:CodeknowOk = $false
$codeknowDir = Join-Path $vendorRoot "codeknow"
if (Test-Path (Join-Path $codeknowDir "pyproject.toml")) {
    Write-Host "    instalando codeknow (editavel) no venv do plugin ..."
    try {
        Install-Pip $pluginPip @("-e", $codeknowDir)
        $script:CodeknowOk = $true
        Write-Ok "codeknow instalado"
    }
    catch {
        # codeknow (tree-sitter) pode precisar de compilador C++ no Python mais
        # novo. O resto do harness (db:links, docs, rag) funciona sem ele.
        Write-Warn "codeknow nao instalou: $($_.Exception.Message)"
        Write-Warn "code:index/code:query ficam indisponiveis; o restante funciona."
        Write-Warn "Use -PythonExe com o Python $lastWheelPython (wheels prontas) ou instale Build Tools C++."
    }
}
else {
    Write-Warn "codeknow nao encontrado em vendor; code:index ficara indisponivel"
}

# ---------------------------------------------------------------------------
# 4. Venv do RAG
# ---------------------------------------------------------------------------
Write-Step "Instalando o RAG"

$ragDir = Join-Path $vendorRoot "local-rag-system"
if (Test-Path (Join-Path $ragDir "requirements.txt")) {
    $ragPip = Ensure-Venv $ragDir
    Upgrade-Pip $ragPip
    Write-Host "    instalando requirements do RAG (pode demorar varios minutos) ..."
    Install-Pip $ragPip @("-r", (Join-Path $ragDir "requirements.txt"))
    Install-Pip $ragPip @("scikit-learn", "requests", "pytest", "httpx")
}
else {
    Write-Warn "local-rag-system nao encontrado em vendor"
}

# ---------------------------------------------------------------------------
# 5. Config do workspace
# ---------------------------------------------------------------------------
Write-Step "Gerando workspace\harness.yaml"

if ((Test-Path $writeConfig) -and (Test-Path $pluginPip)) {
    $configArgs = @($writeConfig)
    if ($ForceConfig) { $configArgs += "--force" }
    $config = Invoke-Native (@($pluginPip) + $configArgs)
    if ($config.ExitCode -ne 0) { throw "Falha ao gerar workspace\harness.yaml`n$($config.Output)" }
}
else {
    Write-Warn "scripts\write_config.py nao encontrado; harness.yaml nao foi gerado"
}

# ---------------------------------------------------------------------------
# 6. Resumo
# ---------------------------------------------------------------------------
Write-Step "Instalacao concluida"

$total = (Get-Date) - $script:StartedAt
Write-Host ""
Write-Host ("Tudo dentro de: {0} (em {1:hh\:mm\:ss})" -f $pluginRoot, $total) -ForegroundColor Cyan
if (-not $script:CodeknowOk) {
    Write-Warn "codeknow indisponivel: code:index/code:query nao vao funcionar."
    Write-Warn "O restante do harness (db:links, docs:import, rag:sync) esta pronto."
}
Write-Host "Proximos passos:" -ForegroundColor Cyan
Write-Host "  1. Suba o ambiente:  python crivonansky.py harness start"
Write-Host "  2. Prepare a base:   python crivonansky.py harness prepare"
Write-Host "  3. Abra a TUI:       python crivonansky.py"
Write-Host ""
