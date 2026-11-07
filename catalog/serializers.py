"""
Serializer — Python obyektini JSON'ga (va aksincha) aylantiruvchi "tarjimon".
Kelgan ma'lumotni tekshirish (validatsiya) ham shu yerda.
"""
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import BusinessProfile, Category, City, Listing, ListingImage, Region, User
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
            raise serializers.ValidationError("Telefon raqami noto'g'ri. Masalan: +998901234567")
        if User.objects.filter(username=phone).exists():
            raise serializers.ValidationError("Bu telefon raqami bilan allaqachon ro'yxatdan o'tilgan.")
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
            raise serializers.ValidationError("Telefon raqami yoki parol noto'g'ri.")
        attrs["user"] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_old_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Joriy parol noto'g'ri.")
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
            raise serializers.ValidationError("Parol noto'g'ri.")
        return value


# ---------- Ma'lumotnomalar ----------

class RegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = ["id", "name"]


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ["id", "name", "region"]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name"]


# ---------- Biznes profil ----------

class BusinessPublicSerializer(serializers.ModelSerializer):
    """E'lon ichida ko'rinadigan biznes ma'lumoti. Kontaktlar faqat tizimga kirganlarga."""
    city = CitySerializer(read_only=True)
    category = CategorySerializer(read_only=True)

    class Meta:
        model = BusinessProfile
        fields = ["id", "name", "phone", "telegram_username", "city", "category"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        if not (request and request.user.is_authenticated):
            data["phone"] = None
            data["telegram_username"] = None
        return data


class BusinessProfileSerializer(serializers.ModelSerializer):
    """Biznes egasi o'z profilini yaratishi/tahrirlashi uchun."""

    class Meta:
        model = BusinessProfile
        fields = ["id", "name", "phone", "telegram_username", "city", "category", "created_at"]
        read_only_fields = ["created_at"]

    def validate_phone(self, value):
        phone = normalize_phone(value)
        if not phone:
            raise serializers.ValidationError("Telefon raqami noto'g'ri. Masalan: +998901234567")
        return phone

    def validate_telegram_username(self, value):
        return value.strip().lstrip("@")


# ---------- E'lonlar ----------

class ListingImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ListingImage
        fields = ["id", "image", "order"]


class ListingSerializer(serializers.ModelSerializer):
    business = BusinessPublicSerializer(read_only=True)
    images = ListingImageSerializer(many=True, read_only=True)

    class Meta:
        model = Listing
        fields = [
            "id", "title", "description", "price", "is_active", "is_blocked",
            "created_at", "updated_at", "business", "images",
        ]
        # is_blocked'ni faqat admin o'zgartiradi
        read_only_fields = ["is_blocked", "created_at", "updated_at"]
