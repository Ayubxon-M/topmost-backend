"""Yordamchi funksiyalar: telefon raqami va qidiruv matnini bir xil ko'rinishga keltirish."""
import re

# O'zbek lotin yozuvida o' va g' harflari turlicha yoziladi:
# o'  o‘  oʻ  oʼ  o’  o`  — hammasini oddiy ' ga almashtiramiz.
APOSTROPHES = "‘’ʻʼ`´"
_APOSTROPHE_TABLE = str.maketrans({ch: "'" for ch in APOSTROPHES})


def normalize_text(text):
    """Qidiruv uchun matnni kichik harfga o'tkazadi va apostroflarni birlashtiradi."""
    if not text:
        return ""
    return text.translate(_APOSTROPHE_TABLE).lower().strip()


def normalize_phone(phone):
    """
    Telefon raqamini +998XXXXXXXXX ko'rinishiga keltiradi.

    Qabul qilinadigan misollar:
        "+998 90 123-45-67", "998901234567", "90 123 45 67", "(90) 1234567"
    Noto'g'ri bo'lsa None qaytaradi.
    """
    if not phone:
        return None
    digits = re.sub(r"\D", "", str(phone))  # faqat raqamlarni qoldiramiz
    if len(digits) == 9:
        digits = "998" + digits
    if len(digits) == 12 and digits.startswith("998"):
        return "+" + digits
    return None
