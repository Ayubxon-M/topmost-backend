from django.http import Http404
from rest_framework.exceptions import NotFound
from rest_framework.views import exception_handler as drf_exception_handler


def exception_handler(exc, context):
    """
    DRF'ning standart xato ishlovchisi, bitta farq bilan:
    "No Listing matches the given query." (inglizcha, model nomi bilan) o'rniga
    {"detail": "Topilmadi."} qaytaradi.
    """
    if isinstance(exc, Http404):
        exc = NotFound()
    return drf_exception_handler(exc, context)
