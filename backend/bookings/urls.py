from django.urls import path
from . import views

urlpatterns = [
    path("session/<int:session_id>/book/", views.book_session, name="book-session"),
    path("mine/", views.my_bookings, name="my-bookings"),
    path("<int:booking_id>/cancel/", views.cancel_booking, name="cancel-booking"),
]
