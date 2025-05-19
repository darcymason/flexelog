from django.urls import include, path


from flexelog import views

app_name = "flexelog"
urlpatterns = [
    path("accounts/", include("django.contrib.auth.urls")),
    path("accounts/do_logout", views.do_logout, name="do_logout"),
    path("", views.index, name="index"),
    path("<str:lb_name>/", views.logbook_or_new_edit_delete_post, name="logbook"),
    path("<str:lb_name>/<int:entry_id>/", views.entry_detail, name="entry_detail"),
    path("test/<str:lb_name>/<int:entry_id>/", views.test, name="test"),
]