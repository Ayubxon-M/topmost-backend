from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from .utils import normalize_text


class User(AbstractUser):
    """
    Foydalanuvchi. username maydoniga telefon raqami yoziladi (+998XXXXXXXXX).
    is_active=False bo'lsa — foydalanuvchi bloklangan.
    """

    class Role(models.TextChoices):
        CLIENT = "client", "Mijoz"
        BUSINESS = "business", "Biznes"

    role = models.CharField("Rol", max_length=10, choices=Role.choices, default=Role.CLIENT)

    @property
    def is_business(self):
        return self.role == self.Role.BUSINESS

    def __str__(self):
        return self.username


class Region(models.Model):
    """Viloyat."""
    name = models.CharField("Viloyat nomi", max_length=100, unique=True)

    class Meta:
        verbose_name = "Viloyat"
        verbose_name_plural = "Viloyatlar"
        ordering = ["name"]

    def __str__(self):
        return self.name


class City(models.Model):
    """Shahar yoki tuman."""
    region = models.ForeignKey(Region, on_delete=models.PROTECT, related_name="cities", verbose_name="Viloyat")
    name = models.CharField("Shahar / tuman nomi", max_length=100)

    class Meta:
        verbose_name = "Shahar / tuman"
        verbose_name_plural = "Shaharlar / tumanlar"
        ordering = ["name"]
        unique_together = [("region", "name")]

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField("Kategoriya", max_length=100, unique=True)

    class Meta:
        verbose_name = "Kategoriya"
        verbose_name_plural = "Kategoriyalar"
        ordering = ["name"]

    def __str__(self):
        return self.name


class BusinessProfile(models.Model):
    """Biznes (usta, do'kon, kafe) ma'lumotlari. Har bir biznes-foydalanuvchida bittadan."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="business", verbose_name="Foydalanuvchi")
    name = models.CharField("Nomi", max_length=150)
    phone = models.CharField("Telefon", max_length=20)
    telegram_username = models.CharField("Telegram username", max_length=100, blank=True)
    city = models.ForeignKey(City, on_delete=models.PROTECT, verbose_name="Shahar / tuman")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, verbose_name="Kategoriya")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Biznes profil"
        verbose_name_plural = "Biznes profillar"

    def __str__(self):
        return self.name


class Listing(models.Model):
    """E'lon."""
    business = models.ForeignKey(BusinessProfile, on_delete=models.CASCADE, related_name="listings", verbose_name="Biznes")
    title = models.CharField("Sarlavha", max_length=200)
    description = models.TextField("Izoh", blank=True)
    price = models.PositiveIntegerField("Narx (so'm)", null=True, blank=True)
    is_active = models.BooleanField("Faol", default=True, help_text="Egasi e'lonni yashirishi mumkin")
    is_blocked = models.BooleanField("Bloklangan", default=False, help_text="Admin tomonidan bloklangan")
    # Qidiruv uchun: sarlavha + izohning kichik harfli, apostroflari birlashtirilgan nusxasi.
    search_text = models.TextField(editable=False, blank=True)
    created_at = models.DateTimeField("Yaratilgan", auto_now_add=True)
    updated_at = models.DateTimeField("Yangilangan", auto_now=True)

    class Meta:
        verbose_name = "E'lon"
        verbose_name_plural = "E'lonlar"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        self.search_text = normalize_text(f"{self.title} {self.description}")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class ListingImage(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="images", verbose_name="E'lon")
    image = models.ImageField("Rasm", upload_to="listings/")
    order = models.PositiveSmallIntegerField("Tartib", default=0)

    class Meta:
        verbose_name = "E'lon rasmi"
        verbose_name_plural = "E'lon rasmlari"
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.listing.title} - rasm {self.order}"


class Tariff(models.Model):
    """Pullik tarif. level=1 eng yuqori (ro'yxatda birinchi chiqadi), level=2 undan keyin."""

    class Level(models.IntegerChoices):
        TOP = 1, "1-daraja (eng yuqori)"
        STANDARD = 2, "2-daraja"

    name = models.CharField("Nomi", max_length=100)
    level = models.PositiveSmallIntegerField("Daraja", choices=Level.choices)
    price = models.PositiveIntegerField("Narx (so'm)")
    duration_days = models.PositiveIntegerField("Muddat (kun)")

    class Meta:
        verbose_name = "Tarif"
        verbose_name_plural = "Tariflar"
        ordering = ["level", "price"]

    def __str__(self):
        return f"{self.name} (daraja {self.level}, {self.duration_days} kun)"


class Subscription(models.Model):
    """Biznesning tarifga obunasi. start <= hozir < end bo'lsa — faol."""
    business = models.ForeignKey(BusinessProfile, on_delete=models.CASCADE, related_name="subscriptions", verbose_name="Biznes")
    tariff = models.ForeignKey(Tariff, on_delete=models.PROTECT, verbose_name="Tarif")
    start = models.DateTimeField("Boshlanish", default=timezone.now)
    end = models.DateTimeField("Tugash", blank=True, help_text="Bo'sh qoldirilsa, tarif muddatidan hisoblanadi")

    class Meta:
        verbose_name = "Obuna"
        verbose_name_plural = "Obunalar"
        ordering = ["-start"]

    def save(self, *args, **kwargs):
        if not self.end:
            self.end = self.start + timedelta(days=self.tariff.duration_days)
        super().save(*args, **kwargs)

    @property
    def is_current(self):
        now = timezone.now()
        return self.start <= now < self.end

    def __str__(self):
        return f"{self.business} — {self.tariff.name}"
