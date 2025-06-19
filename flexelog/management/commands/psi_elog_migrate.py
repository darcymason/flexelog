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
from flexelog.models import Logbook, Entry
from flexelog.psi_elog.psi_elogs import PSIEntry, PSILogbook
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


def convert_psi_entry(logbook, psi_entry):
    entry = Entry(
        lb=logbook,
        id=psi_entry.id,
        date=psi_entry.date,
        # XXX try to extract Author field, if given
        attrs=psi_entry.attrs,
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

def yes_no(prompt: str) -> bool:
    answer = ""
    while answer not in ("y", "n", "yes", "no"):
        answer = input(prompt)
    
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
            not_configd = ", ".join(lb_name for lb_name in lb_names if lb_name not in psi_cfg._cfg)
            if not_configd:
                raise CommandError(f"Logbook(s) {not_configd} not defined in config file '{elogd}'")
        
        # Find logbook folders:
        logbooks_dir = Path(
            psi_cfg.get("global", "Logbook dir", default=elogd.parent / "logbooks")
        )
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
            raise CommandError(
                f"Did not find logbook folders for logbook(s) {','.join(missing_logbooks)}"
            )
        flex_lb_names = [lb.name for lb in Logbook.objects.all()]
        existing_logbooks = [lb_name for lb_name in lb_names if lb_name in flex_lb_names]

        if existing_logbooks and not options["yes"]:
            prompt = (
                f"Flexelog already has {', '.join(existing_logbooks)} logbook(s) defined.\n"
                "Continue? (existing entries will be overwritten)  (yes/no)...:"
            )
            if not yes_no(prompt):
                return

        # XXX CREATE USERS
        #  XXX

        # Split elogd.cfg into global and per logbook config sections for flexelog

        # Migrate logbook entries
        original_config_texts = config_sections_texts(config_text)
        for lb_name in lb_names:
            self.stdout.write(f"Migrating PSI logbook '{lb_name}'", ending="...")
            
            # Create the logbook and its settings
            logbook, was_created = Logbook.objects.get_or_create(name=lb_name)
            logbook.config = original_config_texts[lb_name]
            if options["readonly"]:
                logbook.readonly = True

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
                if psi_entry.in_reply_to or len(batch) >= self.BATCH_SIZE:  
                    created = Entry.objects.bulk_create(batch)  # XX not possible if overwriting existing ones? need bulk_update?
                    if batch:
                        entry_ids = [e.id for e in created]
                        sys.stdout.write(
                            f"Entries {min(entry_ids)}-{max(entry_ids)} committed. "
                        )
                    batch = []

                batch.append(convert_psi_entry(logbook, psi_entry))
            
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