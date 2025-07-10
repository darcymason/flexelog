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
from flexelog.models import Logbook, Entry, ElogConfig, User
from flexelog.psi_elog.psi_elogs import PSIEntry, PSILogbook, parse_pwd_file
import datetime

import logging
logger = logging.getLogger("flexelog")

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


def convert_psi_entry(logbook, lb_attrs, psi_entry):
    attrs = {k.lower(): v for k,v in psi_entry.attrs.items()}
    # try to convert date:
    try:
        date = datetime.datetime.fromisoformat(psi_entry.date)
    except:
        date = psi_entry.date  # str
    entry = Entry(
        lb=logbook,
        id=psi_entry.id,
        date=date,
        # XXX try to extract Author field, if given
        attrs={k.lower(): v for k,v in attrs.items()}, # store keys lower case for searching etc.
        encoding=psi_entry.encoding,
        # locked_by  -- not used currently
        # in_reply_to handled below
        text=psi_entry.text,
    )
    if psi_entry.in_reply_to:
        try:
            entry.in_reply_to = logbook.entries.get(id=psi_entry.in_reply_to)
        except Entry.DoesNotExist:
            logger.warning(f"In message {entry.id}, 'in_reply_to' message id {psi_entry.in_reply_to} not found. Setting to None")
    
    return entry

def create_users(users: list[dict[str, str]]):
    for psi_user in users:
        user, was_created = User.objects.get_or_create(username=psi_user["name"])
        first, last = psi_user.get("full_name", "").split(" ", maxsplit=1)
        user.first_name = first
        user.last_name = last
        user.email = psi_user.get("email", "")
        if bool(psi_user.get("inactive")):
            user.is_active = False
        user.save()
        action = "Created" if was_created else "Updated"
        logger.info(
            f"{action} user '{user.get_username()}' "
            f"('{user.get_full_name()}', {user.email})"
        )
    

def yes_no(prompt: str) -> bool:
    answer = ""
    while answer not in ("y", "n", "yes", "no"):
        answer = input(prompt).lower()
    
    return answer.startswith("y")
    

def gen_entries(psi_entries: Generator[PSIEntry, None, None], logbook: Logbook) -> Generator[Entry, None, None]:
    for psi_entry in psi_entries:
        in_reply_to = None
        if psi_entry.in_reply_to:
            try:
                parent_entry = Entry.objects.get(lb=logbook, id=psi_entry.in_reply_to)
            except:
                logger.error(
                    f"In message {psi_entry.id}, 'in_reply_to' message id {psi_entry.in_reply_to} not found. "
                    "Setting in_reply_to to None in flexelog"
                )
            else:
                in_reply_to = parent_entry

        yield Entry(
            id=psi_entry.id,
            lb=logbook,
            date=psi_entry.date,
            attrs=psi_entry.attrs,
            in_reply_to=in_reply_to,
            text=psi_entry.text,
        )


class Command(BaseCommand):
    BATCH_SIZE = 100
    help = "Migrate a file-based PSI elog to Flexelog"

    def add_arguments(self, parser):
        parser.add_argument("elogd_path", type=pathlib.Path, help="Path to the elogd.cfg file for the PSI elog")
        parser.add_argument("-l", "--logbooks", nargs="*", type=str)
        parser.add_argument("-y", "--yes", action=argparse.BooleanOptionalAction, help="Confirm yes to any override questions")
        parser.add_argument(
            '-r', "--readonly", 
            action=argparse.BooleanOptionalAction,
            help="Make all migrated logbooks read-only.  Useful if just trying flexelog and still adding/deleting entries in PSI logbooks"
        )
        
    def handle(self, *args, **options):
        # XXX Note need to check for "Top Groups" and require one of them to be specified at a time
        elogd = options["elogd_path"]
        if elogd.is_dir():
            elogd = elogd / "elogd.cfg"

        if not elogd.exists():
            raise CommandError(f"elogd.cfg file '{elogd}' not found")

        try:
            config_text = open(elogd, "r").read()
            psi_cfg = LogbookConfig(config_text)
        except Exception as e:
            raise CommandError(f"Unable to parse config file '{elogd}'\n" + str(e))
        
        if not options["logbooks"]:
            lb_names = [
                lb_name for lb_name in psi_cfg._cfg
                if not lb_name.lower().startswith(("global ", "group "))
                and lb_name.lower() != "global"
            ]
        else:
            lb_names = options["logbooks"]
            not_configd = ", ".join(f"'{lb_name}'" for lb_name in lb_names if lb_name not in psi_cfg._cfg)
            if not_configd:
                raise CommandError(f"Logbook(s) {not_configd} not defined in config file '{elogd}'")
        
        # Find logbook folders:
        logbooks_dir = psi_cfg.get("global", "Logbook dir")
        if logbooks_dir is None:
            logbooks_dir = elogd.parent / "logbooks"
        else:
            logbooks_dir = Path(logbooks_dir)
            if not logbooks_dir.is_absolute():
                logbooks_dir = elogd.parent / logbooks_dir
        
        if not logbooks_dir.exists():
            raise CommandError(f"Logbook dir '{logbooks_dir}' does not exist")
        
        psi_logbooks = {}
        missing_logbooks = []
        for lb_name in lb_names:
            subdir = Path(psi_cfg.get(lb_name, "Subdir", default=lb_name))
            lb_dir = subdir if subdir.is_absolute() else logbooks_dir / lb_name
            try:
                psi_logbooks[lb_name] = PSILogbook(lb_name, lb_dir, psi_cfg._lb_attrs[lb_name])
            except OSError:
                missing_logbooks.append(lb_name)
        if missing_logbooks:
            msg = f"Did not find logbook folders for logbook(s): {','.join(missing_logbooks)}"
            sys.stdout.write(msg)
            if not (options["yes"] or yes_no("Ignore these logbooks and continue?  (yes/no)...:")):
                return
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
            logger.warning("Config file {elogd.name} has lines outside of a section heading, which are ignored")
        
        global_cfg, _ = ElogConfig.objects.get_or_create(name="global")
        global_cfg.config_text = original_config_texts["global"]
        global_cfg.save()
        logger.info("Copied [global] config to flexelog ElogConfig database entry")

        # CREATE USERS
        #  XXX for now only accept one password file.
        global_pwd_file = psi_cfg.get("global", "Password file")
        lb_pwd_files = set(
            pwd_file for lb_name in lb_names
            if (pwd_file := psi_cfg.get(lb_name, "Password file"))
        )

        if global_pwd_file:
            if any(lb_pwd_file != global_pwd_file for lb_pwd_file in lb_pwd_files):
                logger.warning(
                    "Only the PSI elog global password file will be used for creating users. "
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
            self.stdout.write(f"Migrating PSI logbook '{lb_name}'", ending="...")
            
            # Create the logbook and its settings
            logbook, was_created = Logbook.objects.get_or_create(name=lb_name)
            logbook.config = original_config_texts[lb_name]
            if options["readonly"]:
                logbook.readonly = True
            if psi_cfg.get(logbook, "Hidden"):
                logbook.is_unlisted = True
            # Check for auth needed - note these will also find [global] entries if specified there
            if psi_cfg.get(lb_name, "Password file") or psi_cfg.get(lb_name, "Authentication"):
                logbook.auth_required = True
            
            logbook.save()  # post_save event will create standard Groups if auth_required

            if logbook.entries.count():
                if not options["yes"]:
                    prompt = f"Logbook '{lb_name}' has existing entries.  Delete them?  (yes/no)..."
                    if not yes_no(prompt):
                        return  # XX Could try to update entries that exist ...
                logbook.entries.all().delete()
            
            # Start porting entries, bulk create where possible for speed
            # If have a reply_to, could be in the batch not committed, so commit if needed
            batch = []
            for psi_entry in psi_logbooks[lb_name].entries():
                # if a reply, commit what we have to make sure referenced entry exists first
                # XX is this guaranteed? psi_entries came by original date order, so I think is safe
                if psi_entry.in_reply_to or psi_entry.attachments or len(batch) >= self.BATCH_SIZE:  
                    created = Entry.objects.bulk_create(batch)  # XX not possible if overwriting existing ones? need bulk_update?
                    if batch:
                        entry_ids = [e.id for e in created]
                        sys.stdout.write(
                            f"Entries {min(entry_ids)}-{max(entry_ids)} committed. "
                        )
                    batch = []
                if psi_entry.in_reply_to or psi_entry.attachments:
                    save_entry(psi_entry, logbook, lb_dir, in_reply_to, attachment_names)
                    sys.stdout.write(f"Entry {entry.id} committed. ")
                else:
                    batch.append(convert_psi_entry(logbook, psi_cfg.lb_attrs[lb_name], psi_entry))
            
            if batch:
                created = Entry.objects.bulk_create(batch)  # XX not possible if overwriting existing ones? need bulk_update?
                entry_ids = [e.id for e in created]
                sys.stdout.write(
                    f"Entries {min(entry_ids)}-{max(entry_ids)} committed."
                )

            # XXX do the work
            self.stdout.write(self.style.SUCCESS("OK"))
            # ... raise CommandError('XXX')


        self.stdout.write(
            self.style.SUCCESS("Successfully migrated PSI logbooks")  # XX specify
        )