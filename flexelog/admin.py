from django.contrib import admin
from guardian.admin import GuardedModelAdmin

from .models import Entry, Logbook, ElogConfig


class LogbookAdmin(GuardedModelAdmin):
    pass

admin.site.register(ElogConfig)
admin.site.register(Entry)

admin.site.register(Logbook, LogbookAdmin)


