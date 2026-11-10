"""
Serializer — Python obyektini JSON'ga (va aksincha) aylantiruvchi "tarjimon".
Kelgan ma'lumotni tekshirish (validatsiya) ham shu yerda.
"""
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from django.utils.translation import get_language
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from django.utils.translation import gettext as _
from .models import BusinessProfile, Category, City, Listing, ListingImage, Region, Report, Subscription, Tariff, User
from .utils import normalize_phone


# ---------- Autentifikatsiya ----------

class UserSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(source="username", read_only=True)
    has_business_profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "phone", "role", "has_business_profile"]

    def get_has_business_profile(self, user) -> bool:
        return hasattr(user, "business")


class AuthResponseSerializer(serializers.Serializer):
    """register va login javobi (faqat hujjat uchun)."""
    token = serializers.CharField()
    user = UserSerializer()


class RegisterSerializer(serializers.Serializer):
    phone = serializers.CharField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    role = serializers.ChoiceField(choices=User.Role.choices, default=User.Role.CLIENT)

    def validate_phone(self, value):
        phone = normalize_phone(value)
        if not phone:
            raise serializers.ValidationError(_("Telefon raqami noto'g'ri. Masalan: +998901234567"))
        if User.objects.filter(username=phone).exists():
            raise serializers.ValidationError(_("Bu telefon raqami bilan allaqachon ro'yxatdan o'tilgan."))
        return phone

    def validate(self, attrs):
        # Django'ning parol qoidalari (juda qisqa, juda oddiy, faqat raqam va h.k.)
        try:
            validate_password(attrs["password"], user=User(username=attrs["phone"]))
        except DjangoValidationError as e:
            # Xatolar "password" maydoni ostida qaytadi — ilova ularni parol maydoni tagida ko'rsatadi
            raise serializers.ValidationError({"password": list(e.messages)})
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data["phone"],
            password=validated_data["password"],
            role=validated_data["role"],
        )


class LoginSerializer(serializers.Serializer):
    phone = serializers.CharField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs):
        phone = normalize_phone(attrs["phone"])
        # authenticate() bloklangan (is_active=False) foydalanuvchini ham None qaytaradi
        user = authenticate(self.context.get("request"), username=phone, password=attrs["password"]) if phone else None
        if user is None:
            raise serializers.ValidationError(_("Telefon raqami yoki parol noto'g'ri."))
        attrs["user"] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_old_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError(_("Joriy parol noto'g'ri."))
        return value

    def validate_new_password(self, value):
        try:
            validate_password(value, user=self.context["request"].user)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value


class DeleteAccountSerializer(serializers.Serializer):
    """Akkauntni tasodifan o'chirib yubormaslik uchun parol so'raladi."""
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError(_("Parol noto'g'ri."))
        return value


# ---------- Ma'lumotnomalar ----------

class LocalizedNameMixin:
    """
    "name" — so'rov tiliga qarab: ruscha so'ralsa (Accept-Language: ru) va name_ru to'ldirilgan bo'lsa —
    ruscha nom, aks holda o'zbekcha. Ilova uchun maydon nomi o'zgarmaydi — doim "name".
    """

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if get_language() == "ru" and getattr(instance, "name_ru", ""):
            data["name"] = instance.name_ru
        return data


class RegionSerializer(LocalizedNameMixin, serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = ["id", "name"]


class CitySerializer(LocalizedNameMixin, serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ["id", "name", "region"]


class CategorySerializer(LocalizedNameMixin, serializers.ModelSerializer):
    class Meta:
        model = Category
        # parent: null — bo'lim; aks holda bo'lim id'si. icon — ilovadagi belgi nomi.
        fields = ["id", "name", "parent", "icon"]


# ---------- Biznes profil ----------

BUSINESS_PAGE_FIELDS = [
    "description", "address", "logo", "latitude", "longitude",
    "work_days", "opens_at", "closes_at", "is_24_7", "is_open_now",
]


class BusinessPublicSerializer(serializers.ModelSerializer):
    """Biznes sahifasi va e'lon ichidagi biznes ma'lumoti. Kontaktlar hammaga (mehmonga ham) ochiq."""
    city = CitySerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    # true — ochiq, false — yopiq, null — ish vaqti ko'rsatilmagan
    is_open_now = serializers.BooleanField(read_only=True, allow_null=True)

    class Meta:
        model = BusinessProfile
        fields = ["id", "name", "phone", "telegram_username", "city", "category", *BUSINESS_PAGE_FIELDS]


class TariffSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tariff
        fields = ["id", "name", "level", "price", "duration_days"]


class SubscriptionSerializer(serializers.ModelSerializer):
    tariff = TariffSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = ["id", "tariff", "start", "end"]


class MapBusinessSerializer(BusinessPublicSerializer):
    """Xarita nuqtasi: biznes ma'lumoti + nechta e'loni bor."""
    listings_count = serializers.IntegerField(read_only=True)

    class Meta(BusinessPublicSerializer.Meta):
        fields = [*BusinessPublicSerializer.Meta.fields, "listings_count"]

class BusinessProfileSerializer(serializers.ModelSerializer):
    """Biznes egasi o'z profilini yaratishi/tahrirlashi uchun."""
    # Hozir amalda bo'lgan eng yuqori darajali obuna (yo'q bo'lsa null). Faqat o'qish uchun.
    subscription = serializers.SerializerMethodField()

    is_open_now = serializers.BooleanField(read_only=True, allow_null=True)

    class Meta:
        model = BusinessProfile
        fields = ["id", "name", "phone", "telegram_username", "city", "category", *BUSINESS_PAGE_FIELDS,
                  "created_at", "subscription"]
        # Logo alohida yuklanadi: POST /api/business/me/logo/ (multipart)
        read_only_fields = ["created_at", "logo"]

    def validate_work_days(self, value):
        days = "".join(sorted(set(value)))
        if any(d not in "1234567" for d in days):
            raise serializers.ValidationError(_("Faqat 1–7 raqamlari: 1 — dushanba, 7 — yakshanba."))
        return days

    def validate(self, attrs):
        current = self.instance
        get = lambda name: attrs[name] if name in attrs else getattr(current, name, None)
        lat, lng = get("latitude"), get("longitude")
        if (lat is None) != (lng is None):
            raise serializers.ValidationError({"latitude": _("Kenglik va uzunlik birga kiritiladi.")})
        if lat is not None and not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise serializers.ValidationError({"latitude": _("Koordinata noto'g'ri.")})
        if (get("opens_at") is None) != (get("closes_at") is None):
            raise serializers.ValidationError({"opens_at": _("Ochilish va yopilish vaqti birga kiritiladi.")})
        if get("opens_at") is not None and get("opens_at") == get("closes_at"):
            raise serializers.ValidationError({"closes_at": _("Yopilish vaqti ochilishdan farq qilishi kerak (24 soat uchun «24/7» ni belgilang).")})
        return attrs

    @extend_schema_field(SubscriptionSerializer(allow_null=True))
    def get_subscription(self, profile):
        now = timezone.now()
        sub = (profile.subscriptions.select_related("tariff")
               .filter(start__lte=now, end__gt=now).order_by("tariff__level", "-end").first())
        return SubscriptionSerializer(sub).data if sub else None

    def validate_phone(self, value):
        phone = normalize_phone(value)
        if not phone:
            raise serializers.ValidationError(_("Telefon raqami noto'g'ri. Masalan: +998901234567"))
        return phone

    def validate_telegram_username(self, value):
        return value.strip().lstrip("@")


MAX_IMAGE_MB = 8  # bitta rasm ko'pi bilan (ilova rasmlarni ~300 KB gacha kichraytiradi)


def validate_image_size(image):
    if image.size > MAX_IMAGE_MB * 1024 * 1024:
        raise serializers.ValidationError(_("Rasm juda katta: ko'pi bilan %(mb)s MB.") % {"mb": MAX_IMAGE_MB})
    return image


class BusinessLogoSerializer(serializers.ModelSerializer):
    logo = serializers.ImageField(validators=[validate_image_size])

    class Meta:
        model = BusinessProfile
        fields = ["logo"]


# ---------- E'lonlar ----------

class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ["reason", "comment"]


class ListingImageSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(validators=[validate_image_size])

    class Meta:
        model = ListingImage
        fields = ["id", "image", "order"]


class ListingSerializer(serializers.ModelSerializer):
    business = BusinessPublicSerializer(read_only=True)
    images = ListingImageSerializer(many=True, read_only=True)
    # Tizimga kirgan foydalanuvchi bu e'lonni ❤️ saqlaganmi (mehmonga doim false)
    is_favorite = serializers.SerializerMethodField()
    # Faqat /api/listings/mine/ da (biznes o'z e'lonini nechta odam saqlaganini ko'radi), boshqa joyda null
    favorites_count = serializers.SerializerMethodField()

    class Meta:
        model = Listing
        fields = [
            "id", "title", "description", "price_type", "price", "is_active", "is_blocked",
            "created_at", "updated_at", "business", "images", "is_favorite", "views_count", "favorites_count",
        ]
        # is_blocked'ni faqat admin o'zgartiradi
        read_only_fields = ["is_blocked", "created_at", "updated_at", "views_count"]

    def get_favorites_count(self, listing) -> int | None:
        return getattr(listing, "favorites_total", None)

    def get_is_favorite(self, listing) -> bool:
        annotated = getattr(listing, "favorited", None)  # ro'yxatda bitta so'rov bilan hisoblanadi
        if annotated is not None:
            return annotated
        request = self.context.get("request")
        if not (request and request.user.is_authenticated):
            return False
        return listing.favorites.filter(user=request.user).exists()

    def validate(self, attrs):
        # Narx turi ko'rsatilmay, faqat narx yuborilsa (eski ilova) — "aniq narx" deb hisoblaymiz.
        # Aks holda "kelishilgan" e'longa yuborilgan narx jimgina o'chib ketardi.
        current_type = getattr(self.instance, "price_type", Listing.PriceType.NEGOTIABLE)
        if "price_type" not in attrs and attrs.get("price") is not None and current_type not in Listing.PRICED_TYPES:
            attrs["price_type"] = Listing.PriceType.FIXED
        price_type = attrs.get("price_type", getattr(self.instance, "price_type", Listing.PriceType.NEGOTIABLE))
        price = attrs["price"] if "price" in attrs else getattr(self.instance, "price", None)
        if price_type in Listing.PRICED_TYPES and price is None:
            raise serializers.ValidationError({"price": _("Bu narx turi uchun narxni kiriting.")})
        return attrs
