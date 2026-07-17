# encrypt-env.ps1
# Cifra il file .env in .env.enc con AES-256 (via un container Docker temporaneo, non serve openssl installato).
# Uso: .\encrypt-env.ps1

if (-not (Test-Path ".env")) {
    Write-Host "Errore: non trovo .env nella cartella corrente. Crealo prima da .env.example." -ForegroundColor Red
    exit 1
}

$secure = Read-Host "Scegli una passphrase per cifrare .env (ricordala, serve per decifrarlo)" -AsSecureString
$bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
$plainPassphrase = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
[System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

docker run --rm -v ${PWD}:/work -w /work alpine/openssl enc -aes-256-cbc -salt -pbkdf2 -in .env -out .env.enc -pass pass:"$plainPassphrase"

$plainPassphrase = $null

if (Test-Path ".env.enc") {
    Write-Host "Creato .env.enc. Questo file e' sicuro da committare su Git." -ForegroundColor Green
    Write-Host "Ricorda la passphrase: senza, .env.enc non si puo' piu' decifrare." -ForegroundColor Yellow
} else {
    Write-Host "Qualcosa e' andato storto, .env.enc non e' stato creato." -ForegroundColor Red
}
