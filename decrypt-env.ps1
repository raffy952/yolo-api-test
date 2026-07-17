# decrypt-env.ps1
# Decifra .env.enc in .env (in chiaro, temporaneo) e genera i file in secrets/
# usati da Docker Compose come "secrets" montati nei container.
# Uso: .\decrypt-env.ps1

if (-not (Test-Path ".env.enc")) {
    Write-Host "Errore: non trovo .env.enc nella cartella corrente." -ForegroundColor Red
    exit 1
}

$secure = Read-Host "Passphrase per decifrare .env.enc" -AsSecureString
$bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
$plainPassphrase = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
[System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

docker run --rm -v ${PWD}:/work -w /work alpine/openssl enc -aes-256-cbc -d -pbkdf2 -in .env.enc -out .env -pass pass:"$plainPassphrase"

$plainPassphrase = $null

if (-not ((Test-Path ".env") -and ((Get-Item ".env").Length -gt 0))) {
    Write-Host "Passphrase sbagliata o errore nella decifratura. Riprova." -ForegroundColor Red
    if (Test-Path ".env") { Remove-Item ".env" }
    exit 1
}

Write-Host "Creato .env in chiaro." -ForegroundColor Green

# --- Genera i file secrets/ a partire dal .env decifrato ---
$envVars = @{}
Get-Content ".env" | ForEach-Object {
    if ($_ -match "^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$") {
        $envVars[$matches[1].Trim()] = $matches[2].Trim()
    }
}

$required = @("DB_USER", "DB_PASSWORD", "GRAFANA_ADMIN_USER", "GRAFANA_ADMIN_PASSWORD")
foreach ($key in $required) {
    if (-not $envVars.ContainsKey($key) -or [string]::IsNullOrWhiteSpace($envVars[$key])) {
        Write-Host "Attenzione: manca la variabile '$key' nel tuo .env. Controlla .env.example." -ForegroundColor Yellow
    }
}

New-Item -ItemType Directory -Force -Path "secrets" | Out-Null

# -NoNewline evita che un a-capo finale finisca dentro la password letta dal container
$envVars["DB_USER"]                | Out-File -Encoding ascii -NoNewline "secrets\db_user.txt"
$envVars["DB_PASSWORD"]            | Out-File -Encoding ascii -NoNewline "secrets\db_password.txt"
$envVars["GRAFANA_ADMIN_USER"]     | Out-File -Encoding ascii -NoNewline "secrets\grafana_admin_user.txt"
$envVars["GRAFANA_ADMIN_PASSWORD"] | Out-File -Encoding ascii -NoNewline "secrets\grafana_admin_password.txt"

Write-Host "Generati i file in .\secrets\ per Docker Compose." -ForegroundColor Green
Write-Host "Ora puoi lanciare: docker compose up -d" -ForegroundColor Green
Write-Host "Ricordati che .env e secrets\ sono in chiaro sul disco: sono gia' esclusi in .gitignore, non committarli." -ForegroundColor Yellow
