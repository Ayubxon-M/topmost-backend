"""
Serverga o'rnatgandan keyin tekshiruv:  python manage.py check_server

Har bir band uchun ✅ (joyida) yoki ❌ (tuzatish kerak) va nima qilish kerakligi chiqadi.
Hammasi ✅ bo'lsa — backend foydalanuvchilarga tayyor.
"""
import os
import sys
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from catalog.models import Category, City, Tariff, User


class Command(BaseCommand):
    help = "Server sozlamalarini tekshiradi (production'ga tayyormi)"

    def handle(self, *args, **options):
        # Windows terminali ✅ belgisini chiqara olmasa — UTF-8 ga o'tkazamiz
        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass
        self.failed = 0

        self.stdout.write(self.style.MIGRATE_HEADING("\n1. Xavfsizlik"))
        self.item("DEBUG o'chirilgan", not settings.DEBUG, ".env ichida DEBUG=False qiling")
        self.item("Maxfiy kalit (SECRET_KEY) o'rnatilgan",
                   "insecure" not in settings.SECRET_KEY and len(settings.SECRET_KEY) >= 40,
                   "DEPLOY.md 3-qadam: yangi kalit yaratib .env ga yozing")
        self.item("ALLOWED_HOSTS — aniq domen", bool(settings.ALLOWED_HOSTS) and "*" not in settings.ALLOWED_HOSTS,
                   ".env: ALLOWED_HOSTS=api.topmost.uz (sizning domeningiz)")
        self.item("HTTPS yoqilgan", getattr(settings, "SECURE_SSL_REDIRECT", False),
                   "HTTPS ulangach .env ichida HTTPS=True qiling (DEPLOY.md 7-bo'lim)", warn_only=True)
        self.item("CSRF_TRUSTED_ORIGINS (admin panel uchun)",
                   any(o.startswith("https://") for o in settings.CSRF_TRUSTED_ORIGINS),
                   ".env: CSRF_TRUSTED_ORIGINS=https://api.topmost.uz", warn_only=True)

        self.stdout.write(self.style.MIGRATE_HEADING("\n2. Baza va fayllar"))
        executor = MigrationExecutor(connection)
        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
        self.item("Barcha migratsiyalar qo'llangan", not pending, "python manage.py migrate")
        static_ok = Path(settings.STATIC_ROOT, "staticfiles.json").exists()
        self.item("Static fayllar yig'ilgan (admin panel dizayni)", static_ok or settings.DEBUG,
                   "python manage.py collectstatic --noinput")
        self.item("Rasmlar papkasi (media) yozishga ochiq", self.writable(Path(settings.MEDIA_ROOT)),
                   f"{settings.MEDIA_ROOT} papkasiga yozish huquqini bering")
        backup_dir = Path(os.environ.get("BACKUP_DIR") or Path(settings.BASE_DIR) / "backups")
        self.item(f"Backup papkasi yozishga ochiq ({backup_dir})", self.writable(backup_dir),
                   ".env: BACKUP_DIR ni boshqa diskdagi papkaga qo'ying (DEPLOY.md 8-bo'lim)")

        self.stdout.write(self.style.MIGRATE_HEADING("\n3. Ma'lumotlar"))
        self.item("Admin (superuser) bor", User.objects.filter(is_superuser=True).exists(),
                   "python manage.py createsuperuser")
        self.item("Shahar va tumanlar bor", City.objects.exists(), "python manage.py load_initial_data")
        self.item("Kategoriyalar bor", Category.objects.exists(), "python manage.py load_initial_data")
        self.item("Kategoriyalarning ruscha nomlari bor",
                   not Category.objects.filter(name_ru="").exists(),
                   "python manage.py load_initial_data (bo'sh ruscha nomlarni to'ldiradi) yoki admin paneldan",
                   warn_only=True)
        self.item("Tariflar qo'shilgan", Tariff.objects.exists(), "Admin panel → Tariflar → Qo'shish",
                   warn_only=True)
        self.item("Maxfiylik sahifasida aloqa ko'rsatilgan", bool(settings.PRIVACY_CONTACT),
                   ".env: PRIVACY_CONTACT=Telegram @... yoki telefon")

        self.stdout.write("")
        if self.failed:
            self.stdout.write(self.style.ERROR(f"❌ {self.failed} ta band tuzatilishi kerak. Yuqoridagi ko'rsatmalarga qarang."))
        else:
            self.stdout.write(self.style.SUCCESS("✅ Hammasi joyida — backend foydalanuvchilarga tayyor!"))

    def item(self, label, ok, fix, warn_only=False):
        if ok:
            self.stdout.write(f"  ✅ {label}")
            return
        mark = "⚠️ " if warn_only else "❌"
        self.stdout.write(f"  {mark} {label}\n       → {fix}")
        if not warn_only:
            self.failed += 1

    @staticmethod
    def writable(path):
        try:
            path.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=path):
                pass
            return True
        except OSError:
            return False
