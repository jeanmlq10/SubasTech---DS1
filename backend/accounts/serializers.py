from django.contrib.auth import get_user_model
from rest_framework import serializers

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

    def validate(self, attrs):
        attrs = super().validate(attrs)
        role = attrs.get("role")
        trade = attrs.get("technician_trade", "")

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
