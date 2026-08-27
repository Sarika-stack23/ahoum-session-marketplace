"""
Serializers for user accounts.
"""
from rest_framework import serializers
from .models import User


class UserSerializer(serializers.ModelSerializer):
    """Public user representation."""

    class Meta:
        model = User
        fields = ["id", "username", "email", "role", "avatar_url", "bio", "date_joined"]
        read_only_fields = ["id", "username", "email", "role", "date_joined"]


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Allows users to update their own profile.
    Role is NOT editable through this endpoint — it is controlled
    via management command or CREATOR_EMAILS env var.
    """

    class Meta:
        model = User
        fields = ["username", "bio", "avatar_url"]

    def validate_username(self, value):
        user = self.context["request"].user
        if User.objects.filter(username=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value
