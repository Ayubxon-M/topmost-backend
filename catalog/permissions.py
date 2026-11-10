"""
Permission — "bu foydalanuvchi bu ishni qila oladimi?" degan savolga javob.
"""
from django.utils.translation import gettext_lazy as _
from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsBusiness(BasePermission):
    """Faqat tizimga kirgan va role=business bo'lgan foydalanuvchi."""
    message = _("Bu amal faqat biznes akkauntlar uchun.")

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_business)


class IsBusinessOrReadOnly(IsBusiness):
    """O'qish (GET) — hammaga. Yozish (POST/PUT/PATCH/DELETE) — faqat biznesga."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return super().has_permission(request, view)
