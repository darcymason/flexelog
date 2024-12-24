from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from pathlib import Path
import polib

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PSI_LANG_PATH = BASE_DIR / "psi_elog" / "lang"
PO_FILENAME = "django.po"
LANGUAGES = {
    "bg": "bulgarian",
    "br": "brazilian",
    "cz": "czech",
    "de": "german",
    "dk": "danish",
    "es": "spanish",
    "fr": "french",
    "id": "indonesia",
    "it": "italian",
    "jp": "japanese",
    "nl": "dutch",
    "pl": "polish",
    "ru": "russian",
    "se": "swedish",
    "sk": "slowak",
    "tr": "turkish",
    "zh": "chinese",
}


def eloglang_translations(lang_code) -> dict:
    """Return translation dict from a PSI elog's eloglang.<lang-code> file"""
    translations = {}
    if not PSI_LANG_PATH.exists():
        raise IOError(f"Language file path '{PSI_LANG_PATH}' does not exist")
    lang_name = LANGUAGES.get(lang_code)
    matches = list(PSI_LANG_PATH.glob(f"eloglang.{lang_name}*"))
    if not matches:
        return {}
    # Prefer utf8 translation file if available
    for lang_file in matches:
        if "UTF8" in lang_file.suffix.upper():
            break
    else:
        lang_file = matches[0]

    # Check if chosen file has an encoding in the suffix.
    # e.g. "eloglang.zh_CN-UTF8", "eloglang.ru_CP1251"
    if "_" in lang_file.suffix:
        encoding = lang_file.suffix.split("_")[1].replace("CN-", "")
    else:
        encoding = "latin1"

    with open(lang_file, "r", encoding=encoding) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(("#", ";")):
                continue
            split = [x.strip() for x in line.split("=")]
            val = None if len(split) == 1 else split[1]
            translations[split[0]] = val

    return translations


class Command(BaseCommand):
    help = "Use PSI elogs eloglang.* files to translate messages"

    def add_arguments(self, parser):
        pass
        # parser.add_argument("-l", nargs="*", type=str) # specific languages

    def handle(self, *args, **options):
        locale_paths = getattr(settings, "LOCALE_PATHS", [])
        # self.stdout.write(f"Starting translations from paths {locale_paths}")
        if not locale_paths:
            self.stdout.write(
                self.style.ERROR("No LOCALE_PATHS set in settings.py")
            )
            return
        self.stdout.write("Going through locale_paths")
        any_updated = False
        for locale_path in locale_paths:
            self.stdout.write(f"Starting translations from path {locale_path}")
            for lang_code_path in Path(locale_path).iterdir():
                lang_code = lang_code_path.name
                if not lang_code_path.is_dir() or lang_code not in LANGUAGES:
                    self.stdout.write(f"Folder '{lang_code}' is not a known language code")
                    continue
                po_filepath = Path(locale_path) / lang_code / "LC_MESSAGES" / PO_FILENAME
                po = polib.pofile(po_filepath)
                translation = eloglang_translations(lang_code)
                updated = False
                for entry in po.untranslated_entries():
                    if translation.get(entry.msgid):  # don't update if missing or empty value
                        entry.msgstr = translation[entry.msgid]
                        updated = True
                        self.stdout.write(
                            self.style.SUCCESS(f"{lang_code}: {entry.msgid}  -->  {entry.msgstr}")
                        )
                if updated:
                    po.save(po_filepath)
                    self.stdout.write(
                        self.style.SUCCESS(f"Saved updated .po file '{po_filepath}'")
                    )
                    any_updated = True
                else:
                    self.stdout.write(f"No new translations for '{lang_code}'")
                    
        if any_updated:
            self.stdout.write(
                self.style.SUCCESS(f"\n\n ** Please run `python manage.py compilemessages` to make translations available")
            )
        

