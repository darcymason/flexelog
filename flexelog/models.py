from datetime import datetime
from binaryornot.helpers import is_binary_string
from pathlib import Path
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User

from textwrap import shorten
from configparser import ConfigParser

import logging 
logger = logging.getLogger("flexelog")


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
        unique=True,
    )
    config_text = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name}"



def validate_logbook_name(value):
    if value.lower() in RESERVED_LB_NAMES:
        raise ValidationError(
            _("'%(name)s' is reserved, it cannot be used for a logbook or logbook group name"),
            params={"name": value},
        )



class Logbook(models.Model):
    name = models.CharField(
        max_length=MAX_LOGBOOK_NAME,
        blank=False,
        validators=[validate_logbook_name],
        unique=True,
    )
    # logbookgroup_set for LogbookGroups
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
            ("configure_logbook", _("Configure logbook")),  # XX need to code this ability
        )

    def __str__(self):
        return (
            f"'{self.name}':   {self.comment}   order:{self.order} "
            f"{'   active' if self.active else ''} {'   readonly' if self.readonly else ''}"
            f"{'   auth-required' if self.auth_required else ''}"
            f"{'   unlisted' if self.is_unlisted else ''}"
        )
    def latest_date(self):
        return self.entries.latest("date").date  # XXX need to check if no entries
    
    @classmethod
    def active_logbooks(cls):
        return list(cls.objects.filter(active=True).order_by("order"))

    @property
    def slug_name(self):
        return slugify(self.name)

class LogbookGroup(models.Model):
    name = models.CharField(
        max_length=MAX_LOGBOOK_NAME,
        blank=False,
        null=False,
        validators=[validate_logbook_name],
        unique=True,
    )

    logbooks = models.ManyToManyField(Logbook)

    def __str__(self):
        show_limit = 3
        lb_names = [lb.name for lb in self.logbooks.all()]
        member_list = ", ".join(lb_names[:show_limit]) + (", ..." if len(lb_names) > show_limit else "" )
        return f"'{self.name}'" + (" = " + member_list if member_list else "")
    
    @property
    def slug_name(self):
        return slugify(self.name)

class Entry(models.Model):
    fixed_attr_names = ["date", "id", "author", "text"]
    rowid = models.AutoField(primary_key=True, blank=True)
    lb = models.ForeignKey(Logbook, on_delete=models.PROTECT, related_name="entries")
    id = models.IntegerField(blank=False, null=False)
    date = models.DateTimeField()
    author = models.ForeignKey(User, on_delete=models.DO_NOTHING, null=True, blank=True, related_name="entries") # XX should never delete authors
    last_modified_author = models.ForeignKey(User, on_delete=models.DO_NOTHING, blank=True, null=True, related_name="entries_modified") # XX should never delete authors
    last_modified_date = models.DateTimeField(blank=True, null=True)
    attrs = models.JSONField(default=dict, null=True)
    in_reply_to = models.ForeignKey("self", models.SET_NULL, blank=True, null=True, related_name="replies")
    encoding = models.TextField(blank=True, null=True)
    locked_by = models.TextField(blank=True, null=True)
    text = models.TextField(blank=True, null=True)
    # attachments

    def get(self, attr_name, default=None):
        if attr_name.lower() in self.fixed_attr_names:
            return getattr(self, attr_name.lower())
        else:
            return self.attrs.get(attr_name.lower(), default=default) if self.attrs else default
   
    def __str__(self):
        return (
            f"{self.lb.name} {self.id}: {self.date} {shorten(str(self.attrs) or "", 20)} "
            f"{shorten(self.text or "", 30)}"
        )
    
    def reply_ancestor(self):
        """Return self, or first ancestor that is not a reply to another entry"""
        root = self
        while root.in_reply_to:
            root = root.in_reply_to
        return root

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("lb", "id"), name="id in logbook")
        ]
        verbose_name = _("Entry")
        verbose_name_plural = _("Entries")
        indexes = [
            models.Index(fields=["lb", "-id"]),
            models.Index(fields=["lb", "-date"])
        ]


def upload_path(instance, filename):
    """Folder/filename to store"""
    # Making this similar to what PSI elog used but adding logbook name folder.
    # Can't use entry id (if a new entry, id doesn't exist yet). Similarly for the attachment pk.
    # But logbook is for sure known.
    return (
        f"attachments/{instance.entry.lb.slug_name}"
        f"/{timezone.now().year}"
        f"/{filename}"
    )


class Attachment(models.Model):
    IMAGE_SUFFIXES = (
        {".jpg", ".jpeg", ".png", ".svg", ".gif"} |  # PSI elog supported
        {".apng", ".avif", ".jfif", ".pjpeg", ".pjp", ".webp"}  # also accepted by most browsers
        # https://developer.mozilla.org/en-US/docs/Web/HTML/Element/img 2023-10
    )

    entry = models.ForeignKey(Entry, related_name="attachments", verbose_name=_("entry"), on_delete=models.CASCADE)
    attachment_file = models.FileField(
        _("Attachment"), upload_to=upload_path, blank=True, null=True
    )
    uploaded = models.DateTimeField(_("uploaded"), auto_now_add=True)

    class Meta:
        verbose_name = _("attachment")
        verbose_name_plural = _("attachments")
        ordering = ["uploaded"]

    def __str__(self):
        return self.attachment_file.name

    @property
    def display_filename(self):
        if not self.attachment_file.name:
            return ""
        return Path(self.attachment_file.name).name
    
    def exists(self):
        return self.attachment_file.storage.exists(self.attachment_file.name)
    
    def is_image(self):
        """Simple check of extension to see if is a supported image"""
        if not self.exists():
            return False

        return Path(self.attachment_file.name).suffix.lower() in self.IMAGE_SUFFIXES

    def suffix(self):
        if not self.exists():
            return ""
        return Path(self.attachment_file.name).suffix.lower()

    def is_ascii(self):
        if not self.exists():
            return False

        return not is_binary_string(self.attachment_file.read(1024))


    def is_viewable(self):
        if not self.attachment_file.storage.exists(self.attachment_file.name):
            return False

        return (
            self.is_image() or self.is_ascii()
        ) and self.suffix not in (".ps", ".pdf")
