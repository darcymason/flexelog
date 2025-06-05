from django.contrib import admin
from django.contrib.admin import StackedInline

from guardian.admin import GuardedModelAdmin

from .models import Entry, LogbookGroup, Logbook, ElogConfig, Attachment

class LogbookAdmin(GuardedModelAdmin):
    pass

class AttachmentInline(StackedInline):
    model = Attachment


class EntryAdmin(admin.ModelAdmin):
    inlines = (AttachmentInline,)


admin.site.register(ElogConfig)
admin.site.register(LogbookGroup)
admin.site.register(Logbook, LogbookAdmin)
admin.site.register(Entry, EntryAdmin)
admin.site.register(Attachment)
