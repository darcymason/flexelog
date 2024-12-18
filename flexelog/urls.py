from django.urls import path

from . import views

app_name = "flexelog"
urlpatterns = [
    path("", views.index, name="index"),
    path("<str:lb>/<int:entry_id>", views.detail, name="detail"),
]