"""
Zaxira nusxa:  python manage.py backup

Baza (db.sqlite3) va e'lon rasmlari (media/) bitta zip faylga yig'iladi:
    backups/topmost-2026-11-07_0300.zip
Backend ishlab turgan paytda ham xavfsiz (SQLite'ning o'z nusxalash usuli ishlatiladi).
Eng yangi BACKUP_KEEP ta nusxa qoladi, eskilari o'chiriladi.

Sozlamalar (.env):
    BACKUP_DIR=D:\\topmost-backups   — qayerga saqlansin (standart: loyiha ichida backups/)
    BACKUP_KEEP=14                  — nechta nusxa saqlansin

Maslahat: BACKUP_DIR ni boshqa diskka yoki fleshkaga qo'ying — server diski buzilsa ham nusxa qoladi.
"""
import os
import sqlite3
import tempfile
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = "Baza va rasmlarning zaxira nusxasini zip faylga saqlaydi"

    def handle(self, *args, **options):
        db = settings.DATABASES["default"]
        if db["ENGINE"] != "django.db.backends.sqlite3":
            raise CommandError("Bu buyruq faqat SQLite baza uchun.")

        backup_dir = Path(os.environ.get("BACKUP_DIR") or settings.BASE_DIR / "backups")
        keep = int(os.environ.get("BACKUP_KEEP", "14"))
        backup_dir.mkdir(parents=True, exist_ok=True)

        stamp = timezone.localtime().strftime("%Y-%m-%d_%H%M%S")
        target = backup_dir / f"topmost-{stamp}.zip"
        partial = target.with_suffix(".zip.part")  # tugamaguncha boshqa nom — yarim fayl "tayyor" ko'rinmaydi

        with tempfile.TemporaryDirectory() as tmp:
            # 1) Bazaning bir lahzadagi to'liq nusxasi
            db_copy = Path(tmp) / "db.sqlite3"
            src = sqlite3.connect(db["NAME"])
            dst = sqlite3.connect(db_copy)
            try:
                src.backup(dst)
            finally:
                dst.close()
                src.close()

            # 2) Zip: baza + media papkasi
            media_root = Path(settings.MEDIA_ROOT)
            files = 0
            with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(db_copy, "db.sqlite3")
                if media_root.exists():
                    for path in media_root.rglob("*"):
                        if path.is_file():
                            zf.write(path, Path("media") / path.relative_to(media_root))
                            files += 1
        partial.replace(target)

        # 3) Eski nusxalarni o'chirish
        old = sorted(backup_dir.glob("topmost-*.zip"))[:-keep] if keep > 0 else []
        for path in old:
            path.unlink()

        size_mb = target.stat().st_size / 1024 / 1024
        self.stdout.write(self.style.SUCCESS(
            f"Tayyor: {target} ({size_mb:.1f} MB, {files} ta rasm). O'chirilgan eski nusxalar: {len(old)}."
        ))
