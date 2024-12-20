from django.contrib import admin

from .models import Entry, Logbook, GeneralConfig
admin.site.register(GeneralConfig)
admin.site.register(Logbook)
admin.site.register(Entry)
