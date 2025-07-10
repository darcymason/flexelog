import sys
from pathlib import Path
from django.core.management.utils import get_random_secret_key
import tzlocal

usage = """
Flexelog setup:

Run this once for each server, to produce a `settings_local.py` file
which sets some Django settings for your particular flexelog site.

You can edit the file afterwards, but this gives a start by:
* creating a SECRET_KEY using django's `get_random_secret_key`
* asking for a base directory and 'Top Group' name (more below), 
  and then creating (or using, if it exists)
  a directory structure like:
  path/to/flexelog/data
      top-group1-name
          top-group-name.db  (assuming sqlite)
          "media" folder (where attachments will go)
      [...]   
* asking for your server's time zone

If not using sqlite, then you will need to edit the DATABASES 
section of `settings_local.py` yourself after this script.

The `Top group` can be blank unless you are using multiple independent 
Django flexelog servers (necessary if migrating PSI elog Top Groups).
Leave blank to just start experimenting with flexelog.
"""

HERE = Path(__file__).resolve().parent
TEMPLATE_PATH = HERE / "flexsite" / "settings_local_template.txt"
SETTINGS_LOCAL_PATH = HERE / "flexsite" / "settings_local.py"

def validate_yes_no(answer):
    answers = ("y", "n", "yes", "no")
    if answer.lower() in answers:
        return ""
    return f"Answer must be one of {answers}"

def validate_dir(answer):
    path = Path(answer)
    if path.exists():
        return "" if path.is_dir() else "Path is an existing file.  Please enter a directory name."

    return ""

def get_input(msg, validator=None, default=None):
    """Ask for user input. If default provided, return that if empty input given
    
    `validate` is a callback which takes a str and returns a message
    (if a problem) or empty string if successful. 
    """

    prompt = msg
    if default is not None:
        prompt += f" [{str(default) or '<blank>'}] "
    prompt += ": "

    while True:
        answer = input(prompt).strip()
        if answer:
            if validator is None or not (error := validator(answer)):
                break
            print(error)
            continue
        
        # empty answer
        if default is not None:
            answer = default
            break

    return answer


def main():
    print(usage)
    print()

    if SETTINGS_LOCAL_PATH.exists():
        confirm = get_input(
            f"File '{SETTINGS_LOCAL_PATH}' exists."
            "Do you want to overwrite it?",
            validator=validate_yes_no,
            default="no",
        )
        if confirm.lower().startswith("n"):
            sys.exit(-1)

    context = {"SECRET_KEY": get_random_secret_key()}
    print("Secret key created.\n")

    # Base directory ----------------------------
    context["ELOG_DIR"] = elog_dir = get_input(
        "Directory for elog database/attachments",
        default = Path.home() / "flexelog",
        validator=validate_dir,
    )
    # Create dir, if necessary, under top group folder below
    
    # Top Group ----------------------------------
    print(
        "'Top Group': if only using a single Flexelog server, leave blank. "
        "If migrating from PSI elog, and have Top Groups there, enter one name here."
    )
    context["TOP_GROUP_NAME"] = get_input("Top group name", default="")
    tg_path = Path(elog_dir) / context["TOP_GROUP_NAME"]

    if not tg_path.exists():
        yn = get_input(
            f"Path '{tg_path}' does not exist. Do you wish to create it?",
            default="yes",
            validator=validate_yes_no,
        )
        if yn.lower().startswith("y"):
            Path(tg_path).mkdir(parents=True)


    # Database ------------------------------------
    context["DATABASE_NAME"] = get_input(
        "Database name",
        default=f"{context['TOP_GROUP_NAME'] or 'flexelog'}.db"
    )
    # python manage.py migrate will create the database file

    context["TIME_ZONE"] = get_input(
        "Enter the server timezone in IANA format",
        default = tzlocal.get_localzone_name(),
    )    

    # Create the settings_local.py file:
    template = open(TEMPLATE_PATH, 'r').read()
    print(f"Writing '{SETTINGS_LOCAL_PATH}'")

    with open(SETTINGS_LOCAL_PATH, 'w') as f:
        f.write(template.format(**context))

    print(f"\n\n'{SETTINGS_LOCAL_PATH}' file created.")
    print("Please edit as necessary to change settings.")
    print("It is not included in source control, so please create backup copies.")

if __name__ == "__main__":
    main()