# subst.py

import datetime
from django.utils.translation import gettext as _
from django.utils import formats, timezone

from importlib.metadata import version
import re
from flexelog.elog_cfg import get_config
from flexelog.models import Logbook, Entry, User

def subst(subst_text: str, logbook: Logbook, user: User, entry: Entry | None = None):
    # Full list from PSI elog help
    # Implemented:
    # $<attribute>: The entered value of the attribute itself
    # $short_name: The login name (if password file is present)
    # $long_name: The full name from the password file for the current user
    # $user_email: The email address from the password file for the current user
    # $logbook: The name of the current logbook
    # $date: The current date, formatted via  "Time format"  ~~"Date format"~~
    # $utcdate: The current UTC date (GMT) and time, formatted via "Time format"  ~~"Date format"~~
    # $version: The version of the ELOG server in the form x.y.z

    # Not implementing, just return the subst pattern:
    # $revision: The Subversion reversion of the ELOG server as an integer number
    # $shell(<command>): <command> gets passed to the operating system shell and the result is taken for substitution.
    # $host: The host name where elogd is running
    # $remote_host: The host name of the host from with the entry was submitted
    
    # XX could remove the trailing \b on matches (word boundary),
    # but then should order substitutions by longest string first,
    # in case of user-defined attributes with same substrings
    def local_date_str():
        date = timezone.localtime()
        date_format = cfg.get(logbook, "Time format")
        if date_format:
            try:
                return date.strftime(date_format)
            except ValueError:
                return str(formats.localize(date, use_l10n=True))    
        else:
            return str(formats.localize(date, use_l10n=True))
    
    def utc_date_str():
        # oddly, django doesn't seem to have a guaranteed way to get UTC
        #  so get using Python's recommended way.
        date = datetime.datetime.now(datetime.timezone.utc)
        date_format = cfg.get(logbook, "Time format")
        if date_format:
            return date.strftime(date_format)
        else:
            return str(date)

    if "$" not in subst_text:
        return subst_text
    
    cfg = get_config()
    if entry:
        for attr_name, val in entry.attrs.items():
            if isinstance(val, list):
                val = " | ".join(val)
            subst_text = re.sub(rf"(\${attr_name})\b", str(val), subst_text, flags=re.IGNORECASE)
    
    # User-related ones
    subst_text = re.sub(
        rf"\$short_name",
        user.get_username() if not user.is_anonymous else _("Anonymous"),
        subst_text,
        flags=re.IGNORECASE
    )

    subst_text = re.sub(
        rf"\$long_name",
        user.get_full_name() if not user.is_anonymous else _("Anonymous"),
        subst_text,
        flags=re.IGNORECASE
    )

    subst_text = re.sub(
        rf"\$user_email",
        user.email if not user.is_anonymous else "",
        subst_text,
        flags=re.IGNORECASE
    )
    
    # Logbook
    subst_text = re.sub(rf"\$logbook", logbook.name, subst_text, flags=re.I)
    
    # Dates
    subst_text = re.sub(rf"\$date", local_date_str(), subst_text, flags=re.I)
    subst_text = re.sub(rf"\$utcdate", utc_date_str(), subst_text, flags=re.I)

    subst_text = re.sub(rf"\$version", version("flexelog"), subst_text, flags=re.I)
    
    return subst_text