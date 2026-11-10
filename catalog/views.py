"""
View — so'rov (request) kelganda nima qilishni hal qiladigan qism.
"""
from django.core.cache import cache
from django.db.models import Count, Exists, F, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.utils.translation import gettext as _
from .models import BusinessProfile, Category, City, Favorite, Listing, ListingImage, Region, Report, Subscription, Tariff
from .permissions import IsBusiness, IsBusinessOrReadOnly
from .serializers import (
    AuthResponseSerializer, BusinessLogoSerializer, BusinessProfileSerializer, BusinessPublicSerializer, CategorySerializer, ChangePasswordSerializer,
    CitySerializer, DeleteAccountSerializer, ListingImageSerializer, ListingSerializer, LoginSerializer,
    MapBusinessSerializer, ReportSerializer,
    RegionSerializer, RegisterSerializer, TariffSerializer, UserSerializer,
)
from .utils import normalize_text

MAX_IMAGES_PER_LISTING = 10
NO_SUBSCRIPTION_PRIORITY = 99  # obunasi yo'q bizneslar ro'yxat oxirida
VIEW_DEDUP_SECONDS = 24 * 60 * 60  # bitta odamning ko'rishi sutkada bir marta sanaladi


# ---------- Autentifikatsiya ----------

class RegisterView(APIView):
    """POST /api/auth/register/  {phone, password, role} -> {token, user}"""
    permission_classes = [AllowAny]

    @extend_schema(tags=["auth"], summary="Ro'yxatdan o'tish", request=RegisterSerializer,
                   responses={201: AuthResponseSerializer})
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _created = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": UserSerializer(user).data}, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """POST /api/auth/login/  {phone, password} -> {token, user}"""
    permission_classes = [AllowAny]

    @extend_schema(tags=["auth"], summary="Kirish", request=LoginSerializer,
                   responses={200: AuthResponseSerializer})
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token, _created = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": UserSerializer(user).data})


class LogoutView(APIView):
    """POST /api/auth/logout/  — tokenni o'chiradi, qaytadan login qilish kerak bo'ladi."""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["auth"], summary="Chiqish", request=None, responses={204: None})
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """GET /api/auth/me/  — hozir kim tizimga kirganini ko'rsatadi."""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["auth"], summary="Joriy foydalanuvchi", responses=UserSerializer)
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class ChangePasswordView(APIView):
    """
    POST /api/auth/change-password/  {old_password, new_password} -> {token, user}
    Eski token o'chadi (boshqa telefonlardagi kirishlar ham), javobda yangi token qaytadi.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["auth"], summary="Parolni o'zgartirish", request=ChangePasswordSerializer,
                   responses={200: AuthResponseSerializer})
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        Token.objects.filter(user=user).delete()
        token = Token.objects.create(user=user)
        return Response({"token": token.key, "user": UserSerializer(user).data})


class DeleteAccountView(APIView):
    """
    POST /api/auth/delete-account/  {password} -> 204
    Akkaunt, biznes profil, e'lonlar va rasmlar butunlay o'chadi.
    (App Store va Google Play ilovada shunday imkoniyat bo'lishini talab qiladi.)
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["auth"], summary="Akkauntni butunlay o'chirish", request=DeleteAccountSerializer,
                   responses={204: None})
    def post(self, request):
        serializer = DeleteAccountSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = request.user
        if user.is_staff or user.is_superuser:
            raise ValidationError({"detail": _("Admin akkauntini ilova orqali o'chirib bo'lmaydi.")})
        # Rasm fayllarini diskdan ham o'chiramiz (bazadagi yozuvlar CASCADE bilan o'chadi)
        for img in ListingImage.objects.filter(listing__business__user=user):
            img.delete_files()
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------- Ma'lumotnomalar (ochiq, faqat o'qish) ----------

def int_param(request, name):
    """URL'dagi ?name=5 parametrini butun songa aylantiradi. Yo'q bo'lsa None."""
    value = request.query_params.get(name)
    if value in (None, ""):
        return None
    if not value.isdigit():
        raise ValidationError({name: [_("Butun son bo'lishi kerak.")]})
    return int(value)


class RegionViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/regions/"""
    queryset = Region.objects.all()
    serializer_class = RegionSerializer
    permission_classes = [AllowAny]
    pagination_class = None  # ro'yxat kichik, sahifalash shart emas


class CityViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/cities/  (?region=1 — viloyat bo'yicha filtr)"""
    serializer_class = CitySerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        qs = City.objects.all()
        region = int_param(self.request, "region")
        if region is not None:
            qs = qs.filter(region_id=region)
        return qs


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/categories/  — hammasi bitta ro'yxatda: bo'limlar (parent=null) va ularning ichidagilar"""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    pagination_class = None


class TariffViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/tariffs/  — pullik tariflar va narxlari (obuna admin orqali ulanadi)"""
    queryset = Tariff.objects.all()
    serializer_class = TariffSerializer
    permission_classes = [AllowAny]
    pagination_class = None


# ---------- E'lonlar ----------

@extend_schema_view(
    list=extend_schema(summary="E'lonlar ro'yxati", parameters=[
        OpenApiParameter("city", OpenApiTypes.INT, description="Shahar/tuman id"),
        OpenApiParameter("category", OpenApiTypes.INT, description="Kategoriya id"),
        OpenApiParameter("region", OpenApiTypes.INT, description="Viloyat id"),
        OpenApiParameter("business", OpenApiTypes.INT, description="Biznes id (biznes sahifasidagi e'lonlar)"),
        OpenApiParameter("q", OpenApiTypes.STR, description="Qidiruv (sarlavha va izoh bo'yicha)"),
    ]),
    retrieve=extend_schema(summary="Bitta e'lon"),
    create=extend_schema(summary="E'lon qo'shish (biznes)"),
    update=extend_schema(summary="E'lonni to'liq tahrirlash (o'ziniki)"),
    partial_update=extend_schema(summary="E'lonni qisman tahrirlash (o'ziniki)"),
    destroy=extend_schema(summary="E'lonni o'chirish (o'ziniki)"),
)
class ListingViewSet(viewsets.ModelViewSet):
    """
    GET    /api/listings/              — hamma uchun (?city=, ?category=, ?region=, ?q=)
    GET    /api/listings/{id}/         — hamma uchun
    GET    /api/listings/mine/         — biznes: o'z e'lonlari (yashirinlari ham)
    GET    /api/listings/favorites/    — tizimga kirgan: sevimli e'lonlari
    POST/DELETE /api/listings/{id}/favorite/ — sevimlilarga qo'shish / olib tashlash
    POST   /api/listings/{id}/report/  — shikoyat (tizimga kirgan)
    POST   /api/listings/              — biznes: yangi e'lon
    PATCH  /api/listings/{id}/         — biznes: faqat o'z e'loni
    DELETE /api/listings/{id}/         — biznes: faqat o'z e'loni
    POST   /api/listings/{id}/images/  — biznes: rasm yuklash (multipart: image, order)
    DELETE /api/listings/{id}/images/{image_id}/ — biznes: rasmni o'chirish
    """
    serializer_class = ListingSerializer
    permission_classes = [IsBusinessOrReadOnly]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # Swagger hujjatini yaratish paytida
            return Listing.objects.none()
        qs = Listing.objects.select_related(
            "business__city", "business__category", "business__user",
        ).prefetch_related("images")
        user = self.request.user
        if user.is_authenticated:
            # "is_favorite" — har e'lon uchun alohida so'rov emas, bitta so'rovda
            qs = qs.annotate(favorited=Exists(Favorite.objects.filter(user=user, listing=OuterRef("pk"))))

        if self.action == "list":
            return self.filter_public(qs)
        if self.action in ("favorite", "favorites", "report"):
            return qs.filter(is_active=True, is_blocked=False, business__user__is_active=True)
        if self.action == "retrieve":
            # Hamma ko'ra oladigan e'lonlar + egasi o'zining yashirin/bloklangan e'lonini ham ochadi
            visible = Q(is_active=True, is_blocked=False, business__user__is_active=True)
            if self.request.user.is_authenticated:
                visible |= Q(business__user=self.request.user)
            return qs.filter(visible)

        # Qolgan barcha amallar (tahrirlash, o'chirish, rasm, mine) — faqat o'z e'lonlari.
        # Begona e'lon bu ro'yxatda yo'q, shuning uchun DRF avtomatik 404 qaytaradi.
        return qs.filter(business__user=self.request.user)

    def filter_public(self, qs):
        # 1) Ko'rinmaydiganlarni olib tashlaymiz
        qs = qs.filter(is_active=True, is_blocked=False, business__user__is_active=True)

        # 2) Filtrlar
        city = int_param(self.request, "city")
        if city is not None:
            qs = qs.filter(business__city_id=city)
        category = int_param(self.request, "category")
        if category is not None:
            # Bo'lim tanlansa — uning ichidagi barcha kategoriyalar ham ("Ustalar" -> santexnik, elektrik...)
            qs = qs.filter(Q(business__category_id=category) | Q(business__category__parent_id=category))
        region = int_param(self.request, "region")
        if region is not None:
            qs = qs.filter(business__city__region_id=region)
        business = int_param(self.request, "business")
        if business is not None:
            qs = qs.filter(business_id=business)

        # 3) Qidiruv: har bir so'z sarlavha yoki izohda bo'lishi kerak.
        #    "Do‘kon", "Doʻkon", "do'kon" — hammasi bir xil topiladi.
        for word in normalize_text(self.request.query_params.get("q", "")).split():
            qs = qs.filter(search_text__contains=word)

        # 4) Tartib: faol obunasi bor bizneslar avval (1-daraja, keyin 2-daraja),
        #    qolganlari keyin; har bir guruh ichida yangilari avval.
        now = timezone.now()
        best_level = (
            Subscription.objects
            .filter(business=OuterRef("business"), start__lte=now, end__gt=now)
            .order_by("tariff__level")
            .values("tariff__level")[:1]
        )
        qs = qs.annotate(
            priority=Coalesce(Subquery(best_level), Value(NO_SUBSCRIPTION_PRIORITY), output_field=IntegerField())
        )
        return qs.order_by("priority", "-created_at", "-id")

    def perform_create(self, serializer):
        business = getattr(self.request.user, "business", None)
        if business is None:
            raise ValidationError({"detail": _("Avval biznes profilingizni yarating: /api/business/me/")})
        serializer.save(business=business)

    def perform_destroy(self, instance):
        for img in instance.images.all():
            img.delete_files()  # rasm fayllarini diskdan ham o'chiramiz
        instance.delete()

    def retrieve(self, request, *args, **kwargs):
        listing = self.get_object()
        self.count_view(request, listing)
        return Response(self.get_serializer(listing).data)

    @staticmethod
    def count_view(request, listing):
        """Ko'rishni sanaydi: bitta odam (yoki IP) sutkada bir marta, egasining o'zi — hech qachon."""
        user = request.user
        if user.is_authenticated and listing.business.user_id == user.id:
            return
        who = f"u{user.id}" if user.is_authenticated else f"ip{request.META.get('REMOTE_ADDR', '')}"
        key = f"view:{listing.pk}:{who}"
        if cache.add(key, 1, timeout=VIEW_DEDUP_SECONDS):  # add — faqat kalit yo'q bo'lsa yozadi
            Listing.objects.filter(pk=listing.pk).update(views_count=F("views_count") + 1)
            listing.views_count += 1

    @extend_schema(summary="Mening e'lonlarim (biznes, yashirinlari ham) — ko'rishlar va ❤️ soni bilan")
    @action(detail=False, methods=["get"], permission_classes=[IsBusiness])
    def mine(self, request):
        qs = self.get_queryset().annotate(favorites_total=Count("favorites", distinct=True))
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @extend_schema(summary="Sevimli e'lonlarim (❤️)")
    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def favorites(self, request):
        # Oxirgi saqlangani birinchi. Keyin yashirilgan/bloklangan e'lonlar ro'yxatdan tushib qoladi.
        last_saved = Favorite.objects.filter(user=request.user, listing=OuterRef("pk")).values("created_at")[:1]
        qs = (self.get_queryset().filter(favorites__user=request.user)
              .annotate(saved_at=Subquery(last_saved)).order_by("-saved_at"))
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    @extend_schema(summary="Sevimlilarga qo'shish (POST) yoki olib tashlash (DELETE)", request=None,
                   responses={200: None, 201: None, 204: None})
    @action(detail=True, methods=["post", "delete"], permission_classes=[IsAuthenticated])
    def favorite(self, request, pk=None):
        listing = self.get_object()  # faqat ko'rinib turgan e'lonni saqlash mumkin
        if request.method == "DELETE":
            Favorite.objects.filter(user=request.user, listing=listing).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        _favorite, created = Favorite.objects.get_or_create(user=request.user, listing=listing)
        return Response({"is_favorite": True}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @extend_schema(summary="E'lon ustidan shikoyat", request=ReportSerializer, responses={201: None})
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def report(self, request, pk=None):
        listing = self.get_object()  # faqat ko'rinib turgan e'lon
        if listing.business.user_id == request.user.id:
            raise ValidationError({"detail": _("O'z e'loningiz ustidan shikoyat qilib bo'lmaydi.")})
        serializer = ReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Qayta yuborilsa — yangilanadi va yana "yangi" bo'ladi (admin qaytadan ko'radi)
        Report.objects.update_or_create(
            listing=listing, reporter=request.user,
            defaults={**serializer.validated_data, "status": Report.Status.NEW},
        )
        return Response({"detail": _("Shikoyatingiz qabul qilindi. Rahmat!")}, status=status.HTTP_201_CREATED)

    @extend_schema(summary="E'longa rasm yuklash (multipart)",
                   request={"multipart/form-data": ListingImageSerializer},
                   responses={201: ListingImageSerializer})
    @action(detail=True, methods=["post"], url_path="images", parser_classes=[MultiPartParser, FormParser])
    def upload_image(self, request, pk=None):
        listing = self.get_object()
        if listing.images.count() >= MAX_IMAGES_PER_LISTING:
            raise ValidationError({"image": _("Bitta e'longa ko'pi bilan %(n)s ta rasm.") % {"n": MAX_IMAGES_PER_LISTING}})
        serializer = ListingImageSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        serializer.save(listing=listing)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(summary="E'lon rasmini o'chirish", responses={204: None},
                   parameters=[OpenApiParameter("image_id", OpenApiTypes.INT, OpenApiParameter.PATH)])
    @action(detail=True, methods=["delete"], url_path=r"images/(?P<image_id>[0-9]+)")
    def delete_image(self, request, pk=None, image_id=None):
        listing = self.get_object()
        image = get_object_or_404(listing.images, pk=image_id)
        image.delete_files()
        image.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------- Biznes profil ----------

class MyBusinessView(APIView):
    """
    GET   /api/business/me/  — o'z profilini ko'rish
    POST  /api/business/me/  — profil yaratish (bir marta)
    PATCH /api/business/me/  — profilni tahrirlash (PUT ham ishlaydi)
    """
    permission_classes = [IsBusiness]

    def get_profile(self):
        profile = BusinessProfile.objects.filter(user=self.request.user).first()
        if profile is None:
            raise NotFound(_("Biznes profil hali yaratilmagan."))
        return profile

    @extend_schema(tags=["business"], summary="Mening biznes profilim", responses=BusinessProfileSerializer)
    def get(self, request):
        return Response(BusinessProfileSerializer(self.get_profile(), context={"request": request}).data)

    @extend_schema(tags=["business"], summary="Biznes profil yaratish", request=BusinessProfileSerializer,
                   responses={201: BusinessProfileSerializer})
    def post(self, request):
        if BusinessProfile.objects.filter(user=request.user).exists():
            raise ValidationError({"detail": _("Profil allaqachon mavjud. Tahrirlash uchun PATCH ishlating.")})
        serializer = BusinessProfileSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(tags=["business"], summary="Biznes profilni to'liq tahrirlash",
                   request=BusinessProfileSerializer, responses=BusinessProfileSerializer)
    def put(self, request):
        return self._update(request, partial=False)

    @extend_schema(tags=["business"], summary="Biznes profilni qisman tahrirlash",
                   request=BusinessProfileSerializer, responses=BusinessProfileSerializer)
    def patch(self, request):
        return self._update(request, partial=True)

    def _update(self, request, partial):
        serializer = BusinessProfileSerializer(self.get_profile(), data=request.data, partial=partial,
                                               context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class MyBusinessLogoView(APIView):
    """
    POST   /api/business/me/logo/  — logo yuklash (multipart: logo)
    DELETE /api/business/me/logo/  — logoni o'chirish
    """
    permission_classes = [IsBusiness]
    parser_classes = [MultiPartParser, FormParser]

    def get_profile(self):
        profile = BusinessProfile.objects.filter(user=self.request.user).first()
        if profile is None:
            raise NotFound(_("Biznes profil hali yaratilmagan."))
        return profile

    @extend_schema(tags=["business"], summary="Logo yuklash (multipart)",
                   request={"multipart/form-data": BusinessLogoSerializer}, responses=BusinessProfileSerializer)
    def post(self, request):
        profile = self.get_profile()
        serializer = BusinessLogoSerializer(profile, data=request.data)
        serializer.is_valid(raise_exception=True)
        old = profile.logo.name
        serializer.save()
        if old and old != profile.logo.name:
            profile.logo.storage.delete(old)  # eski logo faylini diskdan o'chiramiz
        return Response(BusinessProfileSerializer(profile, context={"request": request}).data)

    @extend_schema(tags=["business"], summary="Logoni o'chirish", request=None, responses={204: None})
    def delete(self, request):
        profile = self.get_profile()
        if profile.logo:
            profile.logo.delete(save=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


MAP_LIMIT = 1000  # xaritada bir vaqtda ko'pi bilan shuncha nuqta


@extend_schema_view(
    list=extend_schema(summary="Xarita: joylashuvi belgilangan bizneslar", parameters=[
        OpenApiParameter("category", OpenApiTypes.INT, description="Kategoriya yoki bo'lim id"),
        OpenApiParameter("city", OpenApiTypes.INT, description="Shahar/tuman id"),
    ]),
    retrieve=extend_schema(summary="Biznes sahifasi"),
)
class BusinessViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/businesses/            — xarita uchun: koordinatasi bor bizneslar (?category=, ?city=), sahifalanmaydi
    GET /api/businesses/{id}/       — biznes sahifasi (hammaga ochiq)
    E'lonlari: GET /api/listings/?business={id}
    """
    permission_classes = [AllowAny]
    pagination_class = None  # xaritaga hammasi birdan kerak (MAP_LIMIT bilan cheklangan)

    def get_serializer_class(self):
        return MapBusinessSerializer if self.action == "list" else BusinessPublicSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return BusinessProfile.objects.none()
        # Bloklangan foydalanuvchining biznesi ko'rinmaydi
        qs = BusinessProfile.objects.filter(user__is_active=True).select_related("city", "category")
        if self.action != "list":
            return qs
        qs = qs.filter(latitude__isnull=False, longitude__isnull=False).annotate(
            listings_count=Count("listings", filter=Q(listings__is_active=True, listings__is_blocked=False)),
        )
        category = int_param(self.request, "category")
        if category is not None:
            qs = qs.filter(Q(category_id=category) | Q(category__parent_id=category))
        city = int_param(self.request, "city")
        if city is not None:
            qs = qs.filter(city_id=city)
        return qs.order_by("-id")[:MAP_LIMIT]