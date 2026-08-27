from django.contrib import admin
from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["username", "email", "role", "github_id", "date_joined"]
    list_filter = ["role"]
    search_fields = ["username", "email"]
    readonly_fields = ["github_id", "date_joined"]
