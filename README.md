# TOPMOST — backend

Qo'qon va Farg'ona viloyatidagi ustalar, do'konlar, kafelar va boshqa mahalliy bizneslar e'lonlari uchun
mobil ilova (Flutter, `topmost-app`) backendi. Django + Django REST Framework.

- **API qo'llanmasi (Flutter uchun):** [API.md](API.md)
- **Interaktiv hujjat (Swagger):** http://127.0.0.1:8000/api/docs/
- **Admin panel:** http://127.0.0.1:8000/admin/
- **Serverga o'rnatish:** [DEPLOY.md](DEPLOY.md)
- **Maxfiylik siyosati / Foydalanish shartlari:** `/privacy/`, `/terms/`

## Imkoniyatlar

- Ro'yxatdan o'tish va kirish (telefon + parol, token), parolni o'zgartirish, akkauntni o'chirish
- Ikki darajali kategoriyalar (bo'lim → kategoriya), ikonkalar bilan
- Biznes sahifasi: logo, manzil, xaritadagi joy, ish vaqti («hozir ochiq»)
- E'lonlar: rasmlar (10 tagacha), 4 xil narx turi, qidiruv (apostroflar farqi yo'q), filtrlar
- Pullik tariflar: obunasi bor bizneslar ro'yxatda birinchi
- Sevimlilar ❤️, ko'rishlar soni 👁, shikoyatlar ⚠️ (admin bir bosishda bloklaydi)
- Xarita uchun API (koordinatasi bor bizneslar)
- Ikki til: o'zbekcha va ruscha (`Accept-Language: ru`) — admin panel doim o'zbekcha
- Kunlik backup, server tekshiruvi, 107 ta avtomatik test

## Birinchi marta o'rnatish (Windows, PowerShell)

```powershell
python -m venv venv                  # virtual muhit yaratish
venv\Scripts\activate                # uni yoqish (har yangi terminalda)

# Python 3.15 da PyYAML tayyor paketi yo'q, shuning uchun C kompilyatorsiz o'rnatamiz:
$env:PYYAML_FORCE_LIBYAML = "0"
pip install -r requirements.txt --config-settings="pyyaml_build_config={\"without_libyaml\": true}"

python manage.py migrate             # bazani yaratish
python manage.py load_initial_data   # Farg'ona viloyati shaharlari va 46 ta kategoriya (o'zbekcha + ruscha)
python manage.py createsuperuser     # admin login va parol
```

## Har kuni ishga tushirish

```powershell
venv\Scripts\activate
python manage.py runserver
```

Telefon USB orqali ulangan bo'lsa, ilova `127.0.0.1:8000` orqali shu backend'ga ulanadi
(`adb reverse` — ilova yig'ilganda avtomatik, `topmost-app/backend_ulash.bat`).

## Foydali buyruqlar

| Buyruq | Nima qiladi |
|---|---|
| `python manage.py test` | Barcha avtomatik testlar (hammasi `OK` bo'lishi kerak) |
| `python manage.py load_initial_data` | Shaharlar va kategoriyalar; bor narsani takrorlamaydi, bo'sh ruscha nomlarni to'ldiradi |
| `python manage.py backup` | Baza + rasmlar → `backups/topmost-<sana>.zip` |
| `python manage.py check_server` | Server sozlamalari tekshiruvi (✅ / ❌ va nima qilish kerak) |
| `python manage.py compile_translations` | `locale/*/django.po` → `.mo` (tarjimani o'zgartirgandan keyin) |
| `python serve.py` | Serverda ishga tushirish (waitress) — `runserver` emas |

## Admin panelda

1. **Tariflar** qo'shing (1-daraja — eng yuqori, 2-daraja) — narxni o'zingiz belgilaysiz.
2. Biznes to'lov qilganda — **Obunalar** bo'limida obuna qo'shing.
3. **Shikoyatlar** — yangi shikoyatlarni ko'rib, «🔒 E'lonni bloklash» yoki «Asossiz» deb belgilang.
4. **Kategoriyalar** — yangi soha qo'shish uchun kod kerak emas: nom, ruscha nom, bo'lim va ikonka tanlang.
5. Bloklash: **Foydalanuvchilar** yoki **E'lonlar** ro'yxatida belgilab → "Action" → "...bloklash".

## Tuzilma

```
config/              sozlamalar (settings.py, .env dan o'qiydi) va asosiy URL'lar
catalog/
  models.py          jadvallar: User, Region, City, Category, BusinessProfile, Listing, ListingImage,
                     Tariff, Subscription, Favorite, Report
  serializers.py     JSON <-> model, ma'lumotni tekshirish
  views.py           API mantiqi (filtr, qidiruv, tartib, ruxsatlar, ko'rishlar)
  admin.py           admin panel jadvallari; admin_site.py — menyu va bosh sahifa statistikasi
  middleware.py      API tili (Accept-Language)
  management/        buyruqlar: load_initial_data, backup, check_server, compile_translations
  tests.py           avtomatik testlar
locale/              tarjimalar: uz (Django matnlari), ru (bizning xabarlar)
templates/           admin panel dizayni, privacy.html, terms.html
serve.py             serverda ishga tushirish (waitress)
```
