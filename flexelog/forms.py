from django.forms import ModelForm
from django.utils.translation import gettext_lazy as _

from .models import Entry


class EntryForm(ModelForm):
    class Meta:
        model = Entry
        fields = ["date", "attrs", "text"]
        localized_fields = ["date"]
        labels = {
            # gettext_lazy translates when form is rendered
            "date": _("Entry time"),
            "text": _("Text"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date"].disabled = True
