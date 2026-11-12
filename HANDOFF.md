# TOPMOST — loyiha holati (yangi kompyuterda davom ettirish uchun)

> Yangi kompyuterda Claude'ga birinchi xabarda: **"HANDOFF.md ni o'qib, loyihani davom ettiramiz"** deb yozing.

## Loyiha nima
Qo'qon va Farg'ona viloyatidagi ustalar, do'konlar, kafelar va boshqa mahalliy bizneslar e'lonlari ilovasi.
- **Backend:** `github.com/Ayubxon-M/topmost-backend` — Django + DRF, SQLite, admin panel (o'zbekcha).
- **Ilova:** `github.com/Ayubxon-M/topmost-app` — Flutter (Android/iOS).
- **Server:** taxi kompaniyasi ofisidagi doim yoniq server (ustoz bilan o'rnatiladi) — `DEPLOY.md`.
- Dastlab ilovani do'st (Flutter dasturchi) yozishi kerak edi; endi biz o'zimiz yozdik.

## Ish uslubi (muhim)
- Men dasturlashni o'rganyapman — hammasini **o'zbekcha, sodda** tushuntiring.
- Har bir qadamdan keyin **commit**; nima o'zgarganini va qanday sinashni ayting.
- GitHub'ga **push qilishdan oldin so'rang**.
- So'ralgan tartibni chalkashtirmang; dizayn bo'yicha yangi narsa qilishdan oldin mendan so'rang.

## Dizayn qarorlari
- Ranglar: to'q chuqur ko'k (`#0B2545`) + sian/moviy (`#06B6D4`). Qorong'i fon: `#0F172A` (sof qora emas).
- Bosh sahifa: 2 ustunli kartalar (kvadrat rasm, sarlavha, qalin narx, tuman, 📞 / ✈️ tugmalar).
- Pastki menyu: Telegram iOS uslubidagi "suyuq" (suriladigan) menyu — Bosh sahifa, Xarita, Kabinet, Profil.
- Logo: **B variant** — xarita belgisi ichida yulduz (`topmost-app/assets/logo_variants/`).
- Biznes kontaktlari (telefon, Telegram) **hammaga ochiq** (mehmonga ham).
- Ikki til: o'zbekcha (asosiy) va ruscha. Admin panel doim o'zbekcha.

## Tayyor
Backend (109 test) va ilova (30 test) — to'liq: kirish/ro'yxat, kategoriyalar (2 daraja), biznes sahifasi
(logo, manzil, GPS, ish vaqti), e'lonlar (10 rasm, 4 narx turi, kichik nusxalar), qidiruv/filtrlar, xarita
(OpenStreetMap), sevimlilar, ko'rishlar soni, shikoyatlar (admin bloklaydi), maxfiylik/shartlar sahifalari,
rus tili, backup, `check_server`, avtomatik o'rnatish skriptlari, GitHub Actions testlari.
Google Play matnlari va rasmlari: `topmost-app/STORE_LISTING.md`, `assets/store/`.

## Qolgan ishlar (navbat bilan)
1. **Deploy** (ustoz bilan): `DEPLOY.md` → `setup_server.ps1` / `.sh` → Cloudflare Tunnel → `check_server`.
2. Server manzili tayyor bo'lgach: ilovani `--dart-define=BASE_URL=https://...` bilan yig'ish, telefonda sinash.
3. Imzo kaliti (`topmost-app/RELEASE.md`) — parolni o'zim yarataman va saqlayman.
4. Google Play Console (25$, kompaniya nomidan) → ichki sinov → hammaga.
5. Keyinroq: yangilash skripti (`update_server`), kerak bo'lsa PostgreSQL/MySQL, baho va sharhlar,
   Payme/Click to'lov, push xabarnomalar.

## Yangi kompyuterni sozlash
1. Git, Python 3.12+, Flutter SDK, Android Studio o'rnating.
2. `git clone` ikkala repo'ni ham `Documents` papkasiga.
3. Backend: `README.md` → "Birinchi marta o'rnatish" (`venv`, `pip install`, `migrate`, `load_initial_data`,
   `createsuperuser`).
4. Ilova: `flutter pub get` → Android Studio'da ochish → telefon USB orqali → ▶ Run (`README.md`).

## Texnik eslatmalar
- Python 3.15 da PyYAML tayyor paketi yo'q — README'dagi `--config-settings` usuli bilan o'rnating.
- Telefon kompyuterdagi backend'ga `adb reverse tcp:8000 tcp:8000` orqali ulanadi (build'da avtomatik).
- OpenStreetMap xarita serveri katta trafik uchun emas — foydalanuvchilar ko'payganda boshqa xarita
  provayderiga o'tish kerak (kodda 1 qator).
- Lokal `db.sqlite3` dagi ma'lumotlar faqat sinov uchun — serverga ko'chirilmaydi.
