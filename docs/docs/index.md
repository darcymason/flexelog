# Welcome to the FlexElog documentation

## Quickstart

### Installation
#### Set up Virtual environment and copy the source code
* create a virtual environment
* activate the venv
* clone the repository -- git clone <XXX addr>
* cd flexelog
* pip install -e .

This will install the django server and various other packages

#### Configure database / time / language settings
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
