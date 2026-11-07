# TOPMOST — backend

Qo'qondagi ustalar, do'konlar va kafelar e'lonlari uchun mobil ilova (Flutter) backendi.
Django + Django REST Framework.

- **API qo'llanmasi (Flutter uchun):** [API.md](API.md)
- **Interaktiv hujjat:** http://127.0.0.1:8000/api/docs/
- **Admin panel:** http://127.0.0.1:8000/admin/

## Birinchi marta o'rnatish (Windows, PowerShell)

```powershell
python -m venv venv                  # virtual muhit yaratish
venv\Scripts\activate                # uni yoqish (har yangi terminalda)

# Python 3.15 da PyYAML tayyor paketi yo'q, shuning uchun C kompilyatorsiz o'rnatamiz:
$env:PYYAML_FORCE_LIBYAML = "0"
pip install -r requirements.txt --config-settings="pyyaml_build_config={\"without_libyaml\": true}"

python manage.py migrate             # bazani yaratish
python manage.py createsuperuser     # admin (username'ga telefon: +998901234567)
```

## Har kuni ishga tushirish

```powershell
venv\Scripts\activate
python manage.py runserver 0.0.0.0:8000
```

`0.0.0.0` — server emulyator va bir Wi-Fi'dagi telefonlardan ham ochiladi.
Kompyuter IP manzilini bilish: `ipconfig` → "IPv4 Address" (masalan `192.168.1.5`).
Telefon ulana olmasa — Windows Firewall'da Python'ga "Private network" ruxsatini bering.

## Ishga tushirgandan keyin admin panelda

1. **Viloyatlar**, **Shaharlar / tumanlar**, **Kategoriyalar** ni kiriting — ularsiz biznes profil yaratib bo'lmaydi.
2. **Tariflar** (1-daraja — eng yuqori, 2-daraja) kiriting.
3. Biznes to'lov qilganda — **Obunalar** bo'limida obuna qo'shing (tugash sanasi bo'sh qoldirilsa, tarif muddatidan hisoblanadi).
4. Bloklash: **Foydalanuvchilar** yoki **E'lonlar** ro'yxatida belgilab → "Action" → "...bloklash".

## Tuzilma

```
config/            sozlamalar (settings.py) va asosiy URL'lar
catalog/
  models.py        jadvallar: User, Region, City, Category, BusinessProfile,
                   Listing, ListingImage, Tariff, Subscription
  admin.py         admin panel
  serializers.py   JSON <-> model, ma'lumotni tekshirish
  views.py         API mantiqi (filtr, qidiruv, tartib, ruxsatlar)
  permissions.py   kim nima qila oladi
  urls.py          /api/... yo'llari
  utils.py         telefon va apostroflarni normallashtirish
```

## Hali qilinmagan (keyingi bosqich)

- Production sozlamalari: `SECRET_KEY` va `DEBUG` ni `.env` ga olib chiqish, `ALLOWED_HOSTS`, CORS, serverga deploy
- Avtomatik testlar

## Serverga o'rnatish

Ofis serveriga joylash bo'yicha qadamma-qadam qo'llanma: [DEPLOY.md](DEPLOY.md)
