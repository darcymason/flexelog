# FlexElog translation

## Sources

Original translations are from PSI elog's resources directory,
reformmated to a `gettext`-style setup as per usual Django (and Python in general) practice.

To prepare the 'POT' files which contain the translations:

```console
python manage.py makemessages -l de
```

Then run

```
python manage.py psi_translations
```

If necessary, further edit the django.po files to add additional translations.
Finally, run
```
python manage.py compilemessages
```
which produces the final .mo files used by Django's internationalization/localization.

The `psi_translations` script reads the translation files from PSI (copies in flexelog/psi_elog/lang).  NOTE: some of those files were renamed to put the charset into the file extension, where it was not `latin1`.  If the files are later updated from the PSI elog source code, remember to rename them appropriately.

NOTE: if do *not* want users to be able to each have their own language (set by the browser),
then remove the line
```
"django.middleware.locale.LocaleMiddleware",
```
from the `MIDDLEWARE` section of `settings.py`.
See https://docs.djangoproject.com/en/5.1/topics/i18n/translation/#how-django-discovers-language-preference
