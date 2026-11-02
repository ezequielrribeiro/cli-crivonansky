# Sobe o MySQL e o Apache+PHP da fixture RotaCar e cria os usuários do banco.
#
# Uso:
#   $env:HARNESS_DB_PASSWORD = "readpass"   # opcional; padrão "readpass"
#   .\setup.ps1
#
# Depois, no shell onde o harness será executado:
#   $env:HARNESS_DB_USER = "rotacar_read"
#   $env:HARNESS_DB_PASSWORD = "readpass"

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Push-Location $root
try {
    docker compose up -d --build

    Write-Host "Aguardando o MySQL ficar saudavel..."
    $deadline = (Get-Date).AddMinutes(3)
    $status = ""
    do {
        Start-Sleep -Seconds 3
        $status = docker inspect --format "{{.State.Health.Status}}" rotacar_mysql 2>$null
    } while ($status -ne "healthy" -and (Get-Date) -lt $deadline)

    if ($status -ne "healthy") {
        throw "MySQL nao ficou saudavel a tempo (status: $status)"
    }

    Write-Host "Aguardando o Apache+PHP ficar saudavel..."
    $deadline = (Get-Date).AddMinutes(2)
    $phpStatus = ""
    do {
        Start-Sleep -Seconds 3
        $phpStatus = docker inspect --format "{{.State.Health.Status}}" rotacar_php 2>$null
    } while ($phpStatus -ne "healthy" -and (Get-Date) -lt $deadline)

    if ($phpStatus -ne "healthy") {
        throw "Apache+PHP nao ficou saudavel a tempo (status: $phpStatus)"
    }

    $password = $env:HARNESS_DB_PASSWORD
    if (-not $password) { $password = "readpass" }

    $sql = @"
CREATE USER IF NOT EXISTS 'rotacar_read'@'%' IDENTIFIED BY '$password';
GRANT SELECT ON rotacar.* TO 'rotacar_read'@'%';
CREATE USER IF NOT EXISTS 'rotacar_app'@'%' IDENTIFIED BY '$password';
GRANT SELECT, INSERT, UPDATE, DELETE ON rotacar.* TO 'rotacar_app'@'%';
FLUSH PRIVILEGES;
"@

    $sql | docker exec -i rotacar_mysql mysql -uroot -prootpass

    Write-Host ""
    Write-Host "Ambiente pronto:"
    Write-Host "  - rotacar_mysql (MySQL 8.0, banco rotacar)"
    Write-Host "  - rotacar_php   (Apache + PHP, http://localhost:8081)"
    Write-Host "Defina as variaveis de ambiente para o harness:"
    Write-Host "  `$env:HARNESS_DB_USER = 'rotacar_read'"
    Write-Host "  `$env:HARNESS_DB_PASSWORD = '$password'"
}
finally {
    Pop-Location
}
