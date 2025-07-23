# Copyright 2025 flexelog authors. See LICENSE file for details.
import os
import sys
from pathlib import Path
from django.core.management.utils import get_random_secret_key
import tzlocal
import subprocess
from flexelog.script_util import yes_to, get_input, get_dir, get_port

usage = """
Flexelog setup: Create basic settings files for running under Django

Run this once for each elog server you wish to set up, to produce settings file(s).
Each server can have multiple logbooks, but only one set of users defined.

You can edit the settings file afterwards, but this gives a start by:
* creating a SECRET_KEY and various settings
* creating a sqlite database with directory structure like:
  path/to/flexelog/data
      elogname
          elogname.db 
          "media" folder  (for elog entry attachments)
      [...]   
"""

HERE = Path(__file__).resolve().parent
TEMPLATE_PATH = HERE / "flexsite" / "settings_local_template.txt"
SETTINGS_LOCAL_FOLDER = HERE / "flexsite"
RUN_TEMPLATE = '{py} manage.py runserver {port} {settings_arg}'


def main():
    print(usage)
    print()

    if sys.base_prefix == sys.prefix:
        print("It appears you are not currently running in a virtual environment")
        if not yes_to("Continue?", "no"):
            sys.exit(-1)

    context = {"SECRET_KEY": get_random_secret_key()}
    print("Secret key created.\n")

    have_PSI = yes_to("Will you be migrating a previous (PSI) elog)?", "no")
    # XX If have_PSI, then could get Top group names for the user

    print("Enter a name for this elog server, e.g. an organization name, ")
    print("department name, 'main', etc.")
    if have_PSI:
        print("This could be a 'Top Group' name from PSI elog")
    
    top_group = get_input(
        "Enter a name for this group of e-logbooks", 
        default="main",
    )
    context["TOP_GROUP_NAME"] = top_group
    settings_local_filepath = SETTINGS_LOCAL_FOLDER / f"settings.py"
    
    single_site = True
    if settings_local_filepath.exists():
        print("If you wish to have multiple elog servers, choose No to the following override.")
        if not yes_to(f"File '{settings_local_filepath}' exists. Overwrite?", "yes"):
            if not yes_to(f"Create a new settings file `settings_{top_group}`?", "yes"):
                sys.exit(-1)
            single_site = False
            settings_local_filepath = SETTINGS_LOCAL_FOLDER / f"settings_{top_group}.py"

    # Base directory ----------------------------
    context["ELOG_DIR"] = elog_dir = get_dir("Folder for elog database/attachments", Path.home() / "flexelog")
    
    # Create dir, if necessary, under top group folder below
    tg_path = Path(elog_dir) / top_group
    Path(tg_path).mkdir(parents=True, exist_ok=True)

    # Database ------------------------------------
    context["DATABASE_NAME"] = f"{context['TOP_GROUP_NAME'] or 'flexelog'}.db"
    # python manage.py migrate will create the database file

    context["TIME_ZONE"] = get_input(
        "Enter the server timezone e.g. America/Toronto, Europe/Paris\n"
        "(https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)",
        default = tzlocal.get_localzone_name(),
    )    

    port = get_port("Choose a server port number", default="8000")
    
    # Create the settings[_<top_group>].py file: ---------------------
    template = open(TEMPLATE_PATH, 'r').read()
    print(f"Writing '{settings_local_filepath}'")

    with open(settings_local_filepath, 'w') as f:
        f.write(template.format(**context))

    # Create a script to launch this elog --------------------
    on_windows = sys.platform.startswith("win")
    run_filename = f"run_{top_group}" + ".bat" if on_windows else ""
    py = sys.executable
    settings_arg = "" if single_site else f'--settings=flexsite.settings_{top_group}'
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
    db_filepath = tg_path / context['DATABASE_NAME']
    init_db = yes_to("Do you want to initialize the database?", "yes")
    if init_db:
        if db_filepath.exists():
            if yes_to("Database file exists.  Delete and reinitialize? (ARE YOU SURE?)", "no"):
                db_filepath.unlink()
            else:
                sys.exit(-1)
        migrate_stmt = f"{py} manage.py migrate {settings_arg}"
        super_stmt = f"{py} manage.py createsuperuser {settings_arg}"
        print("----------")
        print(f"Running `{migrate_stmt}`")
        compl_proc = subprocess.run([py, "manage.py", "migrate", settings_arg])
        if compl_proc.returncode != 0:
            print(f"Command exited with code {compl_proc.returncode}")
            sys.exit(-1)
        print("----------")
        print(f"Running `{super_stmt}`")
        compl_proc = subprocess.run(super_stmt)
        if compl_proc.returncode != 0:
            print(f"Command exited with code {compl_proc.returncode}")
            sys.exit(-1)
    print()
    print(f"\n\nPlease review and edit settings file '{settings_local_filepath}' as needed.")
    print("It is not included in source control, so please create backup copies.")
    print()
    print("The above are 'one-time' setup steps.")
    print("For ongoing use, to launch the server in dev/testing mode:")
    print("  - activate the virtual environment (if used) ")
    print(f" `{run_statement}` at the command line")
    print(f"This line is also stored in file `{run_filename}`")
    print("\nThe above may be sufficient for low-traffic internal websites, but ")
    print("for proper website deployment, Django should be run behind a production server.")
    print("See the django documentation (https://docs.djangoproject.com/en/stable/howto/deployment)")


if __name__ == "__main__":
    main()