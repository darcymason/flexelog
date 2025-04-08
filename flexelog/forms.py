from django.db import models
from django.forms import ModelForm, modelform_factory
from django.forms import CharField
from django.utils.translation import gettext_lazy as _

from .models import Entry

def entry_form_factory(attrs):
    fields = ["date", *(f"attrs__{attr}" for attr in attrs), "text"]
    labels = [_("Entry time"), *attrs, _("Text")]
    return modelform_factory(
        Entry, 
        fields=fields,
        labels=labels,
        localized_fields = ["date"],    
    )

# class EntryForm(ModelForm):
#     class Meta:
#         model = Entry
#         fields = ["date", "text"]
#         localized_fields = ["date"]
#         labels = {
#             # gettext_lazy translates when form is rendered
#             "date": _("Entry time"),
#             "text": _("Text"),
#         }

#     def __init__(self, *args, **kwargs):
#         attr_names = kwargs.pop("attr_names", None)
#         super().__init__(*args, **kwargs)
#         if attr_names:
#             for attr_name in attr_names:
#                 self.fields[attr_name] = CharField(label=attr_name, max_length=100)
#         self.fields = ["date", *attr_names, "text"]
#         self.fields["date"].disabled = True