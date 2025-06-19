# psi_psi_log.py
from dataclasses import dataclass
import datetime
import xml.etree.ElementTree as ET  # for pwd file

from typing import Generator
from pathlib import Path
import re
from email.utils import parsedate_to_datetime  # for rfc2822 dates

from flexelog.elog_cfg import Attribute

import logging
logger = logging.getLogger("PSI")

ENTRY_MARKER = "$@MID@$:"


RESERVED_ATTRIBUTES = [
    "id",
    "text",
    "date",
    "encoding",
    "reply to",
    "locked by",
    "in reply to",
    "attachment",
]


def parse_pwd_file(filename) -> list[dict[str, str]]:
    """Return list of user information from the PSI password file
    For each user, returns dict with the tags and their values,
    which from examples seen should include 'name, 'full_name', 'email',
    'password' (not useful), 'last_logout', 'last_activity', 
    'inactive' (0=False) and 'email_notify' (possibly None value).
    """
    tree = ET.parse(filename)
    root = tree.getroot()
    users = []
    for user in root:
        di = {}
        for item in user:
            di[item.tag] = item.text
        users.append(di)
    return users


@dataclass
class PSIEntry:
    """Store info from a PSI elog entry"""

    id: int
    date: datetime.datetime
    attrs: dict[str, str | list]
    in_reply_to: list[int]
    replies: list[int]
    encoding: str
    attachments: list[str]
    locked_by: str
    text: str


class PSILogbook:
    def __init__(
        self,
        name: str,
        path: str | Path,
        cfg_attributes: dict[str, Attribute] | None = None,
    ):
        self.name = name
        self.path = Path(path)
        if not self.path.is_dir():
            raise IOError(
                f"Logbook path '{str(self.path)}' is not a folder"
            )
        self.cfg_attributes = cfg_attributes or {}

    def entries(self) -> Generator[PSIEntry, None, None]:
        """Yield the entries across an entire logbook"""
        for folder in self._get_years():
            yield from self._folder_entries(folder)

    def _get_years(self) -> list[str]:
        # Collect all the year folders - each is just 4-digit year, e.g. 2022, 2023
        return sorted(
            (
                p.name
                for p in self.path.glob("[0-9][0-9][0-9][0-9]")
                if p.is_dir()
            )
        )

    def _folder_entries(self, folder) -> Generator[PSIEntry, None, None]:
        path = self.path / folder
        old_format_files = list(path.glob("[0-9][0-9][0-9][0-9][0-9][0-9].log"))
        if old_format_files:
            msg = (
                f"Found older format (YYMMDD.log) files in folder '{folder}' for logbook '{self.name}'. Cannot convert. "
                "Please see PSI elog's `elconv` program or submit an issue to flexelog's issue list"
            )
            logger.error(msg)
            raise OSError(msg)
        log_filenames = sorted(p.name for p in path.glob("[0-9][0-9][0-9][0-9][0-9][0-9]a.log"))
        yield from self._fileset_entries(path, log_filenames)

    def _fileset_entries(self, path, filenames):
        for filename in filenames:
            yield from self.filename_entries(path / filename)

    def filename_entries(self, filename: str | Path) -> list[PSIEntry]:
        """Parse a file on disk and return matching `Entry`s in it"""
        # File format is like:
        # $@MID@$: <id>
        # Date: Sun, 30 Jul 2023 23:00:44 -0400
        # Attribute1: Attr Value 1
        # Attribute2: Attr Value 2
        # Attribute3: Attr Value 3
        # Attachment: <comma-separated list of filenames>
        # Encoding: <ELCode / HTML / plain>, but we're adding markdown
        # ========================================
        # Text of body
        # $@MID@$: <id+1>
        # ...
        # Note: no separator for body text ending.  Just end of file, or $@...
        filepath = Path(filename)
        timestamp = filepath.stat().st_mtime

        with open(filename, "r") as f:
            entries = []
            line = next(f)
            more_entries = True
            while more_entries:
                while line.strip() == "":
                    line = next(f)
                if not line.startswith(ENTRY_MARKER):
                    raise IOError(
                        f"Expected elog header starting with {ENTRY_MARKER}"
                    )
                entry_id = int(line.split(":", maxsplit=1)[1].strip())

                line = next(f)

                attrs = {}
                # Get attributes section
                while not line.startswith("="):
                    attr, value = line.split(":", maxsplit=1)
                    attrs[attr] = value.strip()
                                
                    line = next(f)

                # Parse out the non-dynamic attributes
                # Date
                val = attrs.pop("Date", "")
                if val:
                    date = parsedate_to_datetime(val)
                else:  # Should never happen, but just in case, have a backup
                    logger.warning(f"No date found in message {entry.id}, file '{filename}'.  Using file date and UTC.")
                    date = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
                
                tzinfo = date.tzinfo
                # Do some processing on attributes
                for attr, value in attrs.items():
                    # Turn MOptions val into list, others to str
                    cfg_Attrib = self.cfg_attributes.get(attr)
                    if cfg_Attrib and cfg_Attrib.options_type == "MOptions":
                        attrs[attr] = [
                            x.strip() for x in value.split("|") if x.strip()
                        ]

                    if cfg_Attrib and cfg_Attrib.val_type.lower().startswith("date") and value:
                        attr_type = cfg_Attrib.val_type.lower()
                        # XX ?should datetime.date ever be used here? No timezone info.
                        conv_cls = datetime.datetime if attr_type == "datetime" else datetime.date
                        try:
                            attrs[attr] = conv_cls.fromtimestamp(int(attrs[attr]), tz=tzinfo).isoformat()
                        except Exception as e:
                            msg = (
                                f"In message {entry_id}, unable to convert attribute '{attr}' "
                                f"with value {attrs[attr]} to Type {attr_type}."
                            )
                            logger.warning(msg)  #  + "\n" + str(e)



                # Replies, attachments
                val = attrs.pop("Reply to", None)
                replies = [s.strip() for s in val.split(",")] if val else []

                in_reply_to = attrs.pop("In reply to", None)

                val = attrs.pop("Attachment", None)
                attachments = (
                    [s.strip() for s in val.split(",")] if val else []
                )

                locked_by = attrs.pop("Locked by", "")
                encoding = attrs.pop("Encoding", None) or "plain"

                # Get body text:
                text_lines = []
                more_entries = False
                for line in f:
                    if line.startswith(ENTRY_MARKER):
                        more_entries = True
                        break
                    text_lines.append(line)

                text = "".join(text_lines)
                entry = PSIEntry(
                    entry_id,
                    date,
                    attrs=attrs,
                    in_reply_to=in_reply_to,
                    replies=replies,
                    encoding=encoding,
                    attachments=attachments,
                    locked_by=locked_by,
                    text=text,
                )
                entries.append(entry)

        return entries


def migrate_logs(db, psi_logs: list[PSILogbook]):
    """Migrate PSI elog's through a database connection"""
    # Create db schema

    for psi_log in psi_logs:
        print(f"Migrating log '{psi_log.name}'")
        migrate_log(db, psi_log)


def migrate_log(db, lb: PSILogbook):
    """Migrate a PSI elog to the database"""
    db.add_lb_entries(lb.name, lb.entries())
