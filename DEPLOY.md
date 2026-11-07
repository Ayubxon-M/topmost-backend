# TOPMOST backend'ni ofis serveriga o'rnatish

Bu qo'llanma backend'ni taxi kompaniya ofisidagi doim yoniq turadigan serverga joylash uchun.
Server **Windows** yoki **Linux** bo'lishi mumkin, har ikkalasi uchun buyruqlar berilgan.

Qisqacha sxema:

```
Telefon (Flutter ilova)  →  Internet  →  ofis routeri  →  server: python serve.py (port 8000)  →  Django
```

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
