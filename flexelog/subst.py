# subst.py
import re
from flexelog.elog_cfg import get_config

def subst(subst_text, logbook, user=None, entry=None):
    # Full list from PSI elog help
    # Implemented:
    # $<attribute>: The entered value of the attribute itself
    # $short_name: The login name (if password file is present)
    # $long_name: The full name from the password file for the current user
    # $user_email: The email address from the password file for the current user
    # $logbook: The name of the current logbook
    # $date: The current date, formatted via "Date format"
    # $utcdate: The current UTC date (GMT) and time, formatted via "Date format"
    # $version: The version of the ELOG server in the form x.y.z

    # Not implementing, just return the subst pattern:
    # $revision: The Subversion reversion of the ELOG server as an integer number
    # $shell(<command>): <command> gets passed to the operating system shell and the result is taken for substitution.
    # $host: The host name where elogd is running
    # $remote_host: The host name of the host from with the entry was submitted
    
    # XX could remove the trailing \b on matches (word boundary),
    # but then should order substitutions by longest string first,
    # in case of user-defined attributes with same substrings

    if "$" not in subst_text:
        return subst_text
    
    cfg = get_config()
    if entry:
        for attr_name, val in entry.attrs.items():
            if isinstance(val, list):
                val = " | ".join(val)
            subst_text = re.sub(rf"(\${attr_name})\b", str(val), subst_text, flags=re.IGNORECASE)
    
    return subst_text