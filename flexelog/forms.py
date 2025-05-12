import json
from django.db import models
from django.forms import CheckboxSelectMultiple, Form, DateTimeField, CharField, MultiValueField, MultiWidget, MultipleChoiceField, RadioSelect, SelectMultiple, TextInput, Textarea, modelform_factory
from django.forms import CharField
from django.utils.translation import gettext_lazy as _

from flexelog.elog_cfg import Attribute

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
    def __init__(self, lb_attrs: list[Attribute], entry: Entry | None=None):
        widgets = []
        for attr in lb_attrs:
            if attr.options_type == "Text":
                # value=entry.attrs[attr.name] if entry else ""
                # if isinstance(value, list):
                #     value = "|".join(value)
                widgets.append(TextInput(attrs=dict(size="80", maxlength="1500")))
                    # id="fid",
                    # name=attr.name,
                    # value=value,
                    # onkeydown="return event.key != 'Enter';",
                # )  # XX need value if not new

            elif attr.options_type == "MOptions":  # checkboxes
                widgets.append(CheckboxSelectMultiple())
                for i, option in enumerate(attr.options):
                    with h.span(style="white-space:nowrap;"):
                        option_id = f"{attr.name}_{i}"

                        kwargs = dict(
                            type="checkbox",
                            id=option_id,
                            name=attr.name,
                            value=option,
                            onkeydown="return event.key != 'Enter';",
                        )
                        if entry and option in entry.attrs.get(attr.name):
                            kwargs["checked"] = None
                        h.input(**kwargs)
                        h.label(option, for_=option_id)

            elif attr.options_type == "Options":  # dropdown list
                with h.select(
                    name=attr.name,
                    onkeydown="return event.key != 'Enter';",
                    onchange="document.form1.submit()",
                ):
                    h.option(f'- {_("please select")} -', value="")
                    for option in attr.options:
                        if entry and entry.attrs.get(attr.name) == option:
                            h.option(option, value=option, selected=None)
                        else:
                            h.option(option, value=option)
                    # XX <input type=submit name="extend_1" value="Add {attr.name}" onClick="return mark_submitted();">
            # XXX elif attr.options_type == "ROptions"



        # self.attr_names = ("project", "category", "subject")
        # widgets = (
        #     TextInput(),
        #     TextInput(),
        #     TextInput(),
        # )
        super().__init__(widgets)

    def decompress(self, json_str):
        attrs = json.loads(json_str)
        return list(attrs.values())




def lb_attrs_to_form_fields(lb_attrs: dict[str, Attribute]) -> dict:
    fields = {}
    for name, lb_attr in lb_attrs.items():   
        if lb_attr.options_type in ("ROptions", "MOptions"):
            fields[name] = MultipleChoiceField(
                widget=RadioSelect if lb_attr.options_type == "ROptions" else CheckboxSelectMultiple, 
                required=lb_attr.required, 
                choices=list(enumerate(lb_attr.options)),
            )
        else:
            fields[name] = CharField(
                required=lb_attr.required,
                max_length=1500,
                widget = TextInput(attrs={"size": 80}),
            )  # xX for file elog used size="60" maxlength="200"
    return fields


class EntryForm(Form):
    date = DateTimeField(label=_("Entry time"),required=True, localize=True, disabled=True)
    text = CharField(widget=Textarea)

    def __init__(self, lb_attrs, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.entry_attrs = lb_attrs  # save for conditionals later
        # XXX need to check entry for attrs that are no longer configd for the logbook
        self.fields.update(lb_attrs_to_form_fields(lb_attrs))
        self.order_fields(["date", *lb_attrs.keys(), "text"])
        