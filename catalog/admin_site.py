"""
TOPMOST admin panelining "qobig'i": sarlavhalar, menyu guruhlari va bosh sahifadagi statistika.
Har bir jadvalning (model) sozlamalari esa catalog/admin.py da.
"""
from datetime import timedelta

from django.contrib import admin
from django.urls import reverse
from django.utils import timezone

# Menyu bo'limlari: (bo'lim nomi, [modellar]) — shu tartibda chiqadi
MENU_SECTIONS = [
    ("Foydalanuvchilar va bizneslar", ["user", "businessprofile"]),
    ("E'lonlar", ["listing"]),
    ("Tariflar va obunalar", ["subscription", "tariff"]),
    ("Ma'lumotnomalar", ["region", "city", "category"]),
]

SUBSCRIPTION_SOON_DAYS = 3  # obuna tugashiga shuncha kun qolsa — ogohlantiramiz


class TopmostAdminSite(admin.AdminSite):
    site_header = "TOPMOST"
    site_title = "TOPMOST admin"
    index_title = "Boshqaruv paneli"
    site_url = None  # "Saytni ko'rish" havolasi kerak emas (bizda faqat API bor)

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request, app_label)
        if app_label:  # bitta bo'lim sahifasi — o'zgartirmaymiz
            return app_list

        catalog = next((app for app in app_list if app["app_label"] == "catalog"), None)
        if catalog is None:
            return app_list
        models = {m["object_name"].lower(): m for m in catalog["models"]}

        sections = []
        for title, names in MENU_SECTIONS:
            section_models = [models[n] for n in names if n in models]
            if section_models:
                sections.append({**catalog, "name": title, "models": section_models})
        others = [app for app in app_list if app["app_label"] != "catalog"]
        return sections + others

    def index(self, request, extra_context=None):
        extra_context = {**(extra_context or {}), **self.dashboard_context()}
        return super().index(request, extra_context)

    def dashboard_context(self):
        from .models import BusinessProfile, Category, City, Listing, Region, Subscription, Tariff, User

        now = timezone.now()
        soon = now + timedelta(days=SUBSCRIPTION_SOON_DAYS)

        def url(model, query=""):
            return reverse(f"admin:catalog_{model}_changelist") + query

        visible = Listing.objects.filter(is_active=True, is_blocked=False, business__user__is_active=True)
        active_subs = Subscription.objects.filter(start__lte=now, end__gt=now)

        stats = [
            {"label": "Mijozlar", "value": User.objects.filter(role=User.Role.CLIENT, is_staff=False).count(),
             "url": url("user", "?role__exact=client&is_staff__exact=0"), "color": "blue"},
            {"label": "Bizneslar", "value": BusinessProfile.objects.count(),
             "url": url("businessprofile"), "color": "teal"},
            {"label": "Ko'rinayotgan e'lonlar", "value": visible.count(),
             "url": url("listing", "?is_active__exact=1&is_blocked__exact=0"), "color": "green"},
            {"label": "Bloklangan e'lonlar", "value": Listing.objects.filter(is_blocked=True).count(),
             "url": url("listing", "?is_blocked__exact=1"), "color": "red"},
            {"label": "Faol obunalar", "value": active_subs.count(),
             "url": url("subscription", "?holat=active"), "color": "purple"},
            {"label": f"{SUBSCRIPTION_SOON_DAYS} kunda tugaydigan obunalar",
             "value": active_subs.filter(end__lte=soon).count(),
             "url": url("subscription", "?holat=soon"), "color": "orange"},
            {"label": "Bloklangan foydalanuvchilar", "value": User.objects.filter(is_active=False).count(),
             "url": url("user", "?is_active__exact=0"), "color": "gray"},
        ]

        # Ilova ishlashi uchun avval kiritilishi kerak bo'lgan ma'lumotlar
        setup = [
            {"label": "Viloyat qo'shing", "done": Region.objects.exists(), "url": url("region")},
            {"label": "Shahar / tuman qo'shing", "done": City.objects.exists(), "url": url("city")},
            {"label": "Kategoriya qo'shing", "done": Category.objects.exists(), "url": url("category")},
            {"label": "Tarif qo'shing", "done": Tariff.objects.exists(), "url": url("tariff")},
        ]
        return {
            "topmost_stats": stats,
            "topmost_setup": setup,
            "topmost_setup_done": all(s["done"] for s in setup),
        }
