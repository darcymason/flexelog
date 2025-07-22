# Welcome to the FlexElog documentation

## Quickstart

### Installation
#### Set up Virtual environment and copy the source code
* create a virtual environment (optional, but recommended)
  `python -m venv .venv`
* activate the venv
  (linux)   `source .venv/bin/activate` 
  (Windows) `.venv\Scripts\activate.bat` 

* clone the repository
  (Windows):  download git from https://git-scm.com/ and install
  `git clone --depth=1 https://github.com/darcymason/flexelog.git`
* `cd flexelog`
* `python -m pip install -e .`

This will install the django server and various other packages

#### Running the demo

After the steps above, you can run a minimal example elog 
* ensure virtual environment is activated, if used (see above)
* (Windows): run_demo.bat
* (linux, MacOS): ./run_demo
* the admin login is user 'demo', password 'demo--demo'

#### Configure database / time / language settings

##### Basic sqlite database setup
* in the `flexelog` folder (with `manage.py` in it), run:
  `python flexelog_setup.py`
* answer the questions, press Enter to accept the default shown
* choose yes to initialize the database

* choose whether to use sqlite (default) or some other database system
* edit `settings.py` to:
  * point to your own database engine or file (under `DATABASES`)
  * set your default local time zone (`TIME_ZONE`).  Leave `USE_TZ` as `True`
  * set your default language (`LANGUAGE_CODE`).  The users' browser settings can override this language to provide each with their own language, if it is available.
  * adjust `FILE_UPLOAD_MAX_SIZE` if you need a higher or lower limit
* python manage.py makemigrations
* python manage.py migrate
* python manage.py createsuperuser  (for a new blank database to set up the admin user)
* python manage.py runserver (to try running in debug mode, before setting up a proper webserver)


### Activate language support
Many translation documents (gettext .po files) are in the distribution.  To compile them and make them visible to Django, run:
* python manage.py compilemessages
Then if you set a non-English language first in your browser Settings | Language list, many text instructions, table headers, error messages etc. will be displayed in that language.

For more information about language support, see the [Translation](translation.md) document.

### Migrating an existing elog
* if you have an existing PSI Elog set up, and wish to port it, then run:
  <XXX migration commands>
This will populate database tables with information about your logbooks, 
their configuration, and migrate over all the existing elog entries from
log files on disk into the database table

The admin user can view/edit the tables by going to the `/admin` url for the site.
