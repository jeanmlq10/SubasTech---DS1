from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "technician_trade",
            "phone_number",
            "address",
            "telegram_chat_id",
            "whatsapp_id",
        ]
        read_only_fields = ["id"]


class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=8)
    allowed_public_roles = {User.Role.CLIENT, User.Role.TECHNICIAN}

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "role", "technician_trade", "phone_number", "address"]
        read_only_fields = ["id"]

    def validate_role(self, value):
        if value not in self.allowed_public_roles:
            allowed = ", ".join(sorted(self.allowed_public_roles))
            raise serializers.ValidationError(
                f"Public registration is only allowed for these roles: {allowed}."
            )
        return value

    def validate_email(self, value):
        email = (value or "").strip().lower()
        if email and User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return email

    def validate(self, attrs):
        attrs = super().validate(attrs)
        role = attrs.get("role")
        trade = attrs.get("technician_trade", "")
        email = attrs.get("email", "")

        if role == User.Role.CLIENT and not email:
            raise serializers.ValidationError({"email": "Client registration requires an email."})

        if role == User.Role.TECHNICIAN and not trade:
            raise serializers.ValidationError({"technician_trade": "Technician profession is required."})

        if role != User.Role.TECHNICIAN:
            attrs["technician_trade"] = ""

        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class EmailOrUsernameTokenObtainPairSerializer(TokenObtainPairSerializer):
    email = serializers.EmailField(required=False)
    username = serializers.CharField(required=False, allow_blank=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[self.username_field].required = False
        self.fields[self.username_field].allow_blank = True

    def validate(self, attrs):
        login = (attrs.get("email") or attrs.get("username") or "").strip()
        password = attrs.get("password")

        if not login:
            raise serializers.ValidationError({"email": "Email or username is required."})

        user = self._find_user(login)
        if user is None:
            raise AuthenticationFailed(self.error_messages["no_active_account"], "no_active_account")

        return super().validate({"username": user.get_username(), "password": password})

    def _find_user(self, login: str):
        if "@" in login:
            return User.objects.filter(email__iexact=login).first()
        return User.objects.filter(username=login).first()
