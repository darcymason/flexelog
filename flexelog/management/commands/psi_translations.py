from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from pathlib import Path
import polib
from html import unescape

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PSI_UTF8_LANG_PATH = BASE_DIR / "psi_elog" / "lang"
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
    "sk": "slovak",
    "tr": "turkish",
    "zh_CN": "chinese",
}


def eloglang_translations(lang_code) -> dict:
    """Return translation dict from a PSI elog's eloglang.<lang-code> file"""
    translations = {}
    if not PSI_UTF8_LANG_PATH.exists():
        raise IOError(f"Language file path '{PSI_UTF8_LANG_PATH}' does not exist")
    lang_name = LANGUAGES.get(lang_code)
    if not lang_name:
        return {}
    lang_file = PSI_UTF8_LANG_PATH / f"{lang_name}.eloglang"

    with open(lang_file, "r", encoding="utf8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(("#", ";")):
                continue
            split = [x.strip() for x in line.split("=")]
            val = None if len(split) == 1 else split[1]
            translations[unescape(split[0])] = unescape(val)

    return translations


class Command(BaseCommand):
    help = "Use PSI elogs eloglang.* files to translate messages"

    def add_arguments(self, parser):
        parser.add_argument("--overwrite",
            action="store_true",
            help="Overwrite any existing translations",
        )

    def handle(self, *args, **options):
        locale_paths = getattr(settings, "LOCALE_PATHS", [])
        # self.stdout.write(f"Starting translations from paths {locale_paths}")
        if not locale_paths:
            self.stdout.write(
                self.style.ERROR("No LOCALE_PATHS set in settings.py")
            )
            return
        
        overwriting = options["overwrite"]
        if overwriting:
            check = input("Confirm overwrite all existing translations with PSI translations where available (type yes): ")
            if check.lower() != "yes":
                overwriting = False
                self.stdout.write("Not overwriting")
        if overwriting:
            self.stdout.write("PSI translations (where available) will replace any existing ones")
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
                translations = eloglang_translations(lang_code)
                updated = False

                entries = po if overwriting else po.untranslated_entries()
                for entry in entries:
                    if translations.get(entry.msgid):  # don't update if missing or empty value
                        entry.msgstr = translations[entry.msgid]
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
        

