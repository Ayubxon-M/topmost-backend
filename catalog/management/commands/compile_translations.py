"""
python manage.py compile_translations

locale/**/django.po (odam o'qiydigan tarjima fayli) -> django.mo (Django o'qiydigan fayl).
Django'ning `compilemessages` buyrug'i GNU gettext (msgfmt) dasturini talab qiladi,
Windows'da u odatda yo'q. Bu buyruq xuddi shu ishni sof Python'da qiladi.

.po faylni o'zgartirgandan keyin shu buyruqni ishga tushiring va serverni qayta yoqing.
"""
import ast
import struct
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


def parse_po(path):
    """.po faylni {msgid: msgstr} lug'atiga aylantiradi (ko'plik shakllari ham)."""
    messages = {}
    entry = {}
    key = None

    def flush():
        if "msgid" in entry:
            msgid = entry["msgid"]
            if "msgid_plural" in entry:
                msgid += "\0" + entry["msgid_plural"]
                strs = [entry[k] for k in sorted(k for k in entry if k.startswith("msgstr["))]
                msgstr = "\0".join(strs)
            else:
                msgstr = entry.get("msgstr", "")
            # Tarjimasi bo'sh qatorlar o'tkazib yuboriladi (header — msgid "" bundan mustasno)
            if msgstr.replace("\0", "") or msgid == "":
                messages[msgid] = msgstr
        entry.clear()

    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            if not line:
                flush()
                key = None
            continue
        if line.startswith('"'):
            entry[key] += ast.literal_eval(line)
            continue
        key, _, value = line.partition(" ")
        if key == "msgid" and "msgid" in entry:
            flush()
        entry[key] = ast.literal_eval(value)
    flush()
    return messages


def write_mo(messages, path):
    """GNU .mo formatida yozadi."""
    keys = sorted(messages)
    ids = b""
    strs = b""
    offsets = []
    for k in keys:
        kb, vb = k.encode("utf-8"), messages[k].encode("utf-8")
        offsets.append((len(ids), len(kb), len(strs), len(vb)))
        ids += kb + b"\0"
        strs += vb + b"\0"
    n = len(keys)
    keystart = 7 * 4 + 16 * n
    valuestart = keystart + len(ids)
    koffsets, voffsets = [], []
    for o1, l1, o2, l2 in offsets:
        koffsets += [l1, o1 + keystart]
        voffsets += [l2, o2 + valuestart]
    output = struct.pack("Iiiiiii", 0x950412DE, 0, n, 7 * 4, 7 * 4 + n * 8, 0, 0)
    output += struct.pack(f"{len(koffsets)}i", *koffsets)
    output += struct.pack(f"{len(voffsets)}i", *voffsets)
    output += ids + strs
    Path(path).write_bytes(output)


class Command(BaseCommand):
    help = "locale/ ichidagi .po tarjima fayllarini .mo ga kompilyatsiya qiladi (msgfmt kerak emas)."

    def handle(self, *args, **options):
        found = False
        for locale_dir in settings.LOCALE_PATHS:
            for po in Path(locale_dir).rglob("*.po"):
                found = True
                messages = parse_po(po)
                write_mo(messages, po.with_suffix(".mo"))
                self.stdout.write(self.style.SUCCESS(f"{po} -> .mo ({len(messages) - 1} ta tarjima)"))
        if not found:
            self.stdout.write(self.style.WARNING("Hech qanday .po fayl topilmadi."))
