from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

# Router ViewSet'lar uchun URL'larni avtomatik yaratadi (/listings/, /listings/{id}/ va h.k.)
router = DefaultRouter()
router.register("regions", views.RegionViewSet, basename="region")
router.register("cities", views.CityViewSet, basename="city")
router.register("categories", views.CategoryViewSet, basename="category")
router.register("listings", views.ListingViewSet, basename="listing")

urlpatterns = [
    path("auth/register/", views.RegisterView.as_view(), name="register"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/me/", views.MeView.as_view(), name="me"),
    path("auth/change-password/", views.ChangePasswordView.as_view(), name="change-password"),
    path("auth/delete-account/", views.DeleteAccountView.as_view(), name="delete-account"),
    path("business/me/", views.MyBusinessView.as_view(), name="my-business"),
    path("", include(router.urls)),
]
