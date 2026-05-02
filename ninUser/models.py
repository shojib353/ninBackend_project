import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    def create_user(self, phone_number,password=None, **extra_fields):
        if not phone_number:
            raise ValueError('Phone number is required')
        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)   # 🔐 hash password
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_verified', True)
        return self.create_user(phone_number, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone_number = models.CharField(max_length=20, unique=True, db_index=True)
    name = models.CharField(max_length=50,blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_online = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)  # Phone OTP verified
    date_joined = models.DateTimeField(default=timezone.now)
    last_seen = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []  # No additional fields required for superuser creation

    objects = UserManager()

    class Meta:
        db_table = 'users'
        verbose_name = _('User')
        verbose_name_plural = _('Users')

    def __str__(self):
        return self.phone_number

    def update_last_seen(self):
        self.last_seen = timezone.now()
        self.save(update_fields=['last_seen'])


class UserProfile(models.Model):
    """Extended profile data."""
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female'), ('O', 'Other'), ('N', 'Prefer not to say')]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    display_name = models.CharField(max_length=100)
    bio = models.TextField(max_length=500, blank=True)
    avatar = models.ImageField(upload_to='avatars/%Y/%m/', null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    website = models.URLField(blank=True)
    location = models.CharField(max_length=100, blank=True)
    is_private = models.BooleanField(default=False)
    show_last_seen = models.BooleanField(default=True)
    show_read_receipts = models.BooleanField(default=True)
    allow_calls_from = models.CharField(
        max_length=20,
        choices=[('everyone', 'Everyone'), ('contacts', 'Contacts'), ('nobody', 'Nobody')],
        default='everyone'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_profiles'

    def __str__(self):
        return f'{self.user.name} Profile'


class UserDevice(models.Model):
    """Tracks devices for multi-device login & push notifications."""
    PLATFORM_CHOICES = [('android', 'Android'), ('ios', 'iOS'), ('web', 'Web')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices')
    device_id = models.CharField(max_length=255, db_index=True)
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES)
    device_name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    last_active = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'user_devices'
        unique_together = ('user', 'device_id')

    def __str__(self):
        return f'{self.user.name} - {self.platform} ({self.device_id[:8]}...)'


