"""
Bo'sh bazaga boshlang'ich ma'lumotlarni qo'shadi:  python manage.py load_initial_data

Farg'ona viloyati shahar va tumanlari + asosiy kategoriyalar.
Ikki marta ishga tushirilsa ham hech narsa takrorlanmaydi (bor bo'lsa — o'tkazib yuboriladi).
Tariflar qo'shilmaydi: narxlarni admin panelda o'zingiz belgilaysiz.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Category, City, Region

REGIONS = {
    "Farg'ona viloyati": [
        # Shaharlar
        "Farg'ona", "Qo'qon", "Marg'ilon", "Quvasoy",
        # Tumanlar
        "Oltiariq tumani", "Bag'dod tumani", "Beshariq tumani", "Buvayda tumani",
        "Dang'ara tumani", "Farg'ona tumani", "Furqat tumani", "Qo'shtepa tumani",
        "Quva tumani", "Rishton tumani", "So'x tumani", "Toshloq tumani",
        "Uchko'prik tumani", "O'zbekiston tumani", "Yozyovon tumani",
    ],
}

CATEGORIES = ["Ustalar", "Do'konlar", "Kafelar"]


class Command(BaseCommand):
    help = "Farg'ona viloyati shahar/tumanlari va asosiy kategoriyalarni qo'shadi"

    @transaction.atomic
    def handle(self, *args, **options):
        added_cities = 0
        for region_name, cities in REGIONS.items():
            region, _ = Region.objects.get_or_create(name=region_name)
            for name in cities:
                _, created = City.objects.get_or_create(region=region, name=name)
                added_cities += created

        added_categories = 0
        for name in CATEGORIES:
            _, created = Category.objects.get_or_create(name=name)
            added_categories += created

        self.stdout.write(self.style.SUCCESS(
            f"Tayyor: {added_cities} ta shahar/tuman, {added_categories} ta kategoriya qo'shildi "
            f"(oldin bor bo'lganlari o'tkazib yuborildi)."
        ))
