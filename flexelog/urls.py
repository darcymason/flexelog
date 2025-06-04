from django.conf import settings
from django.urls import include, path, re_path
from django.views.static import serve
from flexelog import views



app_name = "flexelog"
urlpatterns = [
    path("accounts/", include("django.contrib.auth.urls")),
    path("accounts/do_logout", views.do_logout, name="do_logout"),
    path("", views.index, name="index"),
    path("<str:lb_name>/", views.logbook_view, name="logbook"),
    path("<str:lb_name>/<int:entry_id>/", views.entry_detail, name="entry_detail"),
    path("test/<str:lb_name>/<int:entry_id>/", views.test, name="test"),
    re_path("^attachments/", include('attachments.urls', namespace='attachments')),
]

if settings.DEBUG:
    urlpatterns += [
        re_path(
            r"^media/(?P<path>.*)$",
            serve,
            {
                "document_root": settings.MEDIA_ROOT,
            },
        ),
    ]