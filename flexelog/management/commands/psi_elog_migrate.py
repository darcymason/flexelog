from collections import defaultdict
import re
import shutil
import sys
from django.core.management.base import BaseCommand, CommandError
from flexelog.elog_cfg import LogbookConfig
from flexelog.models import Attachment, Logbook

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

from flexelog.script_util import yes_to

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


code_block_re = re.compile(r"(\[CODE\].*?\[/CODE\])", re.IGNORECASE | re.DOTALL)
tags_re = re.compile(r"(</?.*?>)", re.DOTALL)

# This unfortunately does not check if already a blank line before the dashes
# Could check using splitlines, but not really worth it
# TUI editor still underlines above text unless more than 3 leading spaces
dashline = re.compile(r"^( {,3}(?:--+|==+))$", re.MULTILINE)


def process(text: str, *, backticks: bool, dashlines: bool) -> str:
    """Make text more markdown friendly by backticking angle brackets and spacing title dashes"""
    if backticks:
        text = tags_re.sub(r"`\1`", text)
    if dashlines:
        text = dashline.sub(r"\n\1", text)
    return text


def convert_psi_entry(logbook, lb_attrs, psi_entry, backticks: bool, dashlines: bool):
    # try to convert date:
    def is_code_block(chunk):
        return chunk[:6].lower() == "[code]"

    try:
        date = datetime.datetime.fromisoformat(psi_entry.date)
    except:
        date = psi_entry.date  # str

    # Process text if requested, to improve its conversion to markdown
    text = psi_entry.text
    encoding = psi_entry.encoding.strip()
    if backticks or dashlines and text:
        if encoding.lower() == "elcode":
            text = "".join(
                (
                    chunk
                    if is_code_block(chunk)
                    else process(chunk, backticks=backticks, dashlines=dashlines)
                )
                for chunk in code_block_re.split(text)
            )
        elif encoding.lower() != "html":
            text = process(text, backticks=backticks, dashlines=dashlines)

    entry = Entry(
        lb=logbook,
        id=psi_entry.id,
        date=date,
        # XXX try to extract Author field, if given
        attrs=psi_entry.attrs,
        encoding=encoding,
        # locked_by  -- not used currently
        # in_reply_to handled below
        text=text,
    )
    if psi_entry.in_reply_to:
        try:
            entry.in_reply_to = logbook.entries.get(id=psi_entry.in_reply_to)
        except Entry.DoesNotExist:
            logger.warning(
                f"In message {entry.id}, 'in_reply_to' message id {psi_entry.in_reply_to} not found. Setting to None"
            )

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


def gen_entries(
    psi_entries: Generator[PSIEntry, None, None], logbook: Logbook
) -> Generator[Entry, None, None]:
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


def attachment_year(datestr: str) -> str:
    yy = "20" if int(datestr[:2]) < 90 else "19"
    return yy + datestr[:2]


def save_entry(entry, logbook, lb_dir, in_reply_to, attachment_names, file_op):
    if in_reply_to:
        try:
            entry.in_reply_to = logbook.entries.get(id=in_reply_to)
        except Entry.DoesNotExist:
            logger.warning(
                f"In message {entry.id}, 'in_reply_to' message id {in_reply_to} not found. Setting to None"
            )

    # add attachments:
    if attachment_names:
        entry.save()  # generate rowid for Attachment model
        # entry.attachments.set([Path(filename).name[14:] for filename in old_entry.attachments])
        for filename in attachment_names:
            base_filename = Path(filename).name[14:]
            old_filepath = lb_dir / attachment_year(filename) / filename
            if not old_filepath.exists():
                logger.error(
                    f"Entry {entry.lb.name}/{entry.id} attachment '{old_filepath}' not found. Removed from flexelog entry."
                )
            else:
                logger.info(
                    f"Creating attachment '{base_filename}' in logbook '{entry.lb.name}'"
                )
                att = Attachment(entry=entry, attachment_file=base_filename)
                migrate_attachment(
                    att,
                    entry.lb.slug_name,
                    old_filepath,
                    base_filename,
                    file_op=file_op,
                )
                att.save()
    entry.save()


def migrate_attachment(att, lb_name, old_filepath, new_base_name, file_op):
    """Convert old elog attachments into flexelog format

    operation can be "link" (hard link, default), "copy" or "move". Link can only
    be used if the new location is on the same drive as the original.

    Hard links make a pointer to the original file, but are still available even
    if original file is deleted.

    """
    old_filepath = Path(old_filepath)
    att.save()
    att.attachment_file.name = (
        f"attachments/{lb_name}"
        f"/{attachment_year(old_filepath.name)}"
        f"/{att.pk:06d}__{new_base_name}"
    )

    Path(att.attachment_file.path).parent.mkdir(parents=True, exist_ok=True)
    if file_op == "link":
        Path(att.attachment_file.path).hardlink_to(old_filepath)
    else:
        copy_or_move = shutil.copy2 if file_op == "copy" else shutil.move
        copy_or_move(old_filepath, att.attachment_file.path)


class Command(BaseCommand):
    BATCH_SIZE = 100
    help = "Migrate a file-based PSI elog to Flexelog"

    def add_arguments(self, parser):
        parser.add_argument(
            "elogd_path",
            type=pathlib.Path,
            help="Path to the elogd.cfg file for the PSI elog",
        )
        parser.add_argument("-l", "--logbooks", nargs="*", type=str)
        parser.add_argument(
            "-y",
            "--yes",
            action=argparse.BooleanOptionalAction,
            help="Confirm yes to all override questions",
        )
        parser.add_argument(
            "-r",
            "--readonly",
            action=argparse.BooleanOptionalAction,
            help="Make all migrated logbooks read-only.  Useful if just trying flexelog and still adding/deleting entries in PSI logbooks",
        )
        parser.add_argument(
            "-B",
            "--no-backticks",
            action="store_false",
            dest="backticks",
            help="Don't put backticks around HTML-like tags.  Only applies for ELCode or plain text.",
            default=True,
        )
        parser.add_argument(
            "-D",
            "--no-dashline-sep",
            action="store_false",
            dest="dashline-sep",
            help="Don't put an extra line before '--...' or '==...' lines (done by default so markdown doesn't see the above line as a title)",
            default=True,
        )
        parser.add_argument(
            "-a",
            "--attachment-op",
            choices=["link", "copy", "move"],
            default="link",
            help="What to do for transferring attachment files to FlexElog (default hard link)",
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
                lb_name
                for lb_name in psi_cfg._cfg
                if not lb_name.lower().startswith(("global ", "group "))
                and lb_name.lower() != "global"
            ]
        else:
            lb_names = options["logbooks"]
            not_configd = ", ".join(
                f"'{lb_name}'" for lb_name in lb_names if lb_name not in psi_cfg._cfg
            )
            if not_configd:
                raise CommandError(
                    f"Logbook(s) {not_configd} not defined in config file '{elogd}'"
                )

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
                psi_logbooks[lb_name] = PSILogbook(
                    lb_name, lb_dir, psi_cfg._lb_attrs[lb_name]
                )
            except OSError:
                missing_logbooks.append(lb_name)
        if missing_logbooks:
            msg = f"Did not find logbook folders for logbook(s): {','.join(missing_logbooks)}"
            print(msg)
            if not (
                options["yes"]
                or yes_to("Ignore these logbooks and continue?  (yes/no)...:", default="yes")
            ):
                return
        flex_lb_names = [lb.name for lb in Logbook.objects.all()]
        existing_logbooks = [
            lb_name for lb_name in lb_names if lb_name in flex_lb_names
        ]

        if existing_logbooks and not options["yes"]:
            prompt = (
                f"Flexelog already has {', '.join(existing_logbooks)} logbook(s) defined.\n"
                "Continue? (existing entries will be overwritten)  (yes/no)...:"
            )
            if not yes_to(prompt, default="no"):
                return

        # CREATE GLOBAL CONFIG
        # Note: for now just copying previous text (including comments etc.)
        #   even if flexelog might not handle all the same config
        #  XX should at least delete irrelevant things related to server config etc.
        original_config_texts = config_sections_texts(config_text)
        if None in original_config_texts:
            logger.warning(
                "Config file {elogd.name} has lines outside of a section heading, which are ignored"
            )

        global_cfg, _ = ElogConfig.objects.get_or_create(name="global")
        global_cfg.config_text = original_config_texts["global"]
        global_cfg.save()
        logger.info("Copied [global] config to flexelog ElogConfig database entry")

        # CREATE USERS
        #  XXX for now only accept one password file.
        global_pwd_file = psi_cfg.get("global", "Password file")
        lb_pwd_files = set(
            pwd_file
            for lb_name in lb_names
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
            logbook, _ = Logbook.objects.get_or_create(name=lb_name)
            logbook.config = original_config_texts[lb_name]
            if options["readonly"]:
                logbook.readonly = True
            if psi_cfg.get(logbook, "Hidden"):
                logbook.is_unlisted = True
            # Check for auth needed - note these will also find [global] entries if specified there
            if psi_cfg.get(lb_name, "Password file") or psi_cfg.get(
                lb_name, "Authentication"
            ):
                logbook.auth_required = True
            else:
                logbook.auth_required = False

            logbook.save()  # post_save event will create standard Groups if auth_required

            if logbook.entries.count():
                if not options["yes"]:
                    prompt = f"Logbook '{lb_name}' has existing entries.  Delete them?  (yes/no)..."
                    if not yes_to(prompt, default="yes"):
                        return  # XX Could try to update entries that exist ...
                logbook.entries.all().delete()

            # Start porting entries, bulk create where possible for speed
            # If have a reply_to or attachment have to commit so foreign key exists
            batch = []
            for psi_entry in psi_logbooks[lb_name].entries():
                # if a reply, commit what we have to make sure referenced entry exists first
                # XX is this guaranteed? psi_entries came by original date order, so I think is safe
                if (
                    psi_entry.in_reply_to
                    or psi_entry.attachments
                    or len(batch) >= self.BATCH_SIZE
                ):
                    # XX not possible if overwriting existing ones? need bulk_update?
                    created = Entry.objects.bulk_create(batch)  
                    if batch:
                        entry_ids = [e.id for e in created]
                        sys.stdout.write(
                            f"Entries {min(entry_ids)}-{max(entry_ids)} committed. "
                        )
                    batch = []
                # Above made the already batch entries, not the current one
                if psi_entry.in_reply_to or psi_entry.attachments:
                    save_entry(
                        psi_entry,
                        logbook,
                        lb_dir,
                        psi_entry.in_reply_to,
                        psi_entry.attachments,
                        file_op=options["attachment-op"]
                    )
                    sys.stdout.write(f"Entry {entry.id} committed. ")
                else:
                    batch.append(
                        convert_psi_entry(
                            logbook,
                            psi_cfg.lb_attrs[lb_name],
                            psi_entry,
                            backticks=options["backticks"],
                            dashlines=options["dashlines-sep"],
                        )
                    )

            if batch:
                # XX not possible if overwriting existing ones? need bulk_update?
                created = Entry.objects.bulk_create(batch)
                entry_ids = [e.id for e in created]
                sys.stdout.write(
                    f"Entries {min(entry_ids)}-{max(entry_ids)} committed."
                )

            self.stdout.write(self.style.SUCCESS("OK"))

        self.stdout.write(
            self.style.SUCCESS("Successfully migrated PSI logbooks")  # XX specify
        )
