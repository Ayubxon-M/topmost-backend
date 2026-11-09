"""
Bo'sh bazaga boshlang'ich ma'lumotlarni qo'shadi:  python manage.py load_initial_data

Farg'ona viloyati shahar va tumanlari + kategoriyalar (bo'limlar va ularning ichidagilar).
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

# Bo'lim: (ikonka, [(kategoriya, ikonka), ...]). Admin panelda istalgancha qo'shish/o'zgartirish mumkin.
CATEGORIES = {
    "Ustalar": ("build", [
        ("Santexnik", "plumbing"), ("Elektrik", "electrical"), ("Duradgor", "carpenter"),
        ("Payvandchi", "handyman"), ("Konditsioner ustasi", "ac"), ("Maishiy texnika ta'miri", "kitchen"),
        ("Telefon ta'miri", "phone"),
    ]),
    "Qurilish va ta'mir": ("construction", [
        ("Qurilish brigadasi", "construction"), ("Bo'yoqchi", "paint"), ("Kafelchi", "construction"),
        ("Qurilish mollari", "store"),
    ]),
    "Ovqatlanish": ("restaurant", [
        ("Kafe", "cafe"), ("Restoran", "restaurant"), ("Fast-food", "fastfood"), ("Choyxona", "cafe"),
        ("Tort va shirinliklar", "cake"),
    ]),
    "Do'konlar": ("store", [
        ("Oziq-ovqat", "grocery"), ("Kiyim-kechak", "clothes"), ("Elektronika", "devices"),
        ("Uy-ro'zg'or buyumlari", "home"), ("Gullar", "florist"),
    ]),
    "Go'zallik": ("spa", [("Sartaroshxona", "barber"), ("Go'zallik saloni", "spa")]),
    "Transport va avto": ("taxi", [
        ("Taxi", "taxi"), ("Yuk tashish", "shipping"), ("Avtoservis", "car_repair"), ("Avtomoyka", "car_wash"),
    ]),
    "Ta'lim": ("school", [("O'quv markazi", "school"), ("Repetitor", "school")]),
    "Sog'liq": ("medical", [("Dorixona", "pharmacy"), ("Klinika", "medical"), ("Stomatologiya", "medical")]),
    "Xizmatlar": ("handyman", [
        ("Tozalash xizmati", "cleaning"), ("Tikuvchi", "clothes"), ("Fotograf", "camera"),
        ("To'y va tadbirlar", "event"), ("Kompyuter xizmati", "computer"),
    ]),
}


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
        for order, (section_name, (section_icon, children)) in enumerate(CATEGORIES.items()):
            section, created = Category.objects.get_or_create(
                name=section_name, parent=None, defaults={"icon": section_icon, "order": order},
            )
            added_categories += created
            for child_order, (name, icon) in enumerate(children):
                _, created = Category.objects.get_or_create(
                    name=name, parent=section, defaults={"icon": icon, "order": child_order},
                )
                added_categories += created

        self.stdout.write(self.style.SUCCESS(
            f"Tayyor: {added_cities} ta shahar/tuman, {added_categories} ta kategoriya qo'shildi "
            f"(oldin bor bo'lganlari o'tkazib yuborildi)."
        ))
