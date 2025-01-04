"""Convert PSI elog's eloglang.<language> files to UTF8 and rename"""
# This is a 'one-time' operation unless PSI elog updates its translations
# Most files are 'latin1' encoding. Exceptions are listed in `known_encoding`

from pathlib import Path
from textwrap import dedent
from datetime import date

SOURCE_DIR = Path(r"c:\temp\elog-latest")
DEST_DIR = Path(__file__).resolve().parent / "lang"

NEW_HEADER = (
    "# Language file converted from file '{psi_name}'\n"
    "# from PSI elog (https://elog.psi.ch/elog/) on {date}\n"
    "# by script eloglang_to_utf.py\n"
)


known_encoding = {
    ".bulgarian": "CP1251",
    ".czech": "UTF8",
    ".japanese": "shift-JIS",
    ".polish": "UTF8",
    ".slovak": "UTF8",
    ".ru_CP1251": "CP1251",
    ".german_UTF8": "UTF8",
    ".zh_CN-UTF8": "UTF8", 
}

corrected_name = {
    ".ru_CP1251": "russian",
    ".german_UTF8": "german",
    ".zh_CN-UTF8": "chinese", 
}

if __name__ == "__main__":
    if not DEST_DIR.exists():
        DEST_DIR.mkdir(parents=True)
    for path in SOURCE_DIR.glob("eloglang.*"):
        encoding = "latin1"
        if path.suffix in known_encoding:
            encoding = known_encoding[path.suffix]
            print(f"{path.name} using `{encoding}`...", end="")
        name = corrected_name.get(path.suffix, path.suffix[1:])
        out_path = (DEST_DIR / name).with_suffix(".eloglang")
        
        print(f"Writing {str(out_path)} in utf8")
        with open(path, "r", encoding=encoding) as f_in, open(out_path, "w", encoding="utf8") as f_out:
            contents = f_in.read()
            # Replace comments header
            lines = contents.splitlines()
            for i in range(len(lines)):
                if lines[i] and lines[i][0] != "#":
                    break
            comments = NEW_HEADER.format(psi_name=path.name, date=date.today()) + "\n"
            f_out.write(comments + "\n".join(lines[i:]))
