<#
TOPMOST backend'ni Windows serverga o'rnatish — bitta buyruq bilan (DEPLOY.md 2–5-qadamlar).

Ishga tushirish (topmost-backend papkasida, PowerShell):
    powershell -ExecutionPolicy Bypass -File setup_server.ps1

Skript savollar beradi (domen, aloqa). Qayta ishga tushirsa bo'ladi: bor narsani buzmaydi
(.env mavjud bo'lsa — tegmaydi, baza ma'lumotlari takrorlanmaydi).
#>
param(
    [string]$Domain,           # masalan: api.topmost.uz
    [string]$Contact,          # masalan: Telegram @topmost_admin yoki +998 90 123 45 67
    [string]$BackupDir,        # masalan: D:\topmost-backups (bo'sh — loyiha ichida backups\)
    [switch]$Https,            # Cloudflare Tunnel / HTTPS allaqachon tayyor bo'lsa
    [switch]$SkipSuperuser,    # admin yaratishni o'tkazib yuborish
    [switch]$RunTests          # oxirida avtomatik testlarni ham ishga tushirish
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }
function Fail($text) { Write-Host "XATO: $text" -ForegroundColor Red; exit 1 }

# 1) Python
Step "Python tekshirilmoqda"
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { Fail "Python topilmadi. https://www.python.org dan 3.12+ o'rnating ('Add to PATH' belgisini qo'ying)." }
$version = & python -c "import sys; print('%d.%d' % sys.version_info[:2])"
if ([version]$version -lt [version]"3.12") { Fail "Python $version — kamida 3.12 kerak." }
Write-Host "Python $version"

# 2) Virtual muhit va kutubxonalar
Step "Virtual muhit va kutubxonalar"
if (-not (Test-Path "venv\Scripts\python.exe")) { & python -m venv venv }
$py = Resolve-Path "venv\Scripts\python.exe"
& $py -m pip install --upgrade pip --quiet
# Python 3.14+ da PyYAML tayyor paketi bo'lmasligi mumkin — C kompilyatorsiz o'rnatamiz
$env:PYYAML_FORCE_LIBYAML = "0"
& $py -m pip install -r requirements.txt --quiet --config-settings="pyyaml_build_config={`"without_libyaml`": true}"
if ($LASTEXITCODE -ne 0) { Fail "Kutubxonalarni o'rnatib bo'lmadi (internetni tekshiring)." }

# 3) .env
Step ".env sozlamalari"
if (Test-Path ".env") {
    Write-Host ".env allaqachon bor — o'zgartirilmadi."
} else {
    if (-not $Domain) { $Domain = Read-Host "Server domeni (masalan api.topmost.uz)" }
    if (-not $Contact) { $Contact = Read-Host "Foydalanuvchilar uchun aloqa (masalan: Telegram @topmost_admin)" }
    if (-not $BackupDir) { $BackupDir = Read-Host "Backup papkasi, boshqa diskda bo'lgani yaxshi (Enter — loyiha ichida)" }
    $secret = & $py -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
    $httpsValue = if ($Https) { "True" } else { "False" }
    @"
# Yaratildi: setup_server.ps1 ($(Get-Date -Format 'yyyy-MM-dd HH:mm'))
DEBUG=False
SECRET_KEY=$secret
ALLOWED_HOSTS=$Domain,127.0.0.1,localhost
CSRF_TRUSTED_ORIGINS=https://$Domain
# Cloudflare Tunnel / HTTPS ishlagach True qiling va backend'ni qayta yoqing
HTTPS=$httpsValue
TRUSTED_PROXY=127.0.0.1
SERVE_MEDIA=True
PORT=8000
PRIVACY_CONTACT=$Contact
BACKUP_DIR=$BackupDir
BACKUP_KEEP=14
"@ | Set-Content -Path ".env" -Encoding utf8
    Write-Host ".env yaratildi (SECRET_KEY avtomatik). Uni hech kimga bermang."
}

# 4) Baza va fayllar
Step "Baza, admin panel fayllari, tarjimalar, boshlang'ich ma'lumotlar"
& $py manage.py migrate --noinput;            if ($LASTEXITCODE) { Fail "migrate" }
& $py manage.py collectstatic --noinput -v 0; if ($LASTEXITCODE) { Fail "collectstatic" }
& $py manage.py compile_translations;         if ($LASTEXITCODE) { Fail "compile_translations" }
& $py manage.py load_initial_data;            if ($LASTEXITCODE) { Fail "load_initial_data" }

# 5) Admin
$hasAdmin = & $py manage.py shell -c "from catalog.models import User; print(User.objects.filter(is_superuser=True).exists())" 2>$null | Select-Object -Last 1
if ($SkipSuperuser) {
    Write-Host "`nAdmin yaratish o'tkazib yuborildi."
} elseif ($hasAdmin -eq "True") {
    Write-Host "`nAdmin allaqachon bor."
} else {
    Step "Admin panel uchun login va parol (username: masalan admin)"
    & $py manage.py createsuperuser
}

if ($RunTests) {
    Step "Avtomatik testlar"
    & $py manage.py test;                     if ($LASTEXITCODE) { Fail "testlar o'tmadi" }
}

# 6) Tekshiruv
Step "Server tekshiruvi"
& $py manage.py check_server
Write-Host "`nTayyor. Ishga tushirish:  venv\Scripts\python.exe serve.py" -ForegroundColor Green
Write-Host "Keyingi qadamlar: DEPLOY.md 6-bo'lim (avtomatik ishga tushish) va 7.1 (Cloudflare Tunnel)."
