from django.contrib import admin

# Register your models here.
from .models import User, UserProfile,UserDevice

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'phone_number', 'name', 'is_online', 'is_verified', 'is_active', 'is_staff','last_seen','date_joined',)
    search_fields = ('phone_number', 'name')
    list_filter = ('is_verified', 'is_active', 'is_staff')

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'display_name', 'bio')
    search_fields = ('display_name', 'bio')

@admin.register(UserDevice)
class UserDeviceAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'device_id', 'device_name', 'platform')
    search_fields = ('device_id', 'device_name', 'platform')
