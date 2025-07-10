

from pathlib import Path

from flexelog.elog_cfg import IMAGE_SUFFIXES


def is_image(filename: str | Path):
    return Path(filename).suffix.lower() in IMAGE_SUFFIXES

def is_ascii(filename: str | Path):
    return not is_binary(str(filename))