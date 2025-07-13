from django.conf import settings
from django.contrib import admin
from django.contrib.admin import StackedInline

from guardian.admin import GuardedModelAdmin

from .models import Entry, LogbookGroup, Logbook, ElogConfig, Attachment


class ElogConfigAdmin(admin.ModelAdmin):
    def get_changeform_initial_data(self, request):
        return {
            'config_text': settings.GLOBAL_CONFIG_INITIAL
        }



class LogbookAdmin(GuardedModelAdmin):
    def get_changeform_initial_data(self, request):
        return {
            'config': settings.LOGBOOK_CONFIG_INITIAL
        }

class AttachmentInline(StackedInline):
    model = Attachment


class EntryAdmin(admin.ModelAdmin):
    inlines = (AttachmentInline,)


admin.site.register(ElogConfig, ElogConfigAdmin)
admin.site.register(LogbookGroup)
admin.site.register(Logbook, LogbookAdmin)
admin.site.register(Entry, EntryAdmin)
admin.site.register(Attachment)
