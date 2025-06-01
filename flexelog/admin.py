from django.contrib import admin
from guardian.admin import GuardedModelAdmin

from .models import Entry, LogbookGroup, Logbook, ElogConfig


class LogbookAdmin(GuardedModelAdmin):
    pass

admin.site.register(ElogConfig)
admin.site.register(LogbookGroup)
admin.site.register(Logbook, LogbookAdmin)
admin.site.register(Entry)

