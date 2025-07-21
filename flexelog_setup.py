# Copyright 2025 flexelog authors. See LICENSE file for details.
import os
import sys
from pathlib import Path
from django.core.management.utils import get_random_secret_key
import tzlocal
import subprocess

usage = """
Flexelog setup:

Run this once for each elog server you wish to set up, to produce settings file(s).
Each server can have multiple logbooks, but only one set of users defined.

You can edit the settings file afterwards, but this gives a start by:
* creating a SECRET_KEY using django's `get_random_secret_key`
* asking for a base directory and elog name (more below), 
  and then creating a directory structure like:
  path/to/flexelog/data
      elogname
          elogname.db  (assuming sqlite)
          "media" folder (where attachments will go)
      [...]   
* asking for your server's time zone

If not using sqlite, then you will need to edit the DATABASES 
section of `settings_<elogname>.py` yourself after this script.

If unsure of the elog name just use something generic
like "elog" or "main".
"""

HERE = Path(__file__).resolve().parent
TEMPLATE_PATH = HERE / "flexsite" / "settings_local_template.txt"
SETTINGS_LOCAL_FOLDER = HERE / "flexsite"
RUN_TEMPLATE = '{py} manage.py runserver {port} {settings_arg}"'


def validate_yes_no(answer):
    answers = ("y", "n", "yes", "no")
    if answer.lower() in answers:
        return ""
    return f"Answer must be one of {answers}"

def yes_or_no(prompt, default) -> bool:
    answer = get_input(prompt, default=default, validator=validate_yes_no)
    return answer.lower().startswith("y")

def validate_dir(answer):
    path = Path(answer)
    if path.exists():
        return "" if path.is_dir() else "Path is an existing file.  Please enter a directory name."

    return ""

def validate_port(answer):
    try:
        int(answer)
    except:
        return "An internet port must be an integer"
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

    if 'VIRTUAL_ENV' not in os.environ:
        print("It appears you are not currently running in a virtual environment")
        if not yes_or_no("Continue anyway?", "no"):
            sys.exit(-1)

    context = {"SECRET_KEY": get_random_secret_key()}
    print("Secret key created.\n")

    have_PSI = get_input(
        "Will you be migrating a previous (PSI) elog)?",
        validator=validate_yes_no,
        default="no"
    )
    have_PSI = (have_PSI.lower().startswith("y"))
    # XX If have_PSI, then could get Top group names for the user

    print("Enter a name for this elog server.")
    print("E.g. your organization name, or department name, ")
    print("or Home if a personal elog server")
    if have_PSI:
        print("This could be a 'Top Group' name from PSI elog")
    
    top_group = get_input(
        "Enter a name for this group of e-logbooks", 
        default="elog",
    )
    context["TOP_GROUP_NAME"] = top_group
    settings_local_filepath = SETTINGS_LOCAL_FOLDER / f"settings_{top_group}.py"
    
    if settings_local_filepath.exists():
        if not yes_or_no(f"File '{settings_local_filepath}' exists. Overwrite?", "yes"):
            sys.exit(-1)

    # Base directory ----------------------------
    context["ELOG_DIR"] = elog_dir = get_input(
        "Folder for elog database/attachments",
        default = Path.home() / "flexelog",
        validator=validate_dir,
    )
    # Create dir, if necessary, under top group folder below
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
    context["DATABASE_NAME"] = f"{context['TOP_GROUP_NAME'] or 'flexelog'}.db"
    # python manage.py migrate will create the database file

    context["TIME_ZONE"] = get_input(
        "Enter the server timezone in IANA format e.g. America/Toronto\n"
        "(https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)",
        default = tzlocal.get_localzone_name(),
    )    

    port = get_input("Choose a server port number", default="8000", validator="validate_int")
    
    # Create the settings_local.py file: ---------------------
    template = open(TEMPLATE_PATH, 'r').read()
    print(f"Writing '{settings_local_filepath}'")

    with open(settings_local_filepath, 'w') as f:
        f.write(template.format(**context))

    # Create a script to launch this elog --------------------
    on_windows = sys.platform.startswith("win")
    run_filename = f"run_{top_group}" + ".bat" if on_windows else ""
    py = "python" if on_windows else "python3"
    settings_arg = f'--settings="flexsite.settings_{top_group}"'
    run_statement = RUN_TEMPLATE.format(
        py=py,
        settings_arg=settings_arg,
        port=port,
    )

    with open(HERE / run_filename, "w") as f:
        f.write(run_statement)

    # --------------------
    # Init the database
    print()
    init_db = yes_or_no("Do you want to initialize the database?", "yes")
    if init_db:
        migrate_stmt = f"{py} manage.py migrate {settings_arg}"
        super_stmt = f"{py} manage.py createsuperuser {settings_arg}"
        print("----------")
        print(f"Running `{migrate_stmt}`")
        compl_proc = subprocess.run([py, "manage.py", "migrate", settings_arg])
        if compl_proc.returncode != 0:
            print(f"Command exited with code {compl_proc.returncode}")
        print("----------")
        print(f"Running `{super_stmt}`")
        compl_proc = subprocess.run(super_stmt)
        if compl_proc.returncode != 0:
            print(f"Command exited with code {compl_proc.returncode}")

    print()
    print(f"\n\nPlease review and edit settings file '{settings_local_filepath}' as needed.")
    print("It is not included in source control, so please create backup copies.")
    print()
    print("The above are 'one-time' setup steps.")
    print("For ongoing use, to launch the server:")
    print("  - activate the virtual environment (if used) ")
    print(f" `{run_statement}` at the command line")
    print(f"This line is also stored in file `{run_filename}`")
    

if __name__ == "__main__":
    main()