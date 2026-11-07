from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    BusinessProfile, Category, City, Listing, ListingImage, Region, Subscription, Tariff, User,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "role", "is_active", "is_staff", "date_joined")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("username", "first_name", "last_name")
    fieldsets = BaseUserAdmin.fieldsets + (("TOPMOST", {"fields": ("role",)}),)
    add_fieldsets = BaseUserAdmin.add_fieldsets + (("TOPMOST", {"fields": ("role",)}),)
    actions = ["block_users", "unblock_users"]

    @admin.action(description="Tanlangan foydalanuvchilarni bloklash")
    def block_users(self, request, queryset):
        # O'zini yoki boshqa adminlarni tasodifan bloklab qo'ymaslik uchun
        count = queryset.filter(is_superuser=False).exclude(pk=request.user.pk).update(is_active=False)
        self.message_user(request, f"{count} ta foydalanuvchi bloklandi.", messages.SUCCESS)

    @admin.action(description="Tanlangan foydalanuvchilarni blokdan chiqarish")
    def unblock_users(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} ta foydalanuvchi blokdan chiqarildi.", messages.SUCCESS)


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "region")
    list_filter = ("region",)
    search_fields = ("name",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ("name",)


class SubscriptionInline(admin.TabularInline):
    model = Subscription
    extra = 0


@admin.register(BusinessProfile)
class BusinessProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "phone", "city", "category", "created_at")
    list_filter = ("city", "category")
    search_fields = ("name", "phone", "user__username")
    autocomplete_fields = ("user",)
    inlines = [SubscriptionInline]


class ListingImageInline(admin.TabularInline):
    model = ListingImage
    extra = 1


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("title", "business", "price", "is_active", "is_blocked", "created_at")
    list_filter = ("is_active", "is_blocked", "business__city", "business__category")
    search_fields = ("title", "business__name")
    inlines = [ListingImageInline]
    actions = ["block_listings", "unblock_listings"]

    @admin.action(description="Tanlangan e'lonlarni bloklash")
    def block_listings(self, request, queryset):
        count = queryset.update(is_blocked=True)
        self.message_user(request, f"{count} ta e'lon bloklandi.", messages.SUCCESS)

    @admin.action(description="Tanlangan e'lonlarni blokdan chiqarish")
    def unblock_listings(self, request, queryset):
        count = queryset.update(is_blocked=False)
        self.message_user(request, f"{count} ta e'lon blokdan chiqarildi.", messages.SUCCESS)


@admin.register(Tariff)
class TariffAdmin(admin.ModelAdmin):
    list_display = ("name", "level", "price", "duration_days")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("business", "tariff", "start", "end", "is_current")
    list_filter = ("tariff",)
    autocomplete_fields = ("business",)

    @admin.display(boolean=True, description="Faol")
    def is_current(self, obj):
        return obj.is_current
