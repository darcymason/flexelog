# FlexElog translation

## Sources

Original translations are from PSI elog's resources directory,
reformmated to a `gettext`-style setup as per usual Django (and Python in general) practice.

To prepare the 'POT' files which contain the translations:

```console
python manage.py makemessages --all
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

The `psi_translations` script reads the translation files from PSI (copies in flexelog/psi_elog/lang).  Background info for developers: those files were all converted to utf-8 encoding and renamed using script `eloglang_to_utf.py` in the same folder. That should not need to be run again, unless updates to PSI elog language files were needed -- however would overwrite any edits made in those files, so use with caution.

NOTE: if do *not* want users to be able to each have their own language (set by the browser),
then remove the line
```
"django.middleware.locale.LocaleMiddleware",
```
from the `MIDDLEWARE` section of `settings.py`.
See https://docs.djangoproject.com/en/5.1/topics/i18n/translation/#how-django-discovers-language-preference
