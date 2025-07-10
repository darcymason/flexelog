from collections import defaultdict
import re
import sys
from django.core.management.base import BaseCommand, CommandError
from flexelog.elog_cfg import LogbookConfig
from flexelog.models import Logbook

from itertools import batched, count
import pathlib
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from pathlib import Path
import argparse

import json
from typing import Generator
from flexelog.models import Attachment, Entry, ElogConfig, Logbook, User
import datetime

from oldflexelog.attachments import attachment_year
from oldflexelog.entries import Entry as OldFlexelogEntry
from oldflexelog.db.sqlite import DatabaseBackend
from flexelog.psi_elog.psi_elogs import parse_pwd_file

import shutil

import logging
logger = logging.getLogger("flexelog")
logger.setLevel(logging.DEBUG)

OLD_PATH = Path(r"g:\my drive\elog")
OLD_ELOGD = OLD_PATH / "elogd.cfg"


old_db = DatabaseBackend(OLD_PATH / "oldflexelog.db")


def config_sections_texts(config_text):
    section = None
    section_lines = defaultdict(list)
    for line in config_text.splitlines():
        if m := re.match(r"\[(.*?)\]", line.strip()):
            section = m.groups()[0]
        else:
            section_lines[section].append(line)
    
    # Concatenate lines together
    return {section: "\n".join(lines) for section, lines in section_lines.items()}


def _ensure_aware(dt: datetime.datetime):
    return timezone.make_aware(dt) if (dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None) else dt

def convert_old_entry(logbook, lb_dir, lb_attrs, old_entry):
    # lb_attrs there to possibly convert other dates, booleans, etc
    attrs = dict(old_entry.attrs.items())
    # # try to convert date:
    # try:
    #     date = datetime.datetime.fromisoformat(old_entry.date)
    # except:
    #     logger.error(f"Unable to convert the date '{old_entry.date}' for old flexelog entry {old_entry.id}")
    #     date = old_entry.date  # str
    # else:
    #     date = _ensure_aware(date)

    logger.debug(f"Converting {logbook.name}/{old_entry.id}")
    entry = Entry(
        lb=logbook,
        id=old_entry.id,
        date=_ensure_aware(old_entry.date),
        # XXX try to extract Author field, if given
        attrs=attrs,
        encoding=old_entry.encoding,
        # locked_by  -- not used currently
        # in_reply_to handled below
        text=old_entry.text,
    )
    if old_entry.reply_to:
        try:
            entry.in_reply_to = logbook.entries.get(id=old_entry.reply_to)
        except Entry.DoesNotExist:
            logger.warning(f"In message {entry.id}, 'in_reply_to' message id {old_entry.reply_to} not found. Setting to None")
    
    # add attachments:
    if old_entry.attachments:
        entry.save()  # generate rowid for Attachment model
        # entry.attachments.set([Path(filename).name[14:] for filename in old_entry.attachments])
        for filename in old_entry.attachments:
            base_filename = Path(filename).name[14:]
            old_filepath = lb_dir / attachment_year(filename) / filename
            if not old_filepath.exists():
                logger.error(f"Entry {entry.lb.name}/{entry.id} attachment '{old_filepath}' not found. Removed from flexelog entry.")
            else:
                logger.info(f"Creating attachment '{base_filename}' in logbook '{entry.lb.name}'")
                att = Attachment(entry=entry, attachment_file=base_filename)
                att.save()  # just to get an id to incorp in filename
                migrate_attachment(att, entry.lb.slug_name, old_filepath, base_filename, copy=True)  # can choose to move instead
                att.save()
    entry.save()


def create_users(users: list[dict[str, str]]):
    for old_user in users:
        user, was_created = User.objects.get_or_create(username=old_user["name"])
        first, last = old_user.get("full_name", "").split(" ", maxsplit=1)
        user.first_name = first
        user.last_name = last
        user.email = old_user.get("email", "")
        if bool(old_user.get("inactive")):
            user.is_active = False
        user.save()
        action = "Created" if was_created else "Updated"
        logger.info(
            f"{action} user '{user.get_username()}' "
            f"('{user.get_full_name()}', {user.email})"
        )

def migrate_attachment(att, lb_name, old_filepath, new_base_name, copy=True):
    """Convert old elog attachments into flexelog format"""
    old_filepath = Path(old_filepath)
    att.save()
    att.attachment_file.name = (
        f"attachments/{lb_name}"
        f"/{attachment_year(old_filepath.name)}"
        f"/{att.pk:06d}__{new_base_name}"
    )
    copy_or_move = shutil.copy if copy else shutil.move

    Path(att.attachment_file.path).parent.mkdir(parents=True, exist_ok=True)
    copy_or_move(old_filepath, att.attachment_file.path)


def yes_no(prompt: str) -> bool:
    answer = ""
    while answer not in ("y", "n", "yes", "no"):
        answer = input(prompt).lower()
    
    return answer.startswith("y")


class Command(BaseCommand):
    BATCH_SIZE = 100
    help = "Flexelog author use only -- Migrate an old-Flexelog elog to Flexelog"

    def add_arguments(self, parser):
        # parser.add_argument("elogd_path", type=pathlib.Path, help="Path to the elogd.cfg file for the old-Flexelog elog")
        parser.add_argument("-l", "--logbooks", nargs="*", type=str)
        parser.add_argument("-y", "--yes", action=argparse.BooleanOptionalAction, help="Confirm yes to any override questions")
        parser.add_argument(
            '-r', "--readonly", 
            action=argparse.BooleanOptionalAction,
            default=False,
            help="Make all migrated logbooks read-only.  Useful if just trying flexelog and still adding/deleting entries in old logbooks"
        )
        
    def handle(self, *args, **options):
        # XXX Note need to check for "Top Groups" and require one of them to be specified at a time

        try:
            config_text = open(OLD_ELOGD, "r").read()
            old_cfg = LogbookConfig(config_text)
        except Exception as e:
            raise CommandError(f"Unable to parse config file '{OLD_ELOGD}'\n" + str(e))
        
        if not options["logbooks"]:
            lb_names = [
                lb_name for lb_name in old_cfg._cfg
                if not lb_name.lower().startswith(("global ", "group "))
                and lb_name.lower() != "global"
            ]
        else:
            lb_names = options["logbooks"]
            not_configd = ", ".join(f"'{lb_name}'" for lb_name in lb_names if lb_name not in old_cfg._cfg)
            if not_configd:
                raise CommandError(f"Logbook(s) {not_configd} not defined in config file '{OLD_ELOGD}'")
        
        # Find logbook folders:
        logbooks_dir = old_cfg.get("global", "Logbook dir")
        if logbooks_dir is None:
            logbooks_dir = OLD_ELOGD.parent / "logbooks"
        else:
            logbooks_dir = Path(logbooks_dir)
            if not logbooks_dir.is_absolute():
                logbooks_dir = OLD_ELOGD.parent / logbooks_dir
        
        if not logbooks_dir.exists():
            raise CommandError(f"Logbook dir '{logbooks_dir}' does not exist")
        
        flex_lb_names = [lb.name for lb in Logbook.objects.all()]
        existing_logbooks = [lb_name for lb_name in lb_names if lb_name in flex_lb_names]

        if existing_logbooks and not options["yes"]:
            prompt = (
                f"Flexelog already has {', '.join(existing_logbooks)} logbook(s) defined.\n"
                "Continue? (existing entries will be overwritten)  (yes/no)...:"
            )
            if not yes_no(prompt):
                return

        # CREATE GLOBAL CONFIG
        # Note: for now just copying previous text (including comments etc.)
        #   even if flexelog might not handle all the same config
        #  XX should at least delete irrelevant things related to server config etc.
        original_config_texts = config_sections_texts(config_text)
        if None in original_config_texts:
            logger.warning("Config file {OLD_ELOGD.name} has lines outside of a section heading, which are ignored")
        
        global_cfg, _ = ElogConfig.objects.get_or_create(name="global")
        global_cfg.config_text = original_config_texts["global"]
        global_cfg.save()
        logger.info("Copied [global] config to flexelog ElogConfig database entry")

        # CREATE USERS
        #  XXX for now only accept one password file.
        global_pwd_file = old_cfg.get("global", "Password file")
        lb_pwd_files = set(
            pwd_file for lb_name in lb_names
            if (pwd_file := old_cfg.get(lb_name, "Password file"))
        )
        if global_pwd_file:
            if any(lb_pwd_file != global_pwd_file for lb_pwd_file in lb_pwd_files):
                logger.warning(
                    "Only the elog global password file will be used for creating users. "
                    "Please create others as needed in flexelog admin webpages."
                )
            pwd_file = global_pwd_file
        elif lb_pwd_files:
            # Just do one arbitrary file -- later can do more but avoiding 
            # collisions issue for now.
            pwd_file = lb_pwd_files.pop()  # pick one, probably only 1 or a few anyway
            logger.warning(
                f"Can currently only migrate users from one password file. Using '{pwd_file}'. "
                "Please create other users as needed in flexelog admin webpages."
            )            
        else:
            pwd_file = None

        
        if pwd_file: 
            pwd_file = logbooks_dir / pwd_file
            if not pwd_file.exists():
                logger.error(
                    f"Password file '{pwd_file}' not found. "
                    "Please set up users manually in flexelog admin webpages."
                )
                pwd_file = None

        if pwd_file:
            users = parse_pwd_file(pwd_file)
            create_users(users)
        # XXX CREATE LOGBOOK GROUPS

        # Migrate logbook entries
        for lb_name in lb_names:
            self.stdout.write(f"Migrating Old Flexelog logbook '{lb_name}'...")
            
            # Create the logbook and its settings
            logbook, was_created = Logbook.objects.get_or_create(name=lb_name)
            logbook.config = original_config_texts[lb_name]
            if options["readonly"]:
                logbook.readonly = True
            if old_cfg.get(logbook, "Hidden"):
                logbook.is_unlisted = True
            # Check for auth needed - note these will also find [global] entries if specified there
            if old_cfg.get(lb_name, "Password file") or old_cfg.get(lb_name, "Authentication"):
                logbook.auth_required = True
            else:
                logbook.auth_required = False
            
            logbook.save()  # post_save event will create standard Groups if auth_required

            subdir = Path(old_cfg.get(lb_name, "Subdir", default=lb_name))
            lb_dir = (
                subdir if subdir.is_absolute() else logbooks_dir / lb_name
            )
            if logbook.entries.count():
                if not options["yes"]:
                    prompt = f"Logbook '{lb_name}' has existing entries.  Delete them?  (yes/no)..."
                    if not yes_no(prompt):
                        return  # XX Could try to update entries that exist ...
                logbook.entries.all().delete()
            
            _, _, old_db_entries = old_db.get_entries(lb_name)
            for old_entry in old_db_entries:
                convert_old_entry(logbook, lb_dir, old_cfg.lb_attrs[lb_name], old_entry)

            self.stdout.write(self.style.SUCCESS("OK"))

        self.stdout.write(
            self.style.SUCCESS("Successfully migrated Old Flexelog logbooks")  # XX specify
        )