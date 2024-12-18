from django.db import models

from textwrap import shorten

# Create your models here.

class Entry(models.Model):
    rowid = models.AutoField(primary_key=True, blank=True)
    lb = models.TextField(blank=True)
    id = models.IntegerField(blank=True, null=True)
    date = models.DateField(blank=True, null=True)
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

def logbook_names():
    return list(Entry.objects.values_list("lb", flat=True).distinct())