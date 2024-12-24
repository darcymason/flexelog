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
That script reads the translation files from PSI (copies in flexelog/resources/psi_elog_lang),

NOTE: if do *not* want users to be able to each have their own language (set by the browser),
then remove the line
```
"django.middleware.locale.LocaleMiddleware",
```
from the `MIDDLEWARE` section of `settings.py`.
See https://docs.djangoproject.com/en/5.1/topics/i18n/translation/#how-django-discovers-language-preference
