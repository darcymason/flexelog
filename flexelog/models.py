from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User

from textwrap import shorten
from configparser import ConfigParser, UNNAMED_SECTION


MAX_LOGBOOK_NAME = getattr(settings, "MAX_LOGBOOK_NAME", 50)
RESERVED_LB_NAMES = ["admin", "user", "accounts"]



def validate_config_section(value):
    # Make sure is readable as ConfigParser lines, without section headers
    cp = ConfigParser(allow_unnamed_section=True, interpolation=None)
    cp.optionxform = str  # strings are case sensitive
    error = ""
    try:
        cp.read_string(value)
    except Exception as e:
        msg = _("Syntax error in config file")
        raise ValidationError(f'{msg}: {str(e)}')



class ElogConfig(models.Model):
    name = models.CharField(
        max_length=50,
        choices=[
            ("global", "Default config for all logbooks if not otherwise specified")
        ],  # XX later could have different configs
        
    )
    config_text = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name}"


def validate_logbook_name(value):
    if value.lower() in RESERVED_LB_NAMES:
        raise ValidationError(
            _("'%(value)s' is reserved, it cannot be used for a logbook name"),
            params={"value": value.lower()},
        )


class Logbook(models.Model):
    name = models.CharField(
        max_length=MAX_LOGBOOK_NAME,
        blank=False,
        validators=[validate_logbook_name],
        unique=True,
    )
    comment = models.CharField(max_length=50, blank=True)
    config = models.TextField(blank=True, null=True)

    # The following override any permissions set for Groups or Users
    active = models.BooleanField(default=True, help_text=_("If False, logbook cannot be viewed or edited"))
    readonly = models.BooleanField(default=False, help_text=_("If True, logbook is frozen, but existing entries can be viewed"))
    auth_required = models.BooleanField(default=True, help_text=_("If False, anyone can view or edit this logbook without login"))
    is_unlisted = models.BooleanField(default=False, help_text=_("If True, don't show in logbook index"))
    order = models.IntegerField(default=999, help_text=_("Logbooks will be listed in increasing order if specified"))

    class Meta:
        indexes = [ models.Index(fields=["name"])]
        verbose_name = _("Logbook")
        verbose_name_plural = _("Logbooks")

        # Permissions below are set for each logbook instance,
        # using django-guardian
        # (https://django-guardian.readthedocs.io/en/stable/userguide/assign/#for-group)
        permissions = (
            ("view_entries", _("View entries")),
            ("add_entries", _("Add entries")),
            ("edit_own_entries", _("Edit own entries")),
            ("edit_others_entries", _("Edit others' entries")),
            ("delete_own_entries", _("Delete own entries")),
            ("delete_others_entries", _("Delete others' entries")),
        )

    def __str__(self):
        return (
            f"'{self.name}':   {self.comment}   order:{self.order} "
            f"{'   active' if self.active else ''} {'   readonly' if self.readonly else ''}"
            f"{'   auth-required' if self.auth_required else ''}"
            f"{'   unlisted' if self.is_unlisted else ''}"
        )
    def latest_date(self):
        return self.entry_set.latest("date").date  # XXX need to check if no entries
    
    @classmethod
    def active_logbooks(cls):
        return list(cls.objects.filter(active=True).order_by("order"))


class Entry(models.Model):
    rowid = models.AutoField(primary_key=True, blank=True)
    lb = models.ForeignKey(Logbook, on_delete=models.PROTECT)
    id = models.IntegerField(blank=False, null=False)
    date = models.DateTimeField()
    author = models.ForeignKey(User, on_delete=models.DO_NOTHING, null=True) # XX should never delete authors, ## temp
    last_modified_author = models.ForeignKey(User, on_delete=models.DO_NOTHING, null=True, related_name="modified_entry") # XX should never delete authors, ## temp
    last_modified_date = models.DateTimeField(null=True)
    attrs = models.JSONField(blank=True, null=True)
    reply_to = models.IntegerField(blank=True, null=True)
    encoding = models.TextField(blank=True, null=True)
    attachments = models.JSONField(blank=True, null=True)
    locked_by = models.TextField(blank=True, null=True)
    text = models.TextField(blank=True, null=True)

    def __str__(self):
        return (
            f"{self.lb} {self.id}: {self.date} {self.attrs} "
            f"{shorten(self.text or "", 50)}"
        )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("lb", "id"), name="id in logbook")
        ]
        verbose_name = _("Entry")
        verbose_name_plural = _("Entries")
        indexes = [
            models.Index(fields=["lb", "-id"]),
        ]


def logbook_names():
    return list(Entry.objects.values_list("lb", flat=True).distinct())

