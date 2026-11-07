"""
Serverda (ofis kompyuterida) backend'ni ishga tushirish:  python serve.py

"python manage.py runserver" faqat dasturlash uchun. Bu fayl esa waitress
orqali ishga tushiradi: ko'p so'rovni bir vaqtda ko'taradi, Windows'da ham,
Linux'da ham ishlaydi. Port va boshqa sozlamalar .env faylidan olinadi.
"""
import os

from waitress import serve

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from django.conf import settings  # noqa: E402
from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()

if __name__ == '__main__':
    host = os.environ.get('HOST', '0.0.0.0')  # 0.0.0.0 — tarmoqdagi boshqa qurilmalar ham ulanadi
    port = int(os.environ.get('PORT', '8000'))
    if settings.DEBUG:
        print("DIQQAT: DEBUG=True. Serverda .env ichida DEBUG=False qiling.")
    print(f"TOPMOST backend ishga tushdi: http://{host}:{port}/  (to'xtatish: Ctrl+C)")
    options = {}
    proxy = os.environ.get('TRUSTED_PROXY', '').strip()
    if proxy:
        # nginx yoki boshqa proksi orqasida tursa, haqiqiy HTTPS/IP ma'lumotini undan oladi
        options = {'trusted_proxy': proxy, 'trusted_proxy_headers': {'x-forwarded-proto', 'x-forwarded-for'}}
    serve(
        application,
        host=host,
        port=port,
        threads=8,
        clear_untrusted_proxy_headers=True,
        max_request_body_size=20 * 1024 * 1024,  # 20 MB — rasm yuklash uchun yetarli
        **options,
    )
