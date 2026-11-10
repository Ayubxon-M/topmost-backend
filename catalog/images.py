"""Rasmning kichik nusxasi (thumbnail): ro'yxatdagi kartalar uchun ~30-40 KB JPEG."""
from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

THUMBNAIL_SIZE = 480  # eng katta tomoni, piksel (2 ustunli kartaga yetarli)


def build_thumbnail(field_file):
    """
    Rasm faylidan (ImageField qiymati) kichik nusxa yasaydi: (fayl nomi, ContentFile) yoki None.
    Telefon rasmi yonboshlab qolgan bo'lsa (EXIF) — to'g'rilanadi; shaffof PNG — oq fonda.
    """
    # Yangi yuklangan fayl hali diskka yozilmagan — Django uni keyin saqlaydi, shuning uchun YOPMAYMIZ,
    # faqat boshiga qaytaramiz. Diskdagi faylni (eski rasmlar) esa o'zimiz ochib-yopamiz.
    stored = getattr(field_file, "_committed", True)
    try:
        if stored:
            field_file.open()
        with Image.open(field_file) as img:
            img = ImageOps.exif_transpose(img)
            img.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE))
            if img.mode != "RGB":
                background = Image.new("RGB", img.size, "white")
                rgba = img.convert("RGBA")
                background.paste(rgba, mask=rgba.getchannel("A"))
                img = background
            buf = BytesIO()
            img.save(buf, "JPEG", quality=80, optimize=True)
    except (OSError, ValueError):
        return None  # rasmni o'qib bo'lmasa — kartada to'liq rasm ko'rsatiladi
    finally:
        if stored:
            field_file.close()
        else:
            field_file.seek(0)
    return Path(field_file.name).stem + "_thumb.jpg", ContentFile(buf.getvalue())
