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

#### Set up the database
* choose whether to use sqlite (default) or some other database system
* create/edit `local_settings.py` to point to your own database type and file
* python manage.py makemigrations
* python manage.py migrate
* set up an admin user: ...

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
