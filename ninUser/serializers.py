from rest_framework import serializers
from .models import User, UserProfile, UserDevice


# ──────────────────────────────────────────
# REQUEST SERIALIZERS
# ──────────────────────────────────────────

class SignUpSerializer(serializers.Serializer):

    password = serializers.CharField(write_only=True, min_length=6)

    # id_token = serializers.CharField(
    #     write_only=True,
    #     help_text="Firebase ID token received after OTP verification"
    # )
    phone_number = serializers.CharField(
        max_length=20,
        help_text="Phone number in E.164 format, e.g. +8801XXXXXXXXX"
    )
    name = serializers.CharField(
        max_length=50,
        help_text="User's full name"
    )
    platform = serializers.ChoiceField(
        choices=['android', 'ios'],
        help_text="Platform of the user's device"
    )
    device_name = serializers.CharField(
        max_length=100,
        help_text="Name of the user's device"
    )
    device_id = serializers.CharField(
        max_length=255,
        help_text="Unique device identifier for multi-device login"
    )


    def validate_phone_number(self, value):
        if not value.startswith('+'):
            raise serializers.ValidationError(
                "Phone number must be in E.164 format (e.g. +8801XXXXXXXXX)."
            )
        return value

class SignInRequestSerializer(serializers.Serializer):
    phone_number = serializers.CharField(
        max_length=20,
        help_text="Phone number in E.164 format, e.g. +8801XXXXXXXXX"
    )
    password = serializers.CharField(write_only=True)

class SignInSerializer(serializers.Serializer):
    id_token = serializers.CharField(
        write_only=True,
        help_text="Firebase ID token received after OTP verification"
    )
    device_name = serializers.CharField(
        max_length=100,
        help_text="Name of the user's device"
    )
    device_id = serializers.CharField(
        max_length=255,
        help_text="Unique device identifier for multi-device login"
    )
    platform = serializers.ChoiceField(
        choices=['android', 'ios'],
        help_text="Platform of the user's device"
    )


# ──────────────────────────────────────────
# RESPONSE SERIALIZERS
# ──────────────────────────────────────────

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            'display_name', 'bio', 'avatar', 'gender',
            'date_of_birth', 'website', 'location',
            'is_private', 'show_last_seen', 'show_read_receipts',
            'allow_calls_from',
        ]
        read_only_fields = fields

class UserPlatformSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDevice
        fields = ['platform', 'device_name', 'device_id']
        read_only_fields = fields


class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    platform = UserPlatformSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'phone_number', 'name',
            'is_verified', 'date_joined', 'last_seen', 'profile', 'platform'
        ]
        read_only_fields = fields


class TokenSerializer(serializers.Serializer):
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)


class AuthResponseSerializer(serializers.Serializer):
    """Used as the response body for SignUp and SignIn."""
    user = UserSerializer(read_only=True)
    tokens = TokenSerializer(read_only=True)