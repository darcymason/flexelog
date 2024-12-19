from django.db import models
from django.conf import settings

from textwrap import shorten

# Create your models here.

MAX_LOGBOOK_NAME = getattr(settings, "MAX_LOGBOOK_NAME", 50)

class Entry(models.Model):
    rowid = models.AutoField(primary_key=True, blank=True)
    lb = models.TextField(blank=True)
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
    class Meta:
        managed = False
        db_table = 'Entries'

class Logbook(models.Model):
    name = models.CharField(max_length=MAX_LOGBOOK_NAME, blank=False)
    config = models.TextField(blank=True, null=True)
    def __str__(self):
        return (
            f"'{self.name}':   {self.config}"
        )

def logbook_names():
    return list(Entry.objects.values_list("lb", flat=True).distinct())