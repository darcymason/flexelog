from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from textwrap import shorten

# Create your models here.

MAX_LOGBOOK_NAME = getattr(settings, "MAX_LOGBOOK_NAME", 50)

def validate_logbook_name(value):
    if value.lower() in ['admin', 'user']:
        raise ValidationError(
            _("'%(value)s' is reserved, it cannot be used for a logbook name"),
            params={"value": value.lower()},
        )

class Logbook(models.Model):
    name = models.CharField(max_length=MAX_LOGBOOK_NAME, blank=False, validators=[validate_logbook_name])
    comment = models.CharField(max_length=50, blank=True)
    config = models.TextField(blank=True, null=True)
    def __str__(self):
        return (
            f"'{self.name}':   {self.comment}"
        )


class Entry(models.Model):
    rowid = models.AutoField(primary_key=True, blank=True)
    lb = models.ForeignKey(Logbook, on_delete=models.PROTECT)
    id = models.IntegerField(blank=True, null=True)
    date = models.TextField(blank=True, null=True)
    attrs = models.JSONField(blank=True, null=True)
    reply_to = models.IntegerField(blank=True, null=True)
    encoding = models.TextField(blank=True, null=True)
    attachments = models.JSONField(blank=True, null=True)
    locked_by = models.TextField(blank=True, null=True)
    text = models.TextField(blank=True, null=True)

    def __str__(self):
        return (
            f"{self.lb} {self.id}: {self.date} {self.attrs} "
            f"{shorten(self.text, 50)}"
        )


def logbook_names():
    return list(Entry.objects.values_list("lb", flat=True).distinct())