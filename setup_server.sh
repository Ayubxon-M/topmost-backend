#!/usr/bin/env bash
# TOPMOST backend'ni Linux serverga o'rnatish — bitta buyruq bilan (DEPLOY.md 2–5-qadamlar).
#
# Ishga tushirish (topmost-backend papkasida):
#     bash setup_server.sh
#
# Skript savollar beradi (domen, aloqa). Qayta ishga tushirsa bo'ladi: bor narsani buzmaydi
# (.env mavjud bo'lsa — tegmaydi, baza ma'lumotlari takrorlanmaydi).
set -euo pipefail
cd "$(dirname "$0")"

step() { printf '\n\033[36m==> %s\033[0m\n' "$1"; }
fail() { printf '\033[31mXATO: %s\033[0m\n' "$1"; exit 1; }

# 1) Python
step "Python tekshirilmoqda"
command -v python3 >/dev/null || fail "python3 topilmadi: sudo apt install python3 python3-venv"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' \
  || fail "Python $(python3 -V) — kamida 3.12 kerak."
python3 -V

# 2) Virtual muhit va kutubxonalar
step "Virtual muhit va kutubxonalar"
[ -x venv/bin/python ] || python3 -m venv venv || fail "venv yaratib bo'lmadi: sudo apt install python3-venv"
PY=venv/bin/python
$PY -m pip install --upgrade pip --quiet
$PY -m pip install -r requirements.txt --quiet || fail "Kutubxonalarni o'rnatib bo'lmadi (internetni tekshiring)."

# 3) .env
step ".env sozlamalari"
if [ -f .env ]; then
  echo ".env allaqachon bor — o'zgartirilmadi."
else
  read -rp "Server domeni (masalan api.topmost.uz): " DOMAIN
  read -rp "Foydalanuvchilar uchun aloqa (masalan: Telegram @topmost_admin): " CONTACT
  read -rp "Backup papkasi, boshqa diskda bo'lgani yaxshi (Enter — loyiha ichida): " BACKUP_DIR
  SECRET=$($PY -c "from django.core.management.utils import get_random_secret_key as k; print(k())")
  cat > .env <<EOF
# Yaratildi: setup_server.sh ($(date '+%Y-%m-%d %H:%M'))
DEBUG=False
SECRET_KEY=$SECRET
ALLOWED_HOSTS=$DOMAIN,127.0.0.1,localhost
CSRF_TRUSTED_ORIGINS=https://$DOMAIN
# Cloudflare Tunnel / HTTPS ishlagach True qiling va backend'ni qayta yoqing
HTTPS=False
TRUSTED_PROXY=127.0.0.1
SERVE_MEDIA=True
PORT=8000
PRIVACY_CONTACT=$CONTACT
BACKUP_DIR=$BACKUP_DIR
BACKUP_KEEP=14
EOF
  chmod 600 .env
  echo ".env yaratildi (SECRET_KEY avtomatik). Uni hech kimga bermang."
fi

# 4) Baza va fayllar
step "Baza, admin panel fayllari, tarjimalar, boshlang'ich ma'lumotlar"
$PY manage.py migrate --noinput
$PY manage.py collectstatic --noinput -v 0
$PY manage.py compile_translations
$PY manage.py load_initial_data

# 5) Admin
HAS_ADMIN=$($PY manage.py shell -c "from catalog.models import User; print(User.objects.filter(is_superuser=True).exists())" 2>/dev/null | tail -n1)
if [ "$HAS_ADMIN" = "True" ]; then
  echo "Admin allaqachon bor."
else
  step "Admin panel uchun login va parol (username: masalan admin)"
  $PY manage.py createsuperuser
fi

# 6) Tekshiruv
step "Server tekshiruvi"
$PY manage.py check_server
printf '\n\033[32mTayyor. Ishga tushirish:  venv/bin/python serve.py\033[0m\n'
echo "Keyingi qadamlar: DEPLOY.md 6-bo'lim (systemd) va 7.1 (Cloudflare Tunnel)."
