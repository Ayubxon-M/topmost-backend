# TOPMOST backend'ni ofis serveriga o'rnatish

Bu qo'llanma backend'ni taxi kompaniya ofisidagi doim yoniq turadigan serverga joylash uchun.
Server **Windows** yoki **Linux** bo'lishi mumkin, har ikkalasi uchun buyruqlar berilgan.

Qisqacha sxema:

```
Telefon (Flutter ilova)  →  Internet (https)  →  Cloudflare Tunnel yoki router  →  server: python serve.py (port 8000)  →  Django
```

## ✅ O'rnatish kuni uchun reja (ustoz bilan, ~2 soat)

| # | Ish | Bo'lim |
|---|---|---|
| 1 | Server qaysi tizimda: Windows yoki Linux? Python 3.12+ bormi? | 2 |
| 2 | Kodni serverga ko'chirish (`git clone`) | 1 |
| 3 | Kutubxonalarni o'rnatish | 2 |
| 4 | `.env` ni to'ldirish (kalit, domen, aloqa) | 3 |
| 5 | Bazani tayyorlash + boshlang'ich ma'lumotlar | 4 |
| 6 | `python serve.py` — ishga tushirib sinash | 5 |
| 7 | Avtomatik ishga tushishni sozlash (server qayta yonganda) | 6 |
| 8 | **Internetdan kirish + HTTPS** (Cloudflare Tunnel yoki router + nginx) | 7 |
| 9 | Kunlik backup | 8 |
| 10 | **`python manage.py check_server`** — hammasi ✅ bo'lishi kerak | 5.1 |
| 11 | Ilovani server manzili bilan yig'ish (RELEASE.md) | 10 |

**Ustozdan oldindan so'rang:** ofisda statik IP bormi? domen bormi (masalan `topmost.uz`)? Cloudflare akkaunti bormi?

### ⚡ Tez yo'l: 2–5-qadamlarni bitta buyruq bajaradi

Kodni serverga ko'chirgach (1-qadam), `topmost-backend` papkasida:

**Windows** (PowerShell):
```powershell
powershell -ExecutionPolicy Bypass -File setup_server.ps1
```
**Linux:**
```bash
bash setup_server.sh
```

Skript: Python'ni tekshiradi → kutubxonalarni o'rnatadi → `.env` yaratadi (maxfiy kalitni o'zi yasaydi,
sizdan faqat **domen** va **aloqa**ni so'raydi) → baza, admin panel fayllari, tarjimalar, shahar va
kategoriyalar → admin login/parol → `check_server` natijasi. Qayta ishga tushirsa bo'ladi — bor narsani buzmaydi.

Skript tugagach — 6-qadam (avtomatik ishga tushish) va 7.1 (Cloudflare Tunnel) qoladi.
Pastdagi 2–5-qadamlar — skript nima qilayotganini tushunish yoki qo'lda bajarish uchun.

---

## 1. Kodni serverga ko'chirish

```bash
git clone https://github.com/Ayubxon-M/topmost-backend.git
cd topmost-backend
```

(GitHub'ga hali chiqmagan bo'lsa, papkani fleshka orqali ko'chirsa ham bo'ladi. Faqat `venv/`,
`db.sqlite3` va `media/` papkalarini **ko'chirmang**: serverda ular yangidan yaratiladi.)

## 2. Python va kutubxonalar

Serverda Python 3.12 yoki undan yangi versiya bo'lishi kerak.

**Windows:**
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
``` 

> Python 3.15 da PyYAML o'rnatishda xato chiqsa, README.md dagi usuldan foydalaning.

## 3. `.env` faylini yaratish (eng muhim qadam)

```bash
copy .env.example .env        # Linux'da: cp .env.example .env
```

Yangi maxfiy kalit yaratib oling:
```bash
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

`.env` ni oching va to'ldiring:
```
DEBUG=False
SECRET_KEY=<yuqoridagi buyruq chiqargan kalit>
ALLOWED_HOSTS=<server manzili: domen yoki IP, masalan api.topmost.uz,192.168.1.50>
CSRF_TRUSTED_ORIGINS=<https://api.topmost.uz>   (HTTPS bo'lmasa: http://192.168.1.50:8000)
PORT=8000
SERVE_MEDIA=True
HTTPS=False      ← SSL sertifikat ulanmaguncha False; ulangandan keyin True
```

> `.env` dagi SECRET_KEY'ni hech kimga bermang va GitHub'ga qo'ymang.

## 4. Bazani tayyorlash

```bash
python manage.py migrate              # bazani yaratish
python manage.py collectstatic        # admin panel CSS/JS fayllarini yig'ish
python manage.py createsuperuser      # admin panel uchun login va parol
python manage.py load_initial_data    # Farg'ona viloyati shahar/tumanlari va kategoriyalar
python manage.py test                 # hammasi OK chiqishi kerak
```

Keyin admin panelda **tariflarni** (nomi, daraja, narx, muddat) o'zingiz qo'shing, chunki narxni
siz belgilaysiz. Boshqa viloyat yoki kategoriya kerak bo'lsa, ularni ham admin paneldan qo'shasiz.

## 5. Ishga tushirish va tekshirish

```bash
python serve.py
```

Serverning o'zida brauzerda oching: `http://127.0.0.1:8000/admin/`. Admin panel dizayn bilan
ochilsa, hammasi joyida. Ofisdagi boshqa kompyuter yoki telefondan oching:
`http://<server IP>:8000/api/categories/`.

> `python manage.py runserver` faqat dasturlash uchun, serverda doim `python serve.py` ishlating.

## 5.1. Avtomatik tekshiruv

```bash
python manage.py check_server
```

Har bir band yonida ✅ (joyida), ⚠️ (tavsiya) yoki ❌ (tuzatish shart) chiqadi, ❌ ostida esa nima qilish
kerakligi yoziladi. **Hamma ❌ yo'qolmaguncha ilovani foydalanuvchilarga chiqarmang.**
HTTPS ulangandan keyin (7-bo'lim) yana bir marta ishga tushiring.

## 6. Server qayta yonganda backend o'zi ishga tushishi

**Windows** (Task Scheduler, ya'ni "Планировщик заданий"):
1. *Create Task* → General: "Run whether user is logged on or not" belgisini qo'ying.
2. Triggers → *At startup*.
3. Actions → Program: `C:\...\topmost-backend\venv\Scripts\python.exe`,
   Arguments: `serve.py`, Start in: `C:\...\topmost-backend`
4. Settings: "If the task fails, restart every 1 minute" belgisini qo'ying.

**Linux** (systemd): `/etc/systemd/system/topmost.service` faylini yarating:
```ini
[Unit]
Description=TOPMOST backend
After=network.target

[Service]
WorkingDirectory=/home/topmost/topmost-backend
ExecStart=/home/topmost/topmost-backend/venv/bin/python serve.py
Restart=always
User=topmost

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable --now topmost
sudo systemctl status topmost       # "active (running)" bo'lishi kerak
```

## 7. Internetdan ulanish (ustoz bilan hal qilinadi)

Flutter ilova foydalanuvchilarning telefonidan, ya'ni ofis tarmog'idan tashqaridan ulanadi.
Shuning uchun serverga internetdan kirish kerak. Ustozingizga quyidagi savollarni bering:

1. **Ofisda doimiy (statik) tashqi IP bormi?** Bo'lsa, routerda port ochiladi
   (port forwarding: tashqi 80/443 → server).
2. **Domen bormi yoki olamizmi?** (masalan `api.topmost.uz`)
3. **HTTPS qanday ulanadi?** Ikki variant bor:
   - **nginx + Let's Encrypt (certbot)**: statik IP va domen bo'lsa. Bu holda `.env` ga
     `TRUSTED_PROXY=127.0.0.1` va `SERVE_MEDIA=False` yoziladi, rasmlarni nginx beradi.
   - **Cloudflare Tunnel**: statik IP bo'lmasa ham ishlaydi, router sozlash shart emas,
     HTTPS'ni o'zi beradi.
4. HTTPS ishlagandan keyin `.env` ichida `HTTPS=True` qiling.

### 7.1. Cloudflare Tunnel — qadamma-qadam (statik IP shart emas, eng oson yo'l)

Tunnel server ichidan Cloudflare'ga **o'zi** ulanadi. Shuning uchun routerda port ochish shart emas,
HTTPS sertifikati esa bepul va avtomatik bo'ladi.

1. **Domen kerak** (masalan `topmost.uz`, yiliga ~10–15$). Domenni https://dash.cloudflare.com ga
   qo'shing (bepul tarif): Cloudflare 2 ta NS manzil beradi, ularni domen sotgan saytda yozasiz.
2. Cloudflare'da: **Zero Trust → Networks → Tunnels → Create a tunnel** → turi *Cloudflared* →
   nomi `topmost`.
3. Sahifada server tizimiga mos o'rnatish buyrug'i chiqadi (Windows yoki Linux). Uni serverda
   **administrator** sifatida bajaring. Tunnel xizmat (service) bo'lib o'rnatiladi va server qayta
   yonganda o'zi ishga tushadi.
4. **Public Hostname** qo'shing:
   - Subdomain: `api`, Domain: `topmost.uz` → manzil `https://api.topmost.uz`
   - Service: `HTTP` → `localhost:8000`
5. `.env` ni yangilang va backend'ni qayta yoqing:
   ```
   ALLOWED_HOSTS=api.topmost.uz
   CSRF_TRUSTED_ORIGINS=https://api.topmost.uz
   HTTPS=True
   TRUSTED_PROXY=127.0.0.1
   SERVE_MEDIA=True
   ```
6. Telefonda (Wi-Fi'ni o'chirib, mobil internetda) brauzerda oching:
   `https://api.topmost.uz/api/categories/` — kategoriyalar ro'yxati chiqsa, hammasi ishlayapti.
7. `python manage.py check_server` — hammasi ✅.

> Telefondan ochilmasa: Cloudflare'da tunnel holati **HEALTHY** ekanini va server'da
> `python serve.py` ishlab turganini tekshiring.

Telefon ilovalari (ayniqsa iOS) oddiy `http://` manzilga ulanishni cheklaydi. Shuning uchun
ilovani foydalanuvchilarga chiqarishdan oldin HTTPS albatta ulangan bo'lishi kerak.

Manzil tayyor bo'lgach, uni Flutter dasturchiga bering: API.md dagi `baseUrl` shu manzilga o'zgartiriladi.

## 8. Zaxira nusxa (backup)

Eng qimmatli fayllar: **`db.sqlite3`** (hamma ma'lumotlar) va **`media/`** (e'lon rasmlari).
Ikkalasini bitta buyruq zip faylga yig'adi:

```bash
python manage.py backup
```

`.env` faylida qayerga saqlanishini va nechta nusxa turishini belgilang. Nusxani **boshqa diskka**
qo'ying: server diski buzilsa ham nusxa qoladi.
```
BACKUP_DIR=D:\topmost-backups        # Linux: /mnt/backup/topmost
BACKUP_KEEP=14                       # oxirgi 14 ta nusxa qoladi, eskilari o'chadi
```

**Har kuni avtomatik ishlashi uchun:**
- **Windows** (Task Scheduler): *Create Task* → Triggers: *Daily*, soat 03:00 →
  Actions: Program `C:\...\topmost-backend\venv\Scripts\python.exe`, Arguments `manage.py backup`,
  Start in `C:\...\topmost-backend`.
- **Linux** (cron): `crontab -e` ni oching va quyidagi qatorni qo'shing:
  ```
  0 3 * * * cd /home/topmost/topmost-backend && venv/bin/python manage.py backup >> backups.log 2>&1
  ```

**Nusxadan qayta tiklash:** backend'ni to'xtating, zip faylni oching, ichidagi `db.sqlite3` va `media/`
papkasini loyiha papkasiga ko'chiring (eskilarining ustidan yozing), keyin backend'ni qayta yoqing.

> Har oyda bir marta nusxadan tiklashni sinab ko'ring. Ochilmaydigan nusxa yo'q nusxa bilan barobar.

## 8.1. Maxfiylik siyosati

`https://<sizning domeningiz>/privacy/` sahifasi tayyor. Bu havolani App Store va Google Play'da
ilova sahifasiga yozasiz. Google Play'dagi "Akkauntni o'chirish" havolasi esa:
`https://<domen>/privacy/#delete`.

`.env` ga foydalanuvchilar bog'lanadigan aloqani yozing, u sahifada ko'rinadi:
```
PRIVACY_CONTACT=Telegram @topmost_admin yoki +998 90 123 45 67
```
> Matnni ([templates/privacy.html](templates/privacy.html)) kompaniya rahbari yoki ustozingiz bilan
> bir o'qib chiqing, kerak bo'lsa o'zgartiring.

## 9. Yangilash (kodga o'zgartirish kiritilganda)

```bash
git pull
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```
Keyin backend'ni qayta ishga tushiring: Windows'da Task Scheduler'da *End* → *Run*,
Linux'da `sudo systemctl restart topmost`.

> Tarjima fayli (`locale/*/django.po`) o'zgargan bo'lsa: `python manage.py compile_translations`.
> Yangi kategoriya/shaharlar qo'shilgan bo'lsa: `python manage.py load_initial_data` (bor narsani takrorlamaydi).

## 10. Ilovani server manziliga ulash

Server `https://` manzil bilan ishlagach, ilova shu manzil bilan yig'iladi (`topmost-app/RELEASE.md`):

```powershell
flutter build appbundle --release --dart-define=BASE_URL=https://api.topmost.uz
```

Sinash uchun telefonga to'g'ridan-to'g'ri o'rnatish (USB'siz ishlaydi):
```powershell
flutter run --release --dart-define=BASE_URL=https://api.topmost.uz
```

Google Play'ga kerak bo'ladigan havolalar:
- Maxfiylik siyosati: `https://api.topmost.uz/privacy/`
- Akkauntni o'chirish: `https://api.topmost.uz/privacy/#delete`
- Foydalanish shartlari: `https://api.topmost.uz/terms/`
