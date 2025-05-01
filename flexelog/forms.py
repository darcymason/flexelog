import json
from django.db import models
from django.forms import ModelForm, MultiValueField, MultiWidget, TextInput, modelform_factory
from django.forms import CharField
from django.utils.translation import gettext_lazy as _

from .models import Entry

def entry_form_factory(attrs):
    fields = ["date", "attrs", "text"]
    labels = [_("Entry time"), *attrs, _("Text")]
    return modelform_factory(
        Entry, 
        fields=fields,
        labels=labels,
        localized_fields = ["date"],    
    )



# class AttributesField(MultiValueField):
#     def __init__(self, **kwargs):
#         # Define one message for all fields.
#         self.attr_names = ("project", "category", "subject")
#         error_messages = {
#             "incomplete": "Enter all the required attributes.",
#         }
#         # Or define a different message for each field.
#         fields = (
#             CharField(
#                 error_messages={"incomplete": "Enter a Project."},
#             ),
#             CharField(
#                 error_messages={"incomplete": "Enter a Category."},
#                 #  validators=[RegexValidator(r"^[0-9]+$", "Enter a valid phone number.")],
#             ),
#             CharField(
#                 error_messages={"incomplete": "Enter a Subject."},
#                 # required=False,
#             ),
#         )
#         super().__init__(
#             error_messages=error_messages,
#             fields=fields,
#             require_all_fields=False,
#             **kwargs
#         )
#     def compress(self, data_list) -> dict:
#         """Return a JSON string of the attribute:value dict"""
#         return dict(zip(self.attr_names, data_list))


class AttributesWidget(MultiWidget):
    def __init__(self, attrs=None):
        self.attr_names = ("project", "category", "subject")
        widgets = (
            TextInput(),
            TextInput(),
            TextInput(),
        )
        super().__init__(widgets)

    def decompress(self, json_str):
        attrs = json.loads(json_str)
        return list(attrs.values())


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
        widgets = {
            "attrs": AttributesWidget(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
