from django.urls import include, path


from . import views

app_name = "flexelog"
urlpatterns = [
    path("accounts/", include("django.contrib.auth.urls")),
    path("accounts/do_logout", views.do_logout, name="do_logout"),
    path("", views.index, name="index"),
    path("<str:lb_name>/", views.logbook, name="logbook"),
    path("<str:lb_name>/<int:entry_id>/", views.detail, name="detail"),
]