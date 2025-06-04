from django.contrib import admin
from guardian.admin import GuardedModelAdmin

from .models import Entry, LogbookGroup, Logbook, ElogConfig
from attachments.admin import AttachmentInlines

class LogbookAdmin(GuardedModelAdmin):
    pass


class EntryAdmin(admin.ModelAdmin):
    inlines = (AttachmentInlines,)


admin.site.register(ElogConfig)
admin.site.register(LogbookGroup)
admin.site.register(Logbook, LogbookAdmin)
admin.site.register(Entry, EntryAdmin)

