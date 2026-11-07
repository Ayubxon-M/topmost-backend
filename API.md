# TOPMOST API — Flutter uchun qo'llanma

Qo'qondagi ustalar, do'konlar va kafelar e'lonlari uchun backend API.

> **Interaktiv hujjat:** server ishlab turganda brauzerda `{BASE_URL}/api/docs/` ni oching.
> U yerda har bir endpoint'ni to'g'ridan-to'g'ri sinab ko'rish mumkin ("Authorize" tugmasiga `Token <token>` yozing).
> OpenAPI sxemasi (kod generatorlar uchun): `{BASE_URL}/api/schema/`

---

## 1. Umumiy qoidalar

### Base URL

| Qayerdan ulanadi | BASE_URL |
|---|---|
| Android emulyator | `http://10.0.2.2:8000` |
| iOS simulyator | `http://127.0.0.1:8000` |
| Haqiqiy telefon (bir Wi-Fi'da) | `http://<backend kompyuter IP>:8000`, masalan `http://192.168.1.5:8000` |
| Haqiqiy server (ilova chiqarilganda) | `https://...` — server tayyor bo'lgach backend dasturchi beradi |

> `BASE_URL` ni kodda bitta joyda saqlang (masalan `--dart-define=BASE_URL=...`),
> shunda serverga o'tishda faqat shu qiymat almashadi.

> Android'da `http://` (https emas) ishlatish uchun `AndroidManifest.xml` da
> `android:usesCleartextTraffic="true"` kerak (faqat development'da).

### Format
- So'rov va javoblar — **JSON** (`Content-Type: application/json`).
- Faqat rasm yuklash — **multipart/form-data**.
- Sanalar — ISO 8601, Toshkent vaqti: `"2026-11-07T13:02:59.438030+05:00"`.
- Narx — butun son, so'mda (`50000`). Narx ko'rsatilmagan bo'lsa `null`.

### Autentifikatsiya (token)
`register` yoki `login` javobida `token` keladi. Uni saqlab qo'ying (masalan `flutter_secure_storage`)
va kerakli so'rovlarga sarlavha qo'shing:

```
Authorization: Token d3bdbea26ef7eb96510d52f17879b115f3417acd
```

- Token muddatsiz. U faqat `logout` qilganda yoki admin foydalanuvchini bloklaganda ishlamay qoladi.
- Bitta foydalanuvchida bitta token bo'ladi: `logout` uning **barcha qurilmalardan** chiqishini bildiradi.
- Token noto'g'ri yoki bekor bo'lsa — `401`. Bunday holda foydalanuvchini login sahifasiga qaytaring.

### Rollar
| role | Nima qila oladi |
|---|---|
| mehmon (token yo'q) | E'lonlarni va biznes kontaktlarini (telefon, Telegram) ko'rish |
| `client` | Mehmon bilan bir xil + akkaunt (parol, sozlamalar) |
| `business` | Client + biznes profil yaratish, o'z e'lonlarini qo'shish/tahrirlash/o'chirish |

### Sahifalash (pagination)
`/api/listings/` va `/api/listings/mine/` sahifalab qaytadi (har sahifada 20 ta):

```json
{
  "count": 57,
  "next": "http://10.0.2.2:8000/api/listings/?page=2",
  "previous": null,
  "results": [ ... ]
}
```
Keyingi sahifa uchun `next` dagi URL'ni so'rang (`null` bo'lsa — oxirgi sahifa).
Viloyat, shahar, kategoriya ro'yxatlari sahifalanmaydi — oddiy massiv qaytadi.

### Xatolar
| Kod | Ma'nosi |
|---|---|
| `400` | Yuborilgan ma'lumot noto'g'ri. Javobda maydon bo'yicha xatolar bor |
| `401` | Token yo'q yoki noto'g'ri |
| `403` | Ruxsat yo'q (masalan, `client` e'lon qo'shmoqchi) |
| `404` | Topilmadi (yoki begona e'lon) |
| `429` | So'rov juda ko'p (mehmon 60/daqiqa, foydalanuvchi 120/daqiqa). Biroz kutib qayta urining |

`400` javobi shakli — maydon nomi → xatolar ro'yxati:
```json
{ "phone": ["Telefon raqami noto'g'ri. Masalan: +998901234567"] }
```
Bitta maydonga tegishli bo'lmagan xatolar `non_field_errors` yoki `detail` ichida keladi:
```json
{ "non_field_errors": ["Telefon raqami yoki parol noto'g'ri."] }
{ "detail": "Bu amal faqat biznes akkauntlar uchun." }
```

---

## 2. Endpoint'lar ro'yxati

| Metod | URL | Kim | Tavsif |
|---|---|---|---|
| POST | `/api/auth/register/` | hamma | Ro'yxatdan o'tish |
| POST | `/api/auth/login/` | hamma | Kirish |
| POST | `/api/auth/logout/` | token | Chiqish |
| GET | `/api/auth/me/` | token | Joriy foydalanuvchi |
| POST | `/api/auth/change-password/` | token | Parolni o'zgartirish |
| POST | `/api/auth/delete-account/` | token | Akkauntni butunlay o'chirish |
| GET | `/api/regions/` | hamma | Viloyatlar |
| GET | `/api/cities/?region=` | hamma | Shahar/tumanlar |
| GET | `/api/categories/` | hamma | Kategoriyalar |
| GET | `/api/tariffs/` | hamma | Pullik tariflar va narxlari |
| GET | `/api/listings/?city=&category=&region=&q=&page=` | hamma | E'lonlar ro'yxati |
| GET | `/api/listings/{id}/` | hamma | Bitta e'lon |
| GET | `/api/listings/mine/` | business | Mening e'lonlarim (yashirinlari ham) |
| POST | `/api/listings/` | business | E'lon qo'shish |
| PATCH | `/api/listings/{id}/` | business (o'ziniki) | E'lonni tahrirlash |
| DELETE | `/api/listings/{id}/` | business (o'ziniki) | E'lonni o'chirish |
| POST | `/api/listings/{id}/images/` | business (o'ziniki) | Rasm yuklash (multipart) |
| DELETE | `/api/listings/{id}/images/{image_id}/` | business (o'ziniki) | Rasmni o'chirish |
| GET | `/api/business/me/` | business | Mening biznes profilim |
| POST | `/api/business/me/` | business | Biznes profil yaratish |
| PATCH | `/api/business/me/` | business | Biznes profilni tahrirlash |

---

## 3. Autentifikatsiya

### POST `/api/auth/register/`
```json
{ "phone": "+998901234567", "password": "Topmost2026!", "role": "business" }
```
- `phone` — istalgan ko'rinishda: `+998 90 123-45-67`, `998901234567`, `90 123 45 67`. Server o'zi `+998901234567` ga keltiradi.
- `role` — `"client"` (standart) yoki `"business"`.
- Parol: kamida 8 belgi, juda oddiy bo'lmasin, faqat raqamdan iborat bo'lmasin.

**201** javob:
```json
{
  "token": "d3bdbea26ef7eb96510d52f17879b115f3417acd",
  "user": { "id": 1, "phone": "+998901234567", "role": "business", "has_business_profile": false }
}
```
Xatolar: `phone` noto'g'ri yoki band, `password` juda oddiy — `400`.

### POST `/api/auth/login/`
```json
{ "phone": "901234567", "password": "Topmost2026!" }
```
**200** javob — `register` bilan bir xil (`token` + `user`).
Noto'g'ri parol yoki bloklangan foydalanuvchi — `400`:
`{"non_field_errors": ["Telefon raqami yoki parol noto'g'ri."]}`

### POST `/api/auth/logout/`
Token kerak. Body yo'q. **204** (bo'sh javob). Shundan keyin tokenni qurilmadan o'chiring.

### GET `/api/auth/me/`
Token kerak. **200**:
```json
{ "id": 1, "phone": "+998901234567", "role": "business", "has_business_profile": true }
```
> Ilova ochilganda tokenni tekshirish uchun qulay. `role == "business"` va
> `has_business_profile == false` bo'lsa — foydalanuvchini "Biznes profil yaratish" sahifasiga yuboring.

### POST `/api/auth/change-password/`
Token kerak.
```json
{ "old_password": "Topmost2026!", "new_password": "YangiParol2026!" }
```
**200** — `login` bilan bir xil javob (`token` + `user`), lekin **token yangi**.
Eski token ishlamay qoladi (boshqa telefonlardagi kirishlar ham chiqib ketadi),
shuning uchun javobdagi yangi tokenni darhol saqlang.
Xatolar (`400`): `{"old_password": ["Joriy parol noto'g'ri."]}` yoki `{"new_password": ["Parol juda qisqa..."]}`.

### POST `/api/auth/delete-account/`
Token kerak. Tasdiqlash uchun parol so'raladi:
```json
{ "password": "Topmost2026!" }
```
**204** — akkaunt, biznes profil, barcha e'lonlar va rasmlar **butunlay** o'chadi (qaytarib bo'lmaydi).
Keyin tokenni qurilmadan o'chirib, mehmon rejimiga o'ting. Parol noto'g'ri — `400` `{"password": ["Parol noto'g'ri."]}`.

> **Muhim:** App Store va Google Play ro'yxatdan o'tish bor ilovalardan "Akkauntni o'chirish"
> tugmasini talab qiladi. Uni Sozlamalar sahifasiga qo'ying va "Rostdan o'chirilsinmi?" deb so'rang.

---

## 4. Ma'lumotnomalar (ochiq)

### GET `/api/regions/`
```json
[ { "id": 1, "name": "Farg'ona viloyati" } ]
```

### GET `/api/cities/` yoki `/api/cities/?region=1`
```json
[ { "id": 1, "name": "Qo'qon", "region": 1 } ]
```

### GET `/api/categories/`
```json
[ { "id": 1, "name": "Ustalar" } ]
```

### GET `/api/tariffs/`
```json
[ { "id": 1, "name": "Top", "level": 1, "price": 100000, "duration_days": 30 } ]
```
`level: 1` — eng yuqori (e'lonlar ro'yxatda birinchi chiqadi), `level: 2` — undan keyin.
Obunani hozircha admin qo'lda ulaydi (ilova orqali to'lov yo'q). Ilovada tariflarni ko'rsatib,
"Ulash uchun admin bilan bog'laning" tugmasini qo'ying.

---

## 5. E'lonlar

### GET `/api/listings/`
Filtrlar (hammasi ixtiyoriy, birga ishlatish mumkin):

| Parametr | Misol | Tavsif |
|---|---|---|
| `city` | `?city=1` | Shahar/tuman id |
| `category` | `?category=2` | Kategoriya id |
| `region` | `?region=1` | Viloyat id |
| `q` | `?q=santexnik` | Sarlavha va izoh bo'yicha qidiruv. Katta-kichik harf farqi yo'q, `o'` `o‘` `oʻ` bir xil hisoblanadi. Bir nechta so'z — hammasi bo'lishi kerak |
| `page` | `?page=2` | Sahifa raqami |

Tartib serverda belgilanadi: avval pullik tarifli bizneslar (1-daraja, keyin 2-daraja), keyin qolganlari; har guruh ichida yangilari avval.
Yashirilgan, bloklangan e'lonlar va bloklangan bizneslarning e'lonlari ro'yxatga chiqmaydi.

**200** javob (token bo'lsa ham, bo'lmasa ham bir xil):
```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "title": "Santexnik xizmati",
      "description": "Qo'qon bo'ylab, 24/7",
      "price": 50000,
      "is_active": true,
      "is_blocked": false,
      "created_at": "2026-11-07T13:02:59.461119+05:00",
      "updated_at": "2026-11-07T13:02:59.461133+05:00",
      "business": {
        "id": 1,
        "name": "Ali usta",
        "phone": "+998901234567",
        "telegram_username": "aliusta",
        "city": { "id": 1, "name": "Qo'qon", "region": 1 },
        "category": { "id": 1, "name": "Ustalar" }
      },
      "images": [
        { "id": 1, "image": "http://10.0.2.2:8000/media/listings/photo.jpg", "order": 0 }
      ]
    }
  ]
}
```
`telegram_username` — `@` belgisisiz; biznes Telegram yozmagan bo'lsa `""` (bo'sh) — unda Telegram tugmasini yashiring.

> Telegram'ni ochish: `https://t.me/<telegram_username>`. Qo'ng'iroq: `tel:<phone>`.

### GET `/api/listings/{id}/`
Bitta e'lon — `results` ichidagi obyekt bilan bir xil. Yashirilgan/bloklangan bo'lsa — `404`.
Faqat e'lon **egasi** o'zining yashirilgan yoki bloklangan e'lonini ochishi mumkin (tahrirlash sahifasi uchun).

### GET `/api/listings/mine/` (business)
Biznesning o'z e'lonlari, **yashirilgan** (`is_active: false`) va **admin bloklagan** (`is_blocked: true`) e'lonlari ham. Sahifalangan.

### POST `/api/listings/` (business)
Avval biznes profil yaratilgan bo'lishi shart, aks holda `400`.
```json
{ "title": "Santexnik xizmati", "description": "Qo'qon bo'ylab, 24/7", "price": 50000 }
```
| Maydon | Majburiy | Tavsif |
|---|---|---|
| `title` | ha | 200 belgigacha |
| `description` | yo'q | |
| `price` | yo'q | butun son yoki `null` |
| `is_active` | yo'q | standart `true`. `false` — e'lon yashiriladi |

`is_blocked` ni faqat admin o'zgartiradi (yuborilsa ham e'tiborga olinmaydi).
**201** — yaratilgan e'lon obyekti (`images: []`). Keyin rasmlarni alohida yuklang.

### PATCH `/api/listings/{id}/` (business, o'ziniki)
Faqat o'zgargan maydonlarni yuboring:
```json
{ "price": 60000 }
{ "is_active": false }
```
Begona e'lon — `404`.

### DELETE `/api/listings/{id}/` (business, o'ziniki)
**204**. Rasmlari ham o'chadi.

### POST `/api/listings/{id}/images/` (business, o'ziniki)
`multipart/form-data`:
| Maydon | Majburiy | Tavsif |
|---|---|---|
| `image` | ha | rasm fayli (jpg, png, ...) |
| `order` | yo'q | tartib raqami (0, 1, 2...), standart `0` |

Bitta e'longa ko'pi bilan **10 ta** rasm. **201**:
```json
{ "id": 1, "image": "http://10.0.2.2:8000/media/listings/photo.jpg", "order": 0 }
```

### DELETE `/api/listings/{id}/images/{image_id}/` (business, o'ziniki)
**204**.

---

## 6. Biznes profil (faqat `role: business`)

### POST `/api/business/me/` — yaratish (bir marta)
```json
{
  "name": "Ali usta",
  "phone": "+998901234567",
  "telegram_username": "aliusta",
  "city": 1,
  "category": 1
}
```
- `city`, `category` — id (yuqoridagi ma'lumotnomalardan).
- `phone` — normallashtiriladi. `telegram_username` — `@` bo'lsa olib tashlanadi, ixtiyoriy.

**201**:
```json
{ "id": 1, "name": "Ali usta", "phone": "+998901234567", "telegram_username": "aliusta",
  "city": 1, "category": 1, "created_at": "2026-11-07T13:02:59.438030+05:00",
  "subscription": null }
```
Profil allaqachon bor bo'lsa — `400`.

### GET `/api/business/me/`
**200** — yuqoridagi obyekt. Profil hali yo'q bo'lsa — `404`.

`subscription` — hozir amalda bo'lgan obuna (faqat o'qish uchun, uni admin ulaydi). Obuna yo'q bo'lsa `null`:
```json
"subscription": {
  "id": 3,
  "tariff": { "id": 1, "name": "Top", "level": 1, "price": 100000, "duration_days": 30 },
  "start": "2026-11-01T10:00:00+05:00",
  "end": "2026-12-01T10:00:00+05:00"
}
```
> Biznes kabinetida ko'rsating: "Tarif: Top, 1-dekabrgacha". `null` bo'lsa — `GET /api/tariffs/` ro'yxatini taklif qiling.

### PATCH `/api/business/me/`
Faqat o'zgargan maydonlar: `{ "name": "Ali usta (Qo'qon)" }` → **200**.

---

## 7. Dart misollari (`http` paketi)

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

const baseUrl = 'http://10.0.2.2:8000';
String? token; // login'dan keyin saqlanadi

Map<String, String> headers() => {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Token $token',
    };

Future<void> login(String phone, String password) async {
  final res = await http.post(
    Uri.parse('$baseUrl/api/auth/login/'),
    headers: headers(),
    body: jsonEncode({'phone': phone, 'password': password}),
  );
  final data = jsonDecode(utf8.decode(res.bodyBytes)); // o'zbekcha harflar uchun utf8.decode
  if (res.statusCode == 200) {
    token = data['token'];
  } else {
    throw Exception(data); // masalan {"non_field_errors": [...]}
  }
}

Future<List<dynamic>> fetchListings({int? city, int? category, String? q, int page = 1}) async {
  final uri = Uri.parse('$baseUrl/api/listings/').replace(queryParameters: {
    if (city != null) 'city': '$city',
    if (category != null) 'category': '$category',
    if (q != null && q.isNotEmpty) 'q': q,
    'page': '$page',
  });
  final res = await http.get(uri, headers: headers());
  final data = jsonDecode(utf8.decode(res.bodyBytes));
  return data['results'];
}

Future<void> uploadImage(int listingId, String filePath, {int order = 0}) async {
  final req = http.MultipartRequest('POST', Uri.parse('$baseUrl/api/listings/$listingId/images/'))
    ..headers['Authorization'] = 'Token $token'
    ..fields['order'] = '$order'
    ..files.add(await http.MultipartFile.fromPath('image', filePath));
  final res = await req.send();
  if (res.statusCode != 201) {
    throw Exception(await res.stream.bytesToString());
  }
}
```

## 8. Tavsiya etilgan ilova oqimi

1. Ilova ochiladi → token bor bo'lsa `GET /api/auth/me/` (401 bo'lsa tokenni o'chirib, mehmon rejimi).
2. Bosh sahifa → `GET /api/regions/`, `/api/cities/`, `/api/categories/` (filtrlar uchun), `GET /api/listings/`.
3. Ro'yxatdan o'tish → `role: "business"` tanlansa → `POST /api/business/me/` sahifasi.
4. Biznes kabineti → `GET /api/business/me/` (obuna holati), `GET /api/listings/mine/`,
   e'lon qo'shish (`POST /api/listings/`) → rasmlar (`POST .../images/`).
5. Sozlamalar → parolni o'zgartirish (`POST /api/auth/change-password/`), chiqish (`POST /api/auth/logout/`),
   akkauntni o'chirish (`POST /api/auth/delete-account/`).
