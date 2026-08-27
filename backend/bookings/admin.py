from django.contrib import admin
from .models import Booking, BookingEvent, IdempotencyRecord


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "session", "status", "request_id", "created_at"]
    list_filter = ["status"]
    search_fields = ["user__username", "session__title"]


@admin.register(BookingEvent)
class BookingEventAdmin(admin.ModelAdmin):
    list_display = ["event_type", "session", "user", "request_id", "created_at"]
    list_filter = ["event_type"]


@admin.register(IdempotencyRecord)
class IdempotencyRecordAdmin(admin.ModelAdmin):
    list_display = ["key", "user", "session", "response_status", "created_at"]
