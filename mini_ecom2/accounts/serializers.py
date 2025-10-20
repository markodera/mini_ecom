from rest_framework import serializers
from .models import CustomUser, UserProfile
from rest_framework.response import Response


class CustomUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(style={"input_type": "password"}, write_only=True)
    password2 = serializers.CharField(style={"input_type": "password"}, write_only=True)

    class Meta:
        model = CustomUser
        fields = [
            "username",
            "email",
            "password",
            "password2",
        ]

    def validate(self, attrs):
        password = attrs.get("password")
        password2 = attrs.get("password2")

        if password != password2:
            raise serializers.ValidationError(({"passwords do not match"}))
        return attrs

    def create(self, validate_data):
        validate_data.pop("password2", None)

        user = CustomUser.objects.create_user(**validate_data)
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = "__all__"
