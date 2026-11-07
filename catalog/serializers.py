"""
Serializer — Python obyektini JSON'ga (va aksincha) aylantiruvchi "tarjimon".
Kelgan ma'lumotni tekshirish (validatsiya) ham shu yerda.
"""
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import User
from .utils import normalize_phone


# ---------- Autentifikatsiya ----------

class UserSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(source="username", read_only=True)
    has_business_profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "phone", "role", "has_business_profile"]

    def get_has_business_profile(self, user):
        return hasattr(user, "business")


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
        validate_password(attrs["password"], user=User(username=attrs["phone"]))
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
