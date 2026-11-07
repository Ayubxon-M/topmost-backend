"""
Avtomatik testlar. Ishga tushirish:  python manage.py test

Testlar alohida, vaqtinchalik bazada ishlaydi — sizning db.sqlite3 ga tegmaydi.
Har bir test_... funksiyasi bitta qoidani tekshiradi. Biror narsa buzilsa,
qaysi test "FAIL" bo'lganiga qarab muammoni topasiz.
"""
import os
import shutil
import tempfile
from datetime import timedelta
from io import BytesIO

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from .models import BusinessProfile, Category, City, Listing, ListingImage, Region, Subscription, Tariff, User
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

    def test_contacts_hidden_for_guest(self):
        biz = self.anon.get(f"/api/listings/{self.l_a.pk}/").data["business"]
        self.assertIsNone(biz["phone"])
        self.assertIsNone(biz["telegram_username"])

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

    def test_upload_not_an_image(self):
        bad = SimpleUploadedFile("x.png", b"bu rasm emas", content_type="image/png")
        r = self.a.post(f"/api/listings/{self.listing.pk}/images/", {"image": bad}, format="multipart")
        self.assertEqual(r.status_code, 400)

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

class PrivacyPageTests(TestCase):
    def test_privacy_page_public(self):
        r = self.client.get("/privacy/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Maxfiylik siyosati")
        self.assertContains(r, 'id="delete"')  # Google Play: akkauntni o'chirish havolasi

    @override_settings(PRIVACY_CONTACT="Telegram @topmost_admin")
    def test_privacy_contact_shown(self):
        self.assertContains(self.client.get("/privacy/"), "@topmost_admin")


class DocsTests(TestCase):
    def test_docs_and_schema_open(self):
        self.assertEqual(self.client.get("/api/docs/").status_code, 200)
        self.assertEqual(self.client.get("/api/schema/").status_code, 200)
