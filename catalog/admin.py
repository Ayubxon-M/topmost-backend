"""
Admin panel jadvallari: qaysi ustunlar ko'rinadi, filtrlar, qidiruv, bloklash tugmalari.
Umumiy ko'rinish (menyu, bosh sahifa) — catalog/admin_site.py va templates/admin/.
"""
from datetime import timedelta

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.html import format_html

from .admin_site import SUBSCRIPTION_SOON_DAYS
from .models import (
    BusinessProfile, Category, City, Listing, ListingImage, Region, Subscription, Tariff, User,
)

# Guruhlar (Groups) bizga kerak emas — menyudan olib tashlaymiz
admin.site.unregister(Group)


# ---------- Yordamchilar ----------

def badge(text, color):
    """Rangli belgi: green, red, orange, gray, blue, teal, purple."""
    return format_html('<span class="tm-badge tm-{}">{}</span>', color, text)


def money(value):
    if value is None:
        return "—"
    return f"{value:,}".replace(",", " ") + " so'm"


def thumb(image, size="sm"):
    if not image:
        return format_html('<span class="tm-thumb tm-thumb-{} tm-thumb-empty">rasm yo\'q</span>', size)
    return format_html('<img src="{}" class="tm-thumb tm-thumb-{}" alt="">', image.url, size)


# ---------- Foydalanuvchilar ----------

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "full_name", "role_badge", "business_link", "status_badge", "date_joined")
    list_display_links = ("username",)
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("username", "first_name", "last_name", "business__name")
    ordering = ("-date_joined",)
    list_per_page = 30
    readonly_fields = ("last_login", "date_joined")
    actions = ["block_users", "unblock_users"]

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Rol va holat", {
            "fields": ("role", "is_active"),
            "description": "Foydalanuvchini bloklash uchun «faol» belgisini olib tashlang.",
        }),
        ("Shaxsiy ma'lumot", {"fields": ("first_name", "last_name", "email")}),
        ("Admin huquqlari", {
            "classes": ("collapse",),
            "fields": ("is_staff", "is_superuser", "groups", "user_permissions"),
        }),
        ("Sanalar", {"classes": ("collapse",), "fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (("Rol", {"fields": ("role",)}),)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("business")

    @admin.display(description="Ism")
    def full_name(self, obj):
        return obj.get_full_name() or "—"

    @admin.display(description="Rol", ordering="role")
    def role_badge(self, obj):
        if obj.is_superuser:
            return badge("Admin", "purple")
        return badge("Biznes", "teal") if obj.is_business else badge("Mijoz", "blue")

    @admin.display(description="Biznes")
    def business_link(self, obj):
        business = getattr(obj, "business", None)
        if business is None:
            return "—"
        return format_html('<a href="../businessprofile/{}/change/">{}</a>', business.pk, business.name)

    @admin.display(description="Holat", ordering="is_active")
    def status_badge(self, obj):
        return badge("Faol", "green") if obj.is_active else badge("Bloklangan", "red")

    @admin.action(description="🔒 Tanlanganlarni bloklash")
    def block_users(self, request, queryset):
        # O'zini yoki boshqa adminlarni tasodifan bloklab qo'ymaslik uchun
        count = queryset.filter(is_superuser=False).exclude(pk=request.user.pk).update(is_active=False)
        self.message_user(request, f"{count} ta foydalanuvchi bloklandi.", messages.SUCCESS)

    @admin.action(description="🔓 Tanlanganlarni blokdan chiqarish")
    def unblock_users(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} ta foydalanuvchi blokdan chiqarildi.", messages.SUCCESS)


# ---------- Biznes profillar ----------

class SubscriptionInline(admin.TabularInline):
    model = Subscription
    extra = 0
    fields = ("tariff", "start", "end")
    verbose_name_plural = "Obunalar (to'lov qilganda shu yerga qo'shing)"


@admin.register(BusinessProfile)
class BusinessProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "phone", "telegram_link", "city", "category", "listings_total", "tariff_badge")
    list_filter = ("city__region", "city", "category__parent", "category")
    search_fields = ("name", "phone", "user__username", "telegram_username")
    list_select_related = ("user", "city", "category")
    autocomplete_fields = ("user",)
    list_per_page = 30
    inlines = [SubscriptionInline]
    readonly_fields = ("logo_preview",)
    fieldsets = (
        ("Asosiy", {"fields": ("user", "name", "category", "description", "logo_preview", "logo")}),
        ("Kontaktlar", {"fields": ("phone", "telegram_username")}),
        ("Joylashuv", {
            "fields": ("city", "address", ("latitude", "longitude")),
            "description": "Koordinatani Google yoki Yandex xaritadan olish mumkin: joyni bosib turing — "
                           "40.528, 70.942 kabi ikki son chiqadi.",
        }),
        ("Ish vaqti", {
            "fields": ("is_24_7", "work_days", ("opens_at", "closes_at")),
            "description": "Ish kunlari raqamlarda: 1 — dushanba ... 7 — yakshanba. Masalan «123456» — dushanba–shanba.",
        }),
    )

    @admin.display(description="Logo")
    def logo_preview(self, obj):
        return thumb(obj.logo if obj.pk else None, "md")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_listings=Count("listings")).prefetch_related(
            "subscriptions__tariff"
        )

    @admin.display(description="Telegram")
    def telegram_link(self, obj):
        if not obj.telegram_username:
            return "—"
        return format_html('<a href="https://t.me/{0}" target="_blank">@{0}</a>', obj.telegram_username)

    @admin.display(description="E'lonlar", ordering="_listings")
    def listings_total(self, obj):
        return format_html('<a href="../listing/?business__id__exact={}">{} ta</a>', obj.pk, obj._listings)

    @admin.display(description="Tarif")
    def tariff_badge(self, obj):
        current = [s for s in obj.subscriptions.all() if s.is_current]
        if not current:
            return badge("Oddiy", "gray")
        best = min(current, key=lambda s: s.tariff.level)
        return badge(f"{best.tariff.name} · {best.end:%d.%m}", "purple" if best.tariff.level == 1 else "teal")


# ---------- E'lonlar ----------

class ListingImageInline(admin.TabularInline):
    model = ListingImage
    extra = 1
    fields = ("preview", "image", "order")
    readonly_fields = ("preview",)

    @admin.display(description="Ko'rinishi")
    def preview(self, obj):
        return thumb(obj.image if obj.pk else None, "md")


class ListingStatusFilter(admin.SimpleListFilter):
    title = "holati"
    parameter_name = "holat"

    def lookups(self, request, model_admin):
        return [
            ("visible", "Ko'rinayotgan"),
            ("hidden", "Egasi yashirgan"),
            ("blocked", "Admin bloklagan"),
            ("owner_blocked", "Egasi bloklangan"),
        ]

    def queryset(self, request, queryset):
        value = self.value()
        if value == "visible":
            return queryset.filter(is_active=True, is_blocked=False, business__user__is_active=True)
        if value == "hidden":
            return queryset.filter(is_active=False)
        if value == "blocked":
            return queryset.filter(is_blocked=True)
        if value == "owner_blocked":
            return queryset.filter(business__user__is_active=False)
        return queryset


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("photo", "title", "business", "price_display", "status_badge", "favorites_count", "created_at")
    list_display_links = ("photo", "title")
    list_filter = (ListingStatusFilter, "price_type", "is_active", "is_blocked", "business__city", "business__category")
    search_fields = ("title", "description", "business__name")
    list_select_related = ("business__user",)
    autocomplete_fields = ("business",)
    date_hierarchy = "created_at"
    list_per_page = 25
    readonly_fields = ("created_at", "updated_at")
    inlines = [ListingImageInline]
    actions = ["block_listings", "unblock_listings"]
    fieldsets = (
        ("E'lon", {"fields": ("business", "title", "description", ("price_type", "price"))}),
        ("Holat", {
            "fields": ("is_active", "is_blocked"),
            "description": "«Faol» — egasi boshqaradi. «Bloklangan» — faqat admin. "
                           "Ilovada faqat faol va bloklanmagan e'lonlar ko'rinadi.",
        }),
        ("Sanalar", {"classes": ("collapse",), "fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("images").annotate(_favorites=Count("favorites"))

    @admin.display(description="Rasm")
    def photo(self, obj):
        images = list(obj.images.all())
        return thumb(images[0].image if images else None)

    @admin.display(description="❤️", ordering="_favorites")
    def favorites_count(self, obj):
        return obj._favorites

    @admin.display(description="Narx", ordering="price")
    def price_display(self, obj):
        if obj.price_type == Listing.PriceType.FROM:
            return money(obj.price) + "dan"
        if obj.price_type == Listing.PriceType.FIXED:
            return money(obj.price)
        return obj.get_price_type_display()

    @admin.display(description="Holat")
    def status_badge(self, obj):
        if obj.is_blocked:
            return badge("Bloklangan", "red")
        if not obj.business.user.is_active:
            return badge("Egasi bloklangan", "orange")
        if not obj.is_active:
            return badge("Yashirin", "gray")
        return badge("Ko'rinmoqda", "green")

    @admin.action(description="🔒 Tanlanganlarni bloklash")
    def block_listings(self, request, queryset):
        count = queryset.update(is_blocked=True)
        self.message_user(request, f"{count} ta e'lon bloklandi.", messages.SUCCESS)

    @admin.action(description="🔓 Tanlanganlarni blokdan chiqarish")
    def unblock_listings(self, request, queryset):
        count = queryset.update(is_blocked=False)
        self.message_user(request, f"{count} ta e'lon blokdan chiqarildi.", messages.SUCCESS)


# ---------- Tariflar va obunalar ----------

@admin.register(Tariff)
class TariffAdmin(admin.ModelAdmin):
    list_display = ("name", "level_badge", "price_display", "duration_display", "active_count")

    def get_queryset(self, request):
        now = timezone.now()
        return super().get_queryset(request).annotate(
            _active=Count("subscription", filter=Q(subscription__start__lte=now, subscription__end__gt=now))
        )

    @admin.display(description="Daraja", ordering="level")
    def level_badge(self, obj):
        return badge("1 — eng yuqori", "purple") if obj.level == 1 else badge("2", "teal")

    @admin.display(description="Narx", ordering="price")
    def price_display(self, obj):
        return money(obj.price)

    @admin.display(description="Muddat", ordering="duration_days")
    def duration_display(self, obj):
        return f"{obj.duration_days} kun"

    @admin.display(description="Faol obunalar", ordering="_active")
    def active_count(self, obj):
        return obj._active


class SubscriptionStatusFilter(admin.SimpleListFilter):
    title = "holati"
    parameter_name = "holat"

    def lookups(self, request, model_admin):
        return [
            ("active", "Faol"),
            ("soon", f"{SUBSCRIPTION_SOON_DAYS} kunda tugaydi"),
            ("future", "Hali boshlanmagan"),
            ("expired", "Tugagan"),
        ]

    def queryset(self, request, queryset):
        now = timezone.now()
        value = self.value()
        if value == "active":
            return queryset.filter(start__lte=now, end__gt=now)
        if value == "soon":
            return queryset.filter(start__lte=now, end__gt=now, end__lte=now + timedelta(days=SUBSCRIPTION_SOON_DAYS))
        if value == "future":
            return queryset.filter(start__gt=now)
        if value == "expired":
            return queryset.filter(end__lte=now)
        return queryset


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("business", "tariff", "start", "end", "status_badge")
    list_filter = (SubscriptionStatusFilter, "tariff")
    search_fields = ("business__name", "business__user__username")
    list_select_related = ("business", "tariff")
    autocomplete_fields = ("business",)
    date_hierarchy = "start"

    @admin.display(description="Holat", ordering="end")
    def status_badge(self, obj):
        now = timezone.now()
        if obj.start > now:
            return badge("Hali boshlanmagan", "blue")
        if obj.end <= now:
            return badge("Tugagan", "gray")
        days = (obj.end - now).days
        if days < SUBSCRIPTION_SOON_DAYS:
            return badge(f"Faol · {days} kun qoldi", "orange")
        return badge(f"Faol · {days} kun qoldi", "green")


# ---------- Ma'lumotnomalar ----------

@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("name", "cities_count")
    search_fields = ("name",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_cities=Count("cities"))

    @admin.display(description="Shahar / tumanlar", ordering="_cities")
    def cities_count(self, obj):
        return obj._cities


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "region", "business_count")
    list_filter = ("region",)
    search_fields = ("name",)
    list_select_related = ("region",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_businesses=Count("businessprofile"))

    @admin.display(description="Bizneslar", ordering="_businesses")
    def business_count(self, obj):
        return obj._businesses


class CategoryLevelFilter(admin.SimpleListFilter):
    title = "darajasi"
    parameter_name = "daraja"

    def lookups(self, request, model_admin):
        return [("top", "Bo'limlar"), ("sub", "Ichki kategoriyalar")]

    def queryset(self, request, queryset):
        if self.value() == "top":
            return queryset.filter(parent__isnull=True)
        if self.value() == "sub":
            return queryset.filter(parent__isnull=False)
        return queryset


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("tree_name", "icon", "order", "business_count")
    list_editable = ("icon", "order")
    list_filter = (CategoryLevelFilter, "parent")
    search_fields = ("name", "parent__name")
    list_select_related = ("parent",)
    fields = ("name", "parent", "icon", "order")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_businesses=Count("businessprofile"))

    def get_ordering(self, request):
        # Bo'lim, keyin uning ichidagilar — daraxt ko'rinishida
        return ("parent__order", "parent__name", "parent_id", "order", "name")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "parent":
            kwargs["queryset"] = Category.objects.filter(parent__isnull=True)  # faqat bo'limlar
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description="Kategoriya", ordering="name")
    def tree_name(self, obj):
        if obj.parent_id:
            return format_html('<span style="color:var(--body-quiet-color)">{} ›</span> {}', obj.parent.name, obj.name)
        return format_html("<b>{}</b>", obj.name)

    @admin.display(description="Bizneslar", ordering="_businesses")
    def business_count(self, obj):
        return obj._businesses
