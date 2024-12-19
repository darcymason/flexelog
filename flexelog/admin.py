from django.contrib import admin

from .models import Entry, Logbook
admin.site.register(Logbook)
admin.site.register(Entry)
