"""
Til tanlash: ilova so'rovga "Accept-Language: ru" sarlavhasini qo'shadi —
shunda /api/ javoblari (kategoriya, shahar nomlari, xato xabarlari) ruscha bo'ladi.

Admin panel va boshqa sahifalar doim o'zbekcha (LANGUAGE_CODE) — admin brauzeri ruscha bo'lsa ham
panel aralash tilda chiqib qolmasligi uchun.
"""
from django.conf import settings
from django.utils import translation

SUPPORTED = {code for code, _ in settings.LANGUAGES}


def language_from_header(header):
    """'ru-RU,ru;q=0.9,en;q=0.8' -> 'ru'. Qo'llanmaydigan til bo'lsa — standart (uz)."""
    for part in (header or "").split(","):
        code = part.split(";")[0].strip().lower().split("-")[0]
        if code in SUPPORTED:
            return code
    return settings.LANGUAGE_CODE


class ApiLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/api/"):
            language = language_from_header(request.META.get("HTTP_ACCEPT_LANGUAGE"))
        else:
            language = settings.LANGUAGE_CODE
        translation.activate(language)
        request.LANGUAGE_CODE = language
        response = self.get_response(request)
        response.headers.setdefault("Content-Language", language)
        translation.deactivate()
        return response
