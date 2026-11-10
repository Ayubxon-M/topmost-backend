"""
Avtomatik testlar. Ishga tushirish:  python manage.py test

Testlar alohida, vaqtinchalik bazada ishlaydi — sizning db.sqlite3 ga tegmaydi.
Har bir test_... funksiyasi bitta qoidani tekshiradi. Biror narsa buzilsa,
qaysi test "FAIL" bo'lganiga qarab muammoni topasiz.
"""
import os
import shutil
import tempfile
from pathlib import Path
from unittest import mock
from datetime import timedelta
from io import BytesIO, StringIO

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from .models import BusinessProfile, Category, City, Listing, ListingImage, Region, Report, Subscription, Tariff, User
from .utils import normalize_phone, normalize_text

PASSWORD = "Topmost2026!"
TEMP_MEDIA = tempfile.mkdtemp()  # test rasmlari shu yerga yoziladi, keyin o'chiriladi


def make_image(name="photo.png"):
    buf = BytesIO()
    Image.new("RGB", (10, 10), "teal").save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


class BaseAPITest(TestCase):
    """Hamma testlar uchun umumiy tayyorgarlik: viloyat, shaharlar, kategoriyalar."""

    @classmethod
    def setUpTestData(cls):
        cls.region = Region.objects.create(name="Farg'ona viloyati")
        cls.qoqon = City.objects.create(region=cls.region, name="Qo'qon")
        cls.fargona = City.objects.create(region=cls.region, name="Farg'ona")
        cls.usta = Category.objects.create(name="Ustalar")
        cls.kafe = Category.objects.create(name="Kafelar")

    def setUp(self):
        cache.clear()  # throttling hisoblagichini tozalash
        self.anon = APIClient()

    # --- yordamchilar ---

    def client_for(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c

    def make_business(self, phone, name="Biznes", city=None, category=None):
        user = User.objects.create_user(phone, password=PASSWORD, role=User.Role.BUSINESS)
        profile = BusinessProfile.objects.create(
            user=user, name=name, phone=phone, telegram_username="tg_" + phone[-4:],
            city=city or self.qoqon, category=category or self.usta,
        )
        return user, profile


# =====================================================================
# Yordamchi funksiyalar
# =====================================================================

class UtilsTests(TestCase):
    def test_normalize_phone(self):
        for raw in ["+998 90 123-45-67", "998901234567", "90 123 45 67", "(90) 1234567"]:
            self.assertEqual(normalize_phone(raw), "+998901234567", raw)

    def test_normalize_phone_invalid(self):
        for raw in ["", None, "123", "+7 999 123 45 67", "9989012345678"]:
            self.assertIsNone(normalize_phone(raw), raw)

    def test_normalize_text_apostrophes(self):
        variants = ["O'zbek", "O‘zbek", "Oʻzbek", "Oʼzbek", "O’zbek", "O`zbek"]
        self.assertEqual({normalize_text(v) for v in variants}, {"o'zbek"})


# =====================================================================
# Ro'yxatdan o'tish, kirish, chiqish
# =====================================================================

class AuthTests(BaseAPITest):
    def register(self, **data):
        payload = {"phone": "90 111 22 33", "password": PASSWORD, "role": "business", **data}
        return self.anon.post("/api/auth/register/", payload, format="json")

    def test_register_normalizes_phone_and_returns_token(self):
        r = self.register()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["user"]["phone"], "+998901112233")
        self.assertEqual(r.data["user"]["role"], "business")
        self.assertTrue(r.data["token"])

    def test_register_default_role_is_client(self):
        r = self.anon.post("/api/auth/register/", {"phone": "901112233", "password": PASSWORD}, format="json")
        self.assertEqual(r.data["user"]["role"], "client")

    def test_register_duplicate_phone(self):
        self.register()
        r = self.register(phone="+998901112233")
        self.assertEqual(r.status_code, 400)
        self.assertIn("phone", r.data)

    def test_register_bad_phone(self):
        r = self.register(phone="12345")
        self.assertEqual(r.status_code, 400)
        self.assertIn("phone", r.data)

    def test_register_weak_password_errors_in_uzbek(self):
        r = self.register(password="12345")
        self.assertEqual(r.status_code, 400)
        self.assertIn("password", r.data)
        self.assertIn("Parol juda qisqa", " ".join(r.data["password"]))

    def test_login_with_any_phone_format(self):
        self.register()
        r = self.anon.post("/api/auth/login/", {"phone": "998901112233", "password": PASSWORD}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["token"])

    def test_login_wrong_password(self):
        self.register()
        r = self.anon.post("/api/auth/login/", {"phone": "901112233", "password": "xato"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_blocked_user_cannot_login_and_token_stops_working(self):
        token = self.register().data["token"]
        User.objects.filter(username="+998901112233").update(is_active=False)
        r = self.anon.post("/api/auth/login/", {"phone": "901112233", "password": PASSWORD}, format="json")
        self.assertEqual(r.status_code, 400)
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION="Token " + token)
        self.assertEqual(c.get("/api/auth/me/").status_code, 401)

    def test_me_and_logout(self):
        token = self.register().data["token"]
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION="Token " + token)
        me = c.get("/api/auth/me/")
        self.assertEqual(me.status_code, 200)
        self.assertFalse(me.data["has_business_profile"])
        self.assertEqual(c.post("/api/auth/logout/").status_code, 204)
        self.assertEqual(c.get("/api/auth/me/").status_code, 401)

    def authed(self, token):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION="Token " + token)
        return c

    def test_change_password(self):
        old_token = self.register().data["token"]
        c = self.authed(old_token)
        r = c.post("/api/auth/change-password/", {"old_password": PASSWORD, "new_password": "Yangi2026Parol!"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertNotEqual(r.data["token"], old_token)
        self.assertEqual(c.get("/api/auth/me/").status_code, 401)  # eski token o'chdi
        self.assertEqual(self.authed(r.data["token"]).get("/api/auth/me/").status_code, 200)
        login = self.anon.post("/api/auth/login/", {"phone": "901112233", "password": "Yangi2026Parol!"}, format="json")
        self.assertEqual(login.status_code, 200)

    def test_change_password_wrong_old_and_weak_new(self):
        c = self.authed(self.register().data["token"])
        r = c.post("/api/auth/change-password/", {"old_password": "xato", "new_password": "Yangi2026Parol!"}, format="json")
        self.assertIn("old_password", r.data)
        r = c.post("/api/auth/change-password/", {"old_password": PASSWORD, "new_password": "123"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("new_password", r.data)

    @override_settings(MEDIA_ROOT=TEMP_MEDIA)
    def test_delete_account_removes_everything(self):
        user, biz = self.make_business("+998901000007", "O'chadigan")
        listing = Listing.objects.create(business=biz, title="E'lon")
        c = self.client_for(user)
        img_id = c.post(f"/api/listings/{listing.pk}/images/", {"image": make_image()}, format="multipart").data["id"]
        path = ListingImage.objects.get(pk=img_id).image.path
        self.assertEqual(c.post("/api/auth/delete-account/", {"password": "xato"}, format="json").status_code, 400)
        self.assertEqual(c.post("/api/auth/delete-account/", {"password": PASSWORD}, format="json").status_code, 204)
        self.assertFalse(User.objects.filter(pk=user.pk).exists())
        self.assertFalse(Listing.objects.filter(pk=listing.pk).exists())
        self.assertFalse(os.path.exists(path))  # rasm fayli ham o'chdi

    def test_admin_cannot_delete_self_via_api(self):
        admin = User.objects.create_superuser("+998900000000", password=PASSWORD)
        r = self.client_for(admin).post("/api/auth/delete-account/", {"password": PASSWORD}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertTrue(User.objects.filter(pk=admin.pk).exists())

    def test_me_requires_token(self):
        r = self.anon.get("/api/auth/me/")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.data["detail"], "Tizimga kirilmagan: token yuborilmadi.")


# =====================================================================
# Ma'lumotnomalar
# =====================================================================

class ReferenceTests(BaseAPITest):
    def test_lists_are_public(self):
        self.assertEqual(len(self.anon.get("/api/regions/").data), 1)
        self.assertEqual(len(self.anon.get("/api/categories/").data), 2)
        self.assertEqual(len(self.anon.get("/api/cities/").data), 2)

    def test_tariffs_public(self):
        Tariff.objects.create(name="Standart", level=2, price=50000, duration_days=30)
        Tariff.objects.create(name="Top", level=1, price=100000, duration_days=30)
        r = self.anon.get("/api/tariffs/")
        self.assertEqual([t["name"] for t in r.data], ["Top", "Standart"])
        self.assertEqual(r.data[0]["price"], 100000)

    def test_cities_filter_by_region(self):
        other = Region.objects.create(name="Toshkent")
        City.objects.create(region=other, name="Chilonzor")
        self.assertEqual(len(self.anon.get(f"/api/cities/?region={self.region.pk}").data), 2)
        self.assertEqual(len(self.anon.get(f"/api/cities/?region={other.pk}").data), 1)

    def test_read_only(self):
        self.assertIn(self.anon.post("/api/regions/", {"name": "x"}).status_code, (401, 403, 405))
        admin = User.objects.create_superuser("+998900000000", password=PASSWORD)
        self.assertEqual(self.client_for(admin).post("/api/regions/", {"name": "x"}).status_code, 405)


# =====================================================================
# Biznes profil
# =====================================================================

@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class BusinessPageTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.user, self.biz = self.make_business("+998901000001", "Ali usta")
        self.api = self.client_for(self.user)

    def at(self, weekday, hour, minute=0):
        """2026-11-09 — dushanba. weekday: 1=dushanba ... 7=yakshanba."""
        from datetime import datetime
        from zoneinfo import ZoneInfo
        return datetime(2026, 11, 8 + weekday, hour, minute, tzinfo=ZoneInfo("Asia/Tashkent"))

    def test_open_hours_regular_day(self):
        from datetime import time
        self.biz.opens_at, self.biz.closes_at, self.biz.work_days = time(9), time(18), "123456"
        self.assertTrue(self.biz.is_open_at(self.at(1, 9)))
        self.assertTrue(self.biz.is_open_at(self.at(6, 17, 59)))
        self.assertFalse(self.biz.is_open_at(self.at(1, 18)))
        self.assertFalse(self.biz.is_open_at(self.at(1, 8, 59)))
        self.assertFalse(self.biz.is_open_at(self.at(7, 12)))  # yakshanba — dam olish

    def test_open_hours_overnight(self):
        from datetime import time
        self.biz.opens_at, self.biz.closes_at, self.biz.work_days = time(18), time(2), "5"  # faqat juma kechasi
        self.assertTrue(self.biz.is_open_at(self.at(5, 23)))
        self.assertTrue(self.biz.is_open_at(self.at(6, 1, 30)))  # shanba tongi — juma kechasining davomi
        self.assertFalse(self.biz.is_open_at(self.at(6, 2)))
        self.assertFalse(self.biz.is_open_at(self.at(5, 1)))  # juma tongi — payshanba ishlamaydi

    def test_open_hours_unknown_and_24_7(self):
        self.assertIsNone(self.biz.is_open_at(self.at(1, 12)))
        self.biz.is_24_7 = True
        self.assertTrue(self.biz.is_open_at(self.at(7, 3)))

    def test_update_page_fields(self):
        r = self.api.patch("/api/business/me/", {
            "description": "20 yillik tajriba", "address": "Turkiston ko'chasi 12",
            "latitude": 40.5286, "longitude": 70.9425, "work_days": "654321",
            "opens_at": "09:00", "closes_at": "18:00",
        }, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["work_days"], "123456")  # tartiblandi
        self.assertEqual(r.data["latitude"], 40.5286)
        self.assertIn(r.data["is_open_now"], (True, False))

    def test_validation(self):
        bad = [
            {"latitude": 40.5},                               # uzunliksiz
            {"latitude": 140, "longitude": 70},               # noto'g'ri koordinata
            {"opens_at": "09:00"},                            # yopilish vaqtisiz
            {"opens_at": "09:00", "closes_at": "09:00"},      # bir xil
            {"work_days": "1238"},                            # 8-kun yo'q
        ]
        for data in bad:
            self.assertEqual(self.api.patch("/api/business/me/", data, format="json").status_code, 400, data)

    def test_logo_upload_replace_delete(self):
        import os
        r = self.api.post("/api/business/me/logo/", {"logo": make_image("a.png")}, format="multipart")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["logo"].startswith("http://testserver/media/logos/"))
        first = BusinessProfile.objects.get(pk=self.biz.pk).logo.path
        self.api.post("/api/business/me/logo/", {"logo": make_image("b.png")}, format="multipart")
        self.assertFalse(os.path.exists(first))  # eski logo o'chirildi
        self.assertEqual(self.api.delete("/api/business/me/logo/").status_code, 204)
        self.assertFalse(BusinessProfile.objects.get(pk=self.biz.pk).logo)
        bad = SimpleUploadedFile("x.png", b"rasm emas", content_type="image/png")
        self.assertEqual(self.api.post("/api/business/me/logo/", {"logo": bad}, format="multipart").status_code, 400)

    def test_logo_not_writable_via_patch(self):
        r = self.api.patch("/api/business/me/", {"logo": "hack.png"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(BusinessProfile.objects.get(pk=self.biz.pk).logo)

    def test_public_business_page_and_its_listings(self):
        Listing.objects.create(business=self.biz, title="Quvur")
        _, other = self.make_business("+998901000002", "Boshqa")
        Listing.objects.create(business=other, title="Begona")
        r = self.anon.get(f"/api/businesses/{self.biz.pk}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["name"], "Ali usta")
        self.assertEqual(r.data["phone"], "+998901000001")
        self.assertIn("is_open_now", r.data)
        titles = [x["title"] for x in self.anon.get(f"/api/listings/?business={self.biz.pk}").data["results"]]
        self.assertEqual(titles, ["Quvur"])
        # Listing ichidagi biznesda ham sahifa maydonlari bor
        self.assertIn("address", self.anon.get("/api/listings/").data["results"][0]["business"])

    def test_blocked_business_page_hidden(self):
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(self.anon.get(f"/api/businesses/{self.biz.pk}/").status_code, 404)

class LanguageTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        Category.objects.filter(pk=self.usta.pk).update(name_ru="Мастера")
        City.objects.filter(pk=self.qoqon.pk).update(name_ru="Коканд")

    def names(self, path, lang=None):
        headers = {"HTTP_ACCEPT_LANGUAGE": lang} if lang else {}
        return {x["name"] for x in self.anon.get(path, **headers).data}

    def test_russian_names(self):
        self.assertIn("Мастера", self.names("/api/categories/", "ru-RU,ru;q=0.9"))
        self.assertIn("Kafelar", self.names("/api/categories/", "ru"))  # ruscha yo'q — o'zbekchasi
        self.assertIn("Коканд", self.names("/api/cities/", "ru"))

    def test_uzbek_by_default_and_unknown_language(self):
        self.assertIn("Ustalar", self.names("/api/categories/"))
        self.assertIn("Ustalar", self.names("/api/categories/", "en-US"))

    def test_nested_names_in_listing(self):
        _, biz = self.make_business("+998901000001")
        Listing.objects.create(business=biz, title="E'lon")
        b = self.anon.get("/api/listings/", HTTP_ACCEPT_LANGUAGE="ru").data["results"][0]["business"]
        self.assertEqual((b["city"]["name"], b["category"]["name"]), ("Коканд", "Мастера"))

    def test_error_messages_in_russian(self):
        r = self.anon.post("/api/auth/login/", {"phone": "901112233", "password": "x"}, format="json",
                           HTTP_ACCEPT_LANGUAGE="ru")
        self.assertEqual(r.data["non_field_errors"], ["Неверный номер телефона или пароль."])
        r = self.anon.post("/api/auth/register/", {"phone": "123", "password": "x"}, format="json",
                           HTTP_ACCEPT_LANGUAGE="ru")
        self.assertIn("Неверный номер телефона", str(r.data["phone"]))
        # Django/DRF o'z xabarlari ham ruscha
        r = self.anon.get("/api/listings/99999/", HTTP_ACCEPT_LANGUAGE="ru")
        self.assertEqual(r.data["detail"], "Страница не найдена.")  # DRF o'zining ruscha tarjimasi
        r = self.anon.get("/api/listings/?city=abc", HTTP_ACCEPT_LANGUAGE="ru")
        self.assertEqual(r.data["city"], ["Должно быть целым числом."])

    def test_error_messages_uzbek_by_default(self):
        r = self.anon.post("/api/auth/login/", {"phone": "901112233", "password": "x"}, format="json")
        self.assertEqual(r.data["non_field_errors"], ["Telefon raqami yoki parol noto'g'ri."])

    def test_admin_stays_uzbek(self):
        admin_user = User.objects.create_superuser("admin", password=PASSWORD)
        self.client.force_login(admin_user)
        r = self.client.get("/admin/", HTTP_ACCEPT_LANGUAGE="ru")
        self.assertContains(r, "Boshqaruv paneli")
        self.assertEqual(r.headers["Content-Language"], "uz")

class ViewsCountTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.owner, self.biz = self.make_business("+998901000001")
        self.listing = Listing.objects.create(business=self.biz, title="E'lon")
        self.url = f"/api/listings/{self.listing.pk}/"

    def views(self):
        return Listing.objects.get(pk=self.listing.pk).views_count

    def test_one_view_per_person_per_day(self):
        u1 = self.client_for(User.objects.create_user("+998901000008", password=PASSWORD))
        u2 = self.client_for(User.objects.create_user("+998901000009", password=PASSWORD))
        self.assertEqual(u1.get(self.url).data["views_count"], 1)
        u1.get(self.url)  # takroriy — sanalmaydi
        u2.get(self.url)
        self.anon.get(self.url)  # mehmon — IP bo'yicha
        self.anon.get(self.url)
        self.assertEqual(self.views(), 3)

    def test_owner_not_counted_and_list_does_not_count(self):
        self.client_for(self.owner).get(self.url)
        self.anon.get("/api/listings/")
        self.assertEqual(self.views(), 0)

    def test_mine_shows_favorites_count(self):
        from .models import Favorite
        for phone in ("+998901000008", "+998901000009"):
            Favorite.objects.create(user=User.objects.create_user(phone, password=PASSWORD), listing=self.listing)
        item = self.client_for(self.owner).get("/api/listings/mine/").data["results"][0]
        self.assertEqual(item["favorites_count"], 2)
        self.assertIsNone(self.anon.get(self.url).data["favorites_count"])  # boshqalarga ko'rinmaydi

    def test_views_count_not_writable(self):
        r = self.client_for(self.owner).patch(self.url, {"views_count": 9999}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.views(), 0)

class ReportTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.owner, self.biz = self.make_business("+998901000001")
        self.listing = Listing.objects.create(business=self.biz, title="Shubhali e'lon")
        self.user = User.objects.create_user("+998901000009", password=PASSWORD)
        self.api = self.client_for(self.user)
        self.url = f"/api/listings/{self.listing.pk}/report/"

    def test_report_and_repeat_updates(self):
        r = self.api.post(self.url, {"reason": "fraud", "comment": "Pul oldi, kelmadi"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.api.post(self.url, {"reason": "spam"}, format="json")  # qayta — yangilanadi, ikkinchisi qo'shilmaydi
        self.assertEqual(Report.objects.count(), 1)
        self.assertEqual(Report.objects.get().reason, "spam")

    def test_validation_and_permissions(self):
        self.assertEqual(self.api.post(self.url, {"reason": "yoqmadi"}, format="json").status_code, 400)
        self.assertEqual(self.anon.post(self.url, {"reason": "spam"}, format="json").status_code, 401)
        own = self.client_for(self.owner).post(self.url, {"reason": "spam"}, format="json")
        self.assertEqual(own.status_code, 400)  # o'z e'loni
        Listing.objects.filter(pk=self.listing.pk).update(is_blocked=True)
        self.assertEqual(self.api.post(self.url, {"reason": "spam"}, format="json").status_code, 404)

    def test_admin_block_action_and_pages(self):
        self.api.post(self.url, {"reason": "fraud"}, format="json")
        other = User.objects.create_user("+998901000008", password=PASSWORD)
        self.client_for(other).post(self.url, {"reason": "spam"}, format="json")
        admin_user = User.objects.create_superuser("admin", password=PASSWORD)
        self.client.force_login(admin_user)
        report = Report.objects.first()
        for page in ["/admin/catalog/report/", f"/admin/catalog/report/{report.pk}/change/", "/admin/catalog/listing/", "/admin/"]:
            self.assertEqual(self.client.get(page).status_code, 200, page)
        self.assertContains(self.client.get("/admin/"), "Yangi shikoyatlar")
        self.client.post("/admin/catalog/report/", {"action": "block_reported_listings", "_selected_action": [report.pk]})
        self.listing.refresh_from_db()
        self.assertTrue(self.listing.is_blocked)
        # Shu e'lonning ikkala shikoyati ham yopildi
        self.assertEqual(set(Report.objects.values_list("status", flat=True)), {"resolved"})

class MapTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.santexnik = Category.objects.create(name="Santexnik", parent=self.usta)
        self.u1, self.on_map = self.make_business("+998901000001", "Xaritada", category=self.santexnik)
        BusinessProfile.objects.filter(pk=self.on_map.pk).update(latitude=40.53, longitude=70.94)
        _, self.no_coords = self.make_business("+998901000002", "Koordinatasiz")
        _, self.cafe = self.make_business("+998901000003", "Kafe", city=self.fargona, category=self.kafe)
        BusinessProfile.objects.filter(pk=self.cafe.pk).update(latitude=40.38, longitude=71.78)
        Listing.objects.create(business=self.on_map, title="Ko'rinadi")
        Listing.objects.create(business=self.on_map, title="Yashirin", is_active=False)

    def names(self, q=""):
        r = self.anon.get("/api/businesses/" + q)
        self.assertEqual(r.status_code, 200)
        return sorted(b["name"] for b in r.data)

    def test_only_with_coordinates_not_paginated(self):
        self.assertEqual(self.names(), ["Kafe", "Xaritada"])
        item = next(b for b in self.anon.get("/api/businesses/").data if b["name"] == "Xaritada")
        self.assertEqual((item["latitude"], item["longitude"]), (40.53, 70.94))
        self.assertEqual(item["listings_count"], 1)  # yashirin e'lon sanalmaydi

    def test_filters(self):
        self.assertEqual(self.names(f"?category={self.usta.pk}"), ["Xaritada"])  # bo'lim — ichidagilar bilan
        self.assertEqual(self.names(f"?city={self.fargona.pk}"), ["Kafe"])

    def test_blocked_hidden(self):
        User.objects.filter(pk=self.u1.pk).update(is_active=False)
        self.assertEqual(self.names(), ["Kafe"])

class PriceTypeTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.user, self.biz = self.make_business("+998901000001")
        self.api = self.client_for(self.user)

    def create(self, **data):
        return self.api.post("/api/listings/", {"title": "Xizmat", **data}, format="json")

    def test_types(self):
        self.assertEqual(self.create(price_type="fixed", price=150000).data["price"], 150000)
        r = self.create(price_type="from", price=50000)
        self.assertEqual((r.data["price_type"], r.data["price"]), ("from", 50000))
        r = self.create(price_type="free", price=999)  # bepulda narx saqlanmaydi
        self.assertEqual((r.data["price_type"], r.data["price"]), ("free", None))
        self.assertEqual(self.create().data["price_type"], "negotiable")  # standart

    def test_priced_types_require_price(self):
        for t in ("fixed", "from"):
            r = self.create(price_type=t)
            self.assertEqual(r.status_code, 400, t)
            self.assertIn("price", r.data)
        self.assertEqual(self.create(price_type="cheap").status_code, 400)

    def test_old_app_sending_only_price_gets_fixed(self):
        self.assertEqual(self.create(price=1000).data["price_type"], "fixed")

    def test_switch_to_negotiable_clears_price(self):
        listing_id = self.create(price_type="fixed", price=1000).data["id"]
        r = self.api.patch(f"/api/listings/{listing_id}/", {"price_type": "negotiable"}, format="json")
        self.assertIsNone(r.data["price"])
        r = self.api.patch(f"/api/listings/{listing_id}/", {"price_type": "fixed"}, format="json")
        self.assertEqual(r.status_code, 400)  # narxsiz "aniq narx" bo'lmaydi

class FavoriteTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        _, self.biz = self.make_business("+998901000001")
        self.l1 = Listing.objects.create(business=self.biz, title="Birinchi")
        self.l2 = Listing.objects.create(business=self.biz, title="Ikkinchi")
        self.client_user = User.objects.create_user("+998901000009", password=PASSWORD)
        self.api = self.client_for(self.client_user)

    def fav(self, listing, method="post"):
        return getattr(self.api, method)(f"/api/listings/{listing.pk}/favorite/")

    def test_add_list_remove(self):
        self.assertEqual(self.fav(self.l1).status_code, 201)
        self.assertEqual(self.fav(self.l1).status_code, 200)  # takroriy — xato emas
        self.fav(self.l2)
        r = self.api.get("/api/listings/favorites/")
        self.assertEqual([x["title"] for x in r.data["results"]], ["Ikkinchi", "Birinchi"])  # oxirgisi birinchi
        self.assertTrue(all(x["is_favorite"] for x in r.data["results"]))
        self.assertEqual(self.fav(self.l1, "delete").status_code, 204)
        self.assertEqual(self.api.get("/api/listings/favorites/").data["count"], 1)

    def test_is_favorite_flag_in_list_and_detail(self):
        self.fav(self.l1)
        flags = {x["title"]: x["is_favorite"] for x in self.api.get("/api/listings/").data["results"]}
        self.assertEqual(flags, {"Birinchi": True, "Ikkinchi": False})
        self.assertTrue(self.api.get(f"/api/listings/{self.l1.pk}/").data["is_favorite"])
        self.assertFalse(self.anon.get(f"/api/listings/{self.l1.pk}/").data["is_favorite"])  # mehmon

    def test_guest_cannot_favorite(self):
        self.assertEqual(self.anon.post(f"/api/listings/{self.l1.pk}/favorite/").status_code, 401)
        self.assertEqual(self.anon.get("/api/listings/favorites/").status_code, 401)

    def test_hidden_listing_cannot_be_saved_and_drops_from_list(self):
        self.fav(self.l1)
        Listing.objects.filter(pk=self.l1.pk).update(is_active=False)
        self.assertEqual(self.api.get("/api/listings/favorites/").data["count"], 0)
        self.assertEqual(self.fav(self.l1).status_code, 404)

    def test_favorites_are_private(self):
        self.fav(self.l1)
        other = User.objects.create_user("+998901000008", password=PASSWORD)
        self.assertEqual(self.client_for(other).get("/api/listings/favorites/").data["count"], 0)

class CategoryTreeTests(BaseAPITest):
    def test_api_returns_parent_and_icon(self):
        santexnik = Category.objects.create(name="Santexnik", parent=self.usta, icon="plumbing")
        data = {c["id"]: c for c in self.anon.get("/api/categories/").data}
        self.assertIsNone(data[self.usta.pk]["parent"])
        self.assertEqual(data[santexnik.pk]["parent"], self.usta.pk)
        self.assertEqual(data[santexnik.pk]["icon"], "plumbing")

    def test_section_filter_includes_children(self):
        santexnik = Category.objects.create(name="Santexnik", parent=self.usta)
        elektrik = Category.objects.create(name="Elektrik", parent=self.usta)
        for phone, cat, title in [("+998901000001", santexnik, "Quvur"), ("+998901000002", elektrik, "Rozetka"),
                                  ("+998901000003", self.kafe, "Osh")]:
            _, biz = self.make_business(phone, category=cat)
            Listing.objects.create(business=biz, title=title)
        titles = lambda q: sorted(x["title"] for x in self.anon.get("/api/listings/" + q).data["results"])
        self.assertEqual(titles(f"?category={self.usta.pk}"), ["Quvur", "Rozetka"])  # bo'lim — ichidagilar bilan
        self.assertEqual(titles(f"?category={santexnik.pk}"), ["Quvur"])

    def test_only_two_levels(self):
        from django.core.exceptions import ValidationError
        santexnik = Category.objects.create(name="Santexnik", parent=self.usta)
        with self.assertRaises(ValidationError):
            Category(name="Quvur", parent=santexnik).full_clean()
        with self.assertRaises(ValidationError):  # ichida kategoriyasi bor bo'limni boshqa bo'limga qo'yib bo'lmaydi
            self.usta.parent = self.kafe
            self.usta.full_clean()

    def test_same_name_allowed_in_different_sections(self):
        Category.objects.create(name="Boshqa", parent=self.usta)
        Category.objects.create(name="Boshqa", parent=self.kafe)
        self.assertEqual(Category.objects.filter(name="Boshqa").count(), 2)

class BusinessProfileTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user("+998901000001", password=PASSWORD, role=User.Role.BUSINESS)
        self.api = self.client_for(self.user)

    def profile_data(self, **extra):
        return {"name": "Ali usta", "phone": "90 100 00 01", "telegram_username": "@aliusta",
                "city": self.qoqon.pk, "category": self.usta.pk, **extra}

    def test_get_before_create_is_404(self):
        self.assertEqual(self.api.get("/api/business/me/").status_code, 404)

    def test_create_normalizes_phone_and_telegram(self):
        r = self.api.post("/api/business/me/", self.profile_data(), format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["phone"], "+998901000001")
        self.assertEqual(r.data["telegram_username"], "aliusta")

    def test_create_twice_is_400(self):
        self.api.post("/api/business/me/", self.profile_data(), format="json")
        self.assertEqual(self.api.post("/api/business/me/", self.profile_data(), format="json").status_code, 400)

    def test_patch(self):
        self.api.post("/api/business/me/", self.profile_data(), format="json")
        r = self.api.patch("/api/business/me/", {"name": "Yangi nom"}, format="json")
        self.assertEqual(r.data["name"], "Yangi nom")

    def test_subscription_shown_in_profile(self):
        self.api.post("/api/business/me/", self.profile_data(), format="json")
        self.assertIsNone(self.api.get("/api/business/me/").data["subscription"])
        biz = BusinessProfile.objects.get(user=self.user)
        top = Tariff.objects.create(name="Top", level=1, price=100000, duration_days=30)
        std = Tariff.objects.create(name="Standart", level=2, price=50000, duration_days=30)
        Subscription.objects.create(business=biz, tariff=std)
        Subscription.objects.create(business=biz, tariff=top, start=timezone.now() - timedelta(days=60))  # tugagan
        sub = self.api.get("/api/business/me/").data["subscription"]
        self.assertEqual(sub["tariff"]["name"], "Standart")
        self.assertIn("end", sub)

    def test_subscription_is_read_only(self):
        self.api.post("/api/business/me/", self.profile_data(), format="json")
        self.api.patch("/api/business/me/", {"subscription": {"tariff": 1}}, format="json")
        self.assertFalse(Subscription.objects.exists())

    def test_client_cannot_create(self):
        client_user = User.objects.create_user("+998901000009", password=PASSWORD)
        r = self.client_for(client_user).post("/api/business/me/", self.profile_data(), format="json")
        self.assertEqual(r.status_code, 403)

    def test_anon_cannot_access(self):
        self.assertEqual(self.anon.get("/api/business/me/").status_code, 401)


# =====================================================================
# E'lonlar: ko'rinish, kontaktlar, qidiruv, filtrlar, tartib
# =====================================================================

class ListingPublicTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.user_a, self.biz_a = self.make_business("+998901000001", "Ali usta")
        self.user_b, self.biz_b = self.make_business("+998901000002", "Kafe B", city=self.fargona, category=self.kafe)
        self.l_a = Listing.objects.create(business=self.biz_a, title="Santexnik xizmati", description="Qo‘qon bo'ylab")
        self.l_b = Listing.objects.create(business=self.biz_b, title="Oʻzbek taomlari", price=30000)

    def titles(self, query=""):
        r = self.anon.get("/api/listings/" + query)
        self.assertEqual(r.status_code, 200)
        return [x["title"] for x in r.data["results"]]

    def test_contacts_visible_for_guest(self):
        biz = self.anon.get(f"/api/listings/{self.l_a.pk}/").data["business"]
        self.assertEqual(biz["phone"], "+998901000001")
        self.assertEqual(biz["telegram_username"], "tg_0001")
        listed = self.anon.get("/api/listings/").data["results"][0]["business"]
        self.assertIsNotNone(listed["phone"])

    def test_contacts_visible_for_logged_in(self):
        client_user = User.objects.create_user("+998901000009", password=PASSWORD)
        biz = self.client_for(client_user).get(f"/api/listings/{self.l_a.pk}/").data["business"]
        self.assertEqual(biz["phone"], "+998901000001")
        self.assertEqual(biz["telegram_username"], "tg_0001")

    def test_search_apostrophe_variants(self):
        for q in ["o'zbek", "O‘ZBEK", "oʻzbek", "o`zbek"]:
            self.assertEqual(self.titles(f"?q={q}"), ["Oʻzbek taomlari"], q)

    def test_search_in_description_and_multiple_words(self):
        self.assertEqual(self.titles("?q=qo'qon"), ["Santexnik xizmati"])
        self.assertEqual(self.titles("?q=santexnik qo'qon"), ["Santexnik xizmati"])
        self.assertEqual(self.titles("?q=santexnik taom"), [])

    def test_search_updates_after_edit(self):
        self.l_a.title = "Elektrik"
        self.l_a.save()
        self.assertEqual(self.titles("?q=elektrik"), ["Elektrik"])

    def test_filters(self):
        self.assertEqual(self.titles(f"?city={self.fargona.pk}"), ["Oʻzbek taomlari"])
        self.assertEqual(self.titles(f"?category={self.usta.pk}"), ["Santexnik xizmati"])
        self.assertEqual(len(self.titles(f"?region={self.region.pk}")), 2)
        self.assertEqual(self.titles(f"?city={self.fargona.pk}&category={self.usta.pk}"), [])

    def test_bad_filter_value(self):
        r = self.anon.get("/api/listings/?city=abc")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["city"], ["Butun son bo'lishi kerak."])

    def test_hidden_blocked_and_owner_blocked_not_shown(self):
        self.assertEqual(len(self.titles()), 2)
        Listing.objects.filter(pk=self.l_a.pk).update(is_active=False)
        self.assertEqual(self.titles(), ["Oʻzbek taomlari"])
        Listing.objects.filter(pk=self.l_b.pk).update(is_blocked=True)
        self.assertEqual(self.titles(), [])
        Listing.objects.update(is_active=True, is_blocked=False)
        User.objects.filter(pk=self.user_a.pk).update(is_active=False)
        self.assertEqual(self.titles(), ["Oʻzbek taomlari"])

    def test_hidden_listing_detail_is_404_in_uzbek(self):
        Listing.objects.filter(pk=self.l_a.pk).update(is_active=False)
        r = self.anon.get(f"/api/listings/{self.l_a.pk}/")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.data["detail"], "Topilmadi.")

    def test_order_newest_first_without_subscriptions(self):
        self.assertEqual(self.titles(), ["Oʻzbek taomlari", "Santexnik xizmati"])

    def test_order_by_subscription_level(self):
        _, biz_c = self.make_business("+998901000003", "Usta C")
        Listing.objects.create(business=biz_c, title="Eng yangi, obunasiz")
        top = Tariff.objects.create(name="Top", level=1, price=100000, duration_days=30)
        std = Tariff.objects.create(name="Standart", level=2, price=50000, duration_days=30)
        Subscription.objects.create(business=self.biz_b, tariff=std)
        Subscription.objects.create(business=self.biz_a, tariff=top)
        self.assertEqual(self.titles(), ["Santexnik xizmati", "Oʻzbek taomlari", "Eng yangi, obunasiz"])

    def test_expired_and_future_subscriptions_ignored(self):
        top = Tariff.objects.create(name="Top", level=1, price=100000, duration_days=30)
        now = timezone.now()
        Subscription.objects.create(business=self.biz_a, tariff=top, start=now - timedelta(days=60))  # tugagan
        Subscription.objects.create(business=self.biz_a, tariff=top, start=now + timedelta(days=1))   # hali boshlanmagan
        self.assertEqual(self.titles(), ["Oʻzbek taomlari", "Santexnik xizmati"])

    def test_pagination(self):
        Listing.objects.bulk_create([Listing(business=self.biz_a, title=f"E'lon {i}") for i in range(25)])
        r = self.anon.get("/api/listings/")
        self.assertEqual(r.data["count"], 27)
        self.assertEqual(len(r.data["results"]), 20)
        self.assertIsNotNone(r.data["next"])


# =====================================================================
# E'lonlar: qo'shish, tahrirlash, o'chirish, egalik huquqi, rasmlar
# =====================================================================

@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ListingOwnerTests(BaseAPITest):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        super().setUp()
        self.user_a, self.biz_a = self.make_business("+998901000001", "Ali usta")
        self.user_b, self.biz_b = self.make_business("+998901000002", "Kafe B")
        self.a = self.client_for(self.user_a)
        self.b = self.client_for(self.user_b)
        self.listing = Listing.objects.create(business=self.biz_a, title="Santexnik")

    def test_create(self):
        r = self.a.post("/api/listings/", {"title": "Yangi", "price": 1000, "is_blocked": True}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertFalse(r.data["is_blocked"])  # is_blocked'ni egasi o'zgartira olmaydi
        self.assertEqual(Listing.objects.get(pk=r.data["id"]).business, self.biz_a)

    def test_create_requires_title_in_uzbek(self):
        r = self.a.post("/api/listings/", {}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["title"], ["Bu maydon majburiy."])

    def test_create_without_profile(self):
        user = User.objects.create_user("+998901000005", password=PASSWORD, role=User.Role.BUSINESS)
        r = self.client_for(user).post("/api/listings/", {"title": "x"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_client_and_guest_cannot_create(self):
        client_user = User.objects.create_user("+998901000009", password=PASSWORD)
        self.assertEqual(self.client_for(client_user).post("/api/listings/", {"title": "x"}, format="json").status_code, 403)
        self.assertEqual(self.anon.post("/api/listings/", {"title": "x"}, format="json").status_code, 401)

    def test_owner_can_edit_and_delete(self):
        r = self.a.patch(f"/api/listings/{self.listing.pk}/", {"price": 5000}, format="json")
        self.assertEqual(r.data["price"], 5000)
        self.assertEqual(self.a.delete(f"/api/listings/{self.listing.pk}/").status_code, 204)
        self.assertFalse(Listing.objects.filter(pk=self.listing.pk).exists())

    def test_stranger_gets_404(self):
        url = f"/api/listings/{self.listing.pk}/"
        self.assertEqual(self.b.patch(url, {"title": "hack"}, format="json").status_code, 404)
        self.assertEqual(self.b.delete(url).status_code, 404)
        self.assertEqual(self.b.post(url + "images/", {"image": make_image()}, format="multipart").status_code, 404)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.title, "Santexnik")

    def test_owner_can_edit_hidden_listing(self):
        self.a.patch(f"/api/listings/{self.listing.pk}/", {"is_active": False}, format="json")
        r = self.a.patch(f"/api/listings/{self.listing.pk}/", {"is_active": True}, format="json")
        self.assertEqual(r.status_code, 200)

    def test_owner_can_open_own_hidden_listing_others_cannot(self):
        Listing.objects.filter(pk=self.listing.pk).update(is_active=False)
        url = f"/api/listings/{self.listing.pk}/"
        self.assertEqual(self.a.get(url).status_code, 200)
        self.assertEqual(self.b.get(url).status_code, 404)
        self.assertEqual(self.anon.get(url).status_code, 404)

    def test_mine_includes_hidden_only_own(self):
        Listing.objects.create(business=self.biz_a, title="Yashirin", is_active=False)
        Listing.objects.create(business=self.biz_b, title="Begona")
        r = self.a.get("/api/listings/mine/")
        self.assertEqual(sorted(x["title"] for x in r.data["results"]), ["Santexnik", "Yashirin"])
        self.assertEqual(self.anon.get("/api/listings/mine/").status_code, 401)

    def test_upload_and_delete_image(self):
        url = f"/api/listings/{self.listing.pk}/images/"
        r = self.a.post(url, {"image": make_image(), "order": 1}, format="multipart")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(len(self.anon.get(f"/api/listings/{self.listing.pk}/").data["images"]), 1)
        self.assertEqual(self.a.delete(f"{url}{r.data['id']}/").status_code, 204)
        self.assertEqual(self.listing.images.count(), 0)

    def test_thumbnail_created_small_and_deleted_with_image(self):
        import os
        from PIL import Image as PILImage
        buf = BytesIO()
        PILImage.new("RGB", (1600, 1200), "teal").save(buf, "JPEG")
        big = SimpleUploadedFile("big.jpg", buf.getvalue(), content_type="image/jpeg")
        r = self.a.post(f"/api/listings/{self.listing.pk}/images/", {"image": big}, format="multipart")
        self.assertEqual(r.status_code, 201)
        self.assertIn("/media/listings/thumbs/", r.data["thumbnail"])
        img = ListingImage.objects.get(pk=r.data["id"])
        with PILImage.open(img.thumbnail.path) as thumb:
            self.assertEqual(max(thumb.size), 480)
        self.assertLess(os.path.getsize(img.thumbnail.path), os.path.getsize(img.image.path))
        # Diskdagi eski rasm uchun ham (migratsiya shunday qiladi)
        old_thumb = img.thumbnail.path
        img.thumbnail = ""
        img.make_thumbnail()
        img.save()
        self.assertTrue(os.path.exists(img.thumbnail.path))
        os.remove(old_thumb)
        paths = [img.image.path, img.thumbnail.path]
        self.a.delete(f"/api/listings/{self.listing.pk}/images/{img.pk}/")
        self.assertFalse(any(os.path.exists(p) for p in paths))  # ikkala fayl ham o'chdi

    def test_thumbnail_from_transparent_png(self):
        buf = BytesIO()
        PILImage_new = __import__("PIL.Image", fromlist=["Image"])
        PILImage_new.new("RGBA", (800, 800), (255, 0, 0, 0)).save(buf, "PNG")
        png = SimpleUploadedFile("t.png", buf.getvalue(), content_type="image/png")
        r = self.a.post(f"/api/listings/{self.listing.pk}/images/", {"image": png}, format="multipart")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(ListingImage.objects.get(pk=r.data["id"]).thumbnail)

    def test_upload_not_an_image(self):

        bad = SimpleUploadedFile("x.png", b"bu rasm emas", content_type="image/png")
        r = self.a.post(f"/api/listings/{self.listing.pk}/images/", {"image": bad}, format="multipart")
        self.assertEqual(r.status_code, 400)

    def test_too_large_image_rejected(self):
        from unittest import mock
        with mock.patch("catalog.serializers.MAX_IMAGE_MB", 0):  # 0 MB — har qanday rasm "katta"
            r = self.a.post(f"/api/listings/{self.listing.pk}/images/", {"image": make_image()}, format="multipart")
        self.assertEqual(r.status_code, 400)
        self.assertIn("juda katta", str(r.data["image"]))

    def test_image_limit(self):
        url = f"/api/listings/{self.listing.pk}/images/"
        for _ in range(10):
            self.assertEqual(self.a.post(url, {"image": make_image()}, format="multipart").status_code, 201)
        self.assertEqual(self.a.post(url, {"image": make_image()}, format="multipart").status_code, 400)


# =====================================================================
# Modellar
# =====================================================================

class ModelTests(TestCase):
    def test_subscription_end_calculated_from_tariff(self):
        region = Region.objects.create(name="R")
        city = City.objects.create(region=region, name="C")
        cat = Category.objects.create(name="K")
        user = User.objects.create_user("+998901000001", password=PASSWORD, role=User.Role.BUSINESS)
        biz = BusinessProfile.objects.create(user=user, name="B", phone="+998901000001", city=city, category=cat)
        tariff = Tariff.objects.create(name="T", level=1, price=1, duration_days=30)
        sub = Subscription.objects.create(business=biz, tariff=tariff)
        self.assertEqual(sub.end - sub.start, timedelta(days=30))
        self.assertTrue(sub.is_current)


# =====================================================================
# So'rovlar sonini cheklash
# =====================================================================

class ThrottleTests(BaseAPITest):
    def test_guest_limited_to_60_per_minute(self):
        codes = [self.anon.get("/api/categories/").status_code for _ in range(61)]
        self.assertEqual(codes[:60], [200] * 60)
        self.assertEqual(codes[60], 429)


# =====================================================================
# Admin panel: har bir sahifa ochilishi va bloklash tugmalari
# =====================================================================

@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class AdminTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser("admin", password=PASSWORD)
        self.client.force_login(self.admin)
        self.user, self.biz = self.make_business("+998901000001", "Ali usta")
        self.listing = Listing.objects.create(business=self.biz, title="Santexnik", price=50000)
        tariff = Tariff.objects.create(name="Top", level=1, price=100000, duration_days=30)
        self.sub = Subscription.objects.create(business=self.biz, tariff=tariff)

    def test_all_pages_open(self):
        pages = ["/admin/", "/admin/catalog/"]
        for model, obj in [("user", self.user), ("businessprofile", self.biz), ("listing", self.listing),
                           ("tariff", self.sub.tariff), ("subscription", self.sub), ("region", self.region),
                           ("city", self.qoqon), ("category", self.usta)]:
            pages += [f"/admin/catalog/{model}/", f"/admin/catalog/{model}/add/",
                      f"/admin/catalog/{model}/{obj.pk}/change/"]
        pages += ["/admin/catalog/listing/?holat=visible", "/admin/catalog/subscription/?holat=soon",
                  f"/admin/catalog/listing/?business__id__exact={self.biz.pk}"]
        for page in pages:
            r = self.client.get(page)
            self.assertEqual(r.status_code, 200, page)
            self.assertNotIn("?e=1", r.get("Location", ""), page)

    def test_dashboard_in_uzbek_with_stats(self):
        html = self.client.get("/admin/").content.decode()
        self.assertIn("Boshqaruv paneli", html)
        self.assertIn("tm-stat", html)
        self.assertIn("Foydalanuvchilar va bizneslar", html)

    def test_block_users_action_skips_superuser(self):
        self.client.post("/admin/catalog/user/", {
            "action": "block_users", "_selected_action": [self.user.pk, self.admin.pk],
        })
        self.user.refresh_from_db()
        self.admin.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertTrue(self.admin.is_active)

    def test_block_listings_action(self):
        self.client.post("/admin/catalog/listing/", {
            "action": "block_listings", "_selected_action": [self.listing.pk],
        })
        self.listing.refresh_from_db()
        self.assertTrue(self.listing.is_blocked)


# =====================================================================
# Swagger hujjati
# =====================================================================

class LoadInitialDataTests(TestCase):
    def test_loads_once_and_is_repeatable(self):
        from django.core.management import call_command
        call_command("load_initial_data", stdout=StringIO())
        self.assertEqual(City.objects.count(), 19)
        self.assertEqual(Category.objects.filter(parent=None).count(), 9)  # bo'limlar
        santexnik = Category.objects.get(name="Santexnik")
        self.assertEqual((santexnik.parent.name, santexnik.icon, santexnik.name_ru), ("Ustalar", "plumbing", "Сантехник"))
        self.assertEqual(City.objects.get(name="Qo'qon").name_ru, "Коканд")
        self.assertTrue(City.objects.filter(name="Qo'qon", region__name="Farg'ona viloyati").exists())
        call_command("load_initial_data", stdout=StringIO())  # ikkinchi marta — takrorlanmaydi
        self.assertEqual(City.objects.count(), 19)
        self.assertEqual(Region.objects.count(), 1)


class BackupTests(TestCase):
    def test_backup_creates_zip_and_keeps_last_n(self):
        import zipfile
        from unittest import mock
        from django.core.management import call_command
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as media, \
                tempfile.TemporaryDirectory() as dbdir:
            # Test bazasi xotirada bo'ladi, shuning uchun vaqtinchalik fayl-baza yaratamiz
            db_path = os.path.join(dbdir, "db.sqlite3")
            import sqlite3
            con = sqlite3.connect(db_path)
            con.execute("create table t (x int)")
            con.execute("insert into t values (42)")
            con.commit()
            con.close()
            os.makedirs(os.path.join(media, "listings"))
            with open(os.path.join(media, "listings", "a.png"), "wb") as f:
                f.write(b"rasm")
            dbs = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": db_path}}
            with mock.patch.dict(os.environ, {"BACKUP_DIR": tmp, "BACKUP_KEEP": "2"}), \
                    override_settings(MEDIA_ROOT=media), \
                    mock.patch("catalog.management.commands.backup.settings.DATABASES", dbs):
                for stamp in ["2026-01-01_000000", "2026-01-02_000000"]:  # eski nusxalar
                    open(os.path.join(tmp, f"topmost-{stamp}.zip"), "wb").close()
                call_command("backup", stdout=StringIO())
            zips = sorted(os.listdir(tmp))
            self.assertEqual(len(zips), 2)  # eng eskisi o'chdi
            self.assertNotIn("topmost-2026-01-01_000000.zip", zips)
            with zipfile.ZipFile(os.path.join(tmp, zips[-1])) as zf:
                self.assertIn("media/listings/a.png", zf.namelist())
                zf.extract("db.sqlite3", tmp)
            con = sqlite3.connect(os.path.join(tmp, "db.sqlite3"))
            self.assertEqual(con.execute("select x from t").fetchone()[0], 42)
            con.close()


class CheckServerTests(TestCase):
    def run_check(self):
        from django.core.management import call_command
        out = StringIO()
        call_command("check_server", stdout=out)
        return out.getvalue()

    def test_dev_settings_reported(self):
        out = self.run_check()
        self.assertIn("❌ Maxfiy kalit", out)  # dasturchilik kaliti (django-insecure-...)
        self.assertIn("tuzatilishi kerak", out)

    def test_production_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "static").mkdir()
            Path(tmp, "static", "staticfiles.json").write_text("{}")
            User.objects.create_superuser("admin", password=PASSWORD)
            region = Region.objects.create(name="R")
            City.objects.create(region=region, name="C")
            Category.objects.create(name="K", name_ru="К")
            Tariff.objects.create(name="Top", level=1, price=1, duration_days=30)
            with override_settings(DEBUG=False, SECRET_KEY="p" * 50, ALLOWED_HOSTS=["api.topmost.uz"],
                                   SECURE_SSL_REDIRECT=True, CSRF_TRUSTED_ORIGINS=["https://api.topmost.uz"],
                                   STATIC_ROOT=Path(tmp, "static"), MEDIA_ROOT=Path(tmp, "media"),
                                   PRIVACY_CONTACT="Telegram @topmost"), \
                    mock.patch.dict(os.environ, {"BACKUP_DIR": str(Path(tmp, "backups"))}):
                out = self.run_check()
        self.assertNotIn("❌", out)
        self.assertNotIn("⚠️", out)
        self.assertIn("Hammasi joyida", out)

class PrivacyPageTests(TestCase):
    def test_privacy_page_public(self):
        r = self.client.get("/privacy/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Maxfiylik siyosati")
        self.assertContains(r, 'id="delete"')  # Google Play: akkauntni o'chirish havolasi

    def test_terms_page_public(self):
        r = self.client.get("/terms/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Foydalanish shartlari")
        self.assertContains(r, "Shikoyat qilish")
        self.assertContains(self.client.get("/privacy/"), 'href="/terms/"')  # sahifalar bir-biriga bog'langan

    @override_settings(PRIVACY_CONTACT="Telegram @topmost_admin")
    def test_privacy_contact_shown(self):
        self.assertContains(self.client.get("/privacy/"), "@topmost_admin")


class DocsTests(TestCase):
    def test_docs_and_schema_open(self):
        self.assertEqual(self.client.get("/api/docs/").status_code, 200)
        self.assertEqual(self.client.get("/api/schema/").status_code, 200)
