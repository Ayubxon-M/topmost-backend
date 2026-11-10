"""
Bo'sh bazaga boshlang'ich ma'lumotlarni qo'shadi:  python manage.py load_initial_data

Farg'ona viloyati shahar va tumanlari + kategoriyalar (bo'limlar va ularning ichidagilar),
o'zbekcha va ruscha nomlari bilan.
Ikki marta ishga tushirilsa ham hech narsa takrorlanmaydi (bor bo'lsa — o'tkazib yuboriladi);
faqat bo'sh turgan ruscha nomlar to'ldiriladi.
Tariflar qo'shilmaydi: narxlarni admin panelda o'zingiz belgilaysiz.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Category, City, Region

# (o'zbekcha, ruscha)
REGIONS = {
    ("Farg'ona viloyati", "Ферганская область"): [
        # Shaharlar
        ("Farg'ona", "Фергана"), ("Qo'qon", "Коканд"), ("Marg'ilon", "Маргилан"), ("Quvasoy", "Кувасай"),
        # Tumanlar
        ("Oltiariq tumani", "Алтыарыкский район"), ("Bag'dod tumani", "Багдадский район"),
        ("Beshariq tumani", "Бешарыкский район"), ("Buvayda tumani", "Бувайдинский район"),
        ("Dang'ara tumani", "Дангаринский район"), ("Farg'ona tumani", "Ферганский район"),
        ("Furqat tumani", "Фуркатский район"), ("Qo'shtepa tumani", "Куштепинский район"),
        ("Quva tumani", "Кувинский район"), ("Rishton tumani", "Риштанский район"),
        ("So'x tumani", "Сохский район"), ("Toshloq tumani", "Ташлакский район"),
        ("Uchko'prik tumani", "Учкуприкский район"), ("O'zbekiston tumani", "Узбекистанский район"),
        ("Yozyovon tumani", "Язъяванский район"),
    ],
}

# Bo'lim (o'zbekcha, ruscha): (ikonka, [(kategoriya, ruscha, ikonka), ...])
CATEGORIES = {
    ("Ustalar", "Мастера"): ("build", [
        ("Santexnik", "Сантехник", "plumbing"), ("Elektrik", "Электрик", "electrical"),
        ("Duradgor", "Плотник", "carpenter"), ("Payvandchi", "Сварщик", "handyman"),
        ("Konditsioner ustasi", "Мастер по кондиционерам", "ac"),
        ("Maishiy texnika ta'miri", "Ремонт бытовой техники", "kitchen"),
        ("Telefon ta'miri", "Ремонт телефонов", "phone"),
    ]),
    ("Qurilish va ta'mir", "Строительство и ремонт"): ("construction", [
        ("Qurilish brigadasi", "Строительная бригада", "construction"), ("Bo'yoqchi", "Маляр", "paint"),
        ("Kafelchi", "Плиточник", "construction"), ("Qurilish mollari", "Стройматериалы", "store"),
    ]),
    ("Ovqatlanish", "Еда"): ("restaurant", [
        ("Kafe", "Кафе", "cafe"), ("Restoran", "Ресторан", "restaurant"), ("Fast-food", "Фастфуд", "fastfood"),
        ("Choyxona", "Чайхана", "cafe"), ("Tort va shirinliklar", "Торты и сладости", "cake"),
    ]),
    ("Do'konlar", "Магазины"): ("store", [
        ("Oziq-ovqat", "Продукты", "grocery"), ("Kiyim-kechak", "Одежда", "clothes"),
        ("Elektronika", "Электроника", "devices"), ("Uy-ro'zg'or buyumlari", "Товары для дома", "home"),
        ("Gullar", "Цветы", "florist"),
    ]),
    ("Go'zallik", "Красота"): ("spa", [
        ("Sartaroshxona", "Парикмахерская", "barber"), ("Go'zallik saloni", "Салон красоты", "spa"),
    ]),
    ("Transport va avto", "Транспорт и авто"): ("taxi", [
        ("Taxi", "Такси", "taxi"), ("Yuk tashish", "Грузоперевозки", "shipping"),
        ("Avtoservis", "Автосервис", "car_repair"), ("Avtomoyka", "Автомойка", "car_wash"),
    ]),
    ("Ta'lim", "Образование"): ("school", [
        ("O'quv markazi", "Учебный центр", "school"), ("Repetitor", "Репетитор", "school"),
    ]),
    ("Sog'liq", "Здоровье"): ("medical", [
        ("Dorixona", "Аптека", "pharmacy"), ("Klinika", "Клиника", "medical"),
        ("Stomatologiya", "Стоматология", "medical"),
    ]),
    ("Xizmatlar", "Услуги"): ("handyman", [
        ("Tozalash xizmati", "Клининг", "cleaning"), ("Tikuvchi", "Швея", "clothes"),
        ("Fotograf", "Фотограф", "camera"), ("To'y va tadbirlar", "Свадьбы и мероприятия", "event"),
        ("Kompyuter xizmati", "Компьютерные услуги", "computer"),
    ]),
}


def fill_ru(obj, name_ru):
    """Ruscha nom bo'sh bo'lsa — to'ldiradi (admin yozgan nomni o'zgartirmaydi)."""
    if not obj.name_ru:
        obj.name_ru = name_ru
        obj.save(update_fields=["name_ru"])


class Command(BaseCommand):
    help = "Farg'ona viloyati shahar/tumanlari va kategoriyalarni (o'zbekcha va ruscha) qo'shadi"

    @transaction.atomic
    def handle(self, *args, **options):
        added_cities = 0
        for (region_name, region_ru), cities in REGIONS.items():
            region, _ = Region.objects.get_or_create(name=region_name)
            fill_ru(region, region_ru)
            for name, name_ru in cities:
                city, created = City.objects.get_or_create(region=region, name=name)
                fill_ru(city, name_ru)
                added_cities += created

        added_categories = 0
        for order, ((section_name, section_ru), (section_icon, children)) in enumerate(CATEGORIES.items()):
            section, created = Category.objects.get_or_create(
                name=section_name, parent=None, defaults={"icon": section_icon, "order": order},
            )
            fill_ru(section, section_ru)
            added_categories += created
            for child_order, (name, name_ru, icon) in enumerate(children):
                child, created = Category.objects.get_or_create(
                    name=name, parent=section, defaults={"icon": icon, "order": child_order},
                )
                fill_ru(child, name_ru)
                added_categories += created

        self.stdout.write(self.style.SUCCESS(
            f"Tayyor: {added_cities} ta shahar/tuman, {added_categories} ta kategoriya qo'shildi "
            f"(oldin bor bo'lganlari o'tkazib yuborildi, bo'sh ruscha nomlar to'ldirildi)."
        ))
