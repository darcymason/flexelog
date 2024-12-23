from django.contrib import admin

from .models import Entry, Logbook, ElogConfig
admin.site.register(ElogConfig)
admin.site.register(Logbook)
admin.site.register(Entry)
