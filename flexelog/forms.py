from django.forms import CharField, CheckboxSelectMultiple, Form, DateTimeField
from django.forms import HiddenInput, IntegerField, MultipleChoiceField, RadioSelect, TextInput, Textarea
from django.utils.translation import gettext_lazy as _
from django.utils.datastructures import MultiValueDict

from flexelog.elog_cfg import Attribute, get_config
from django_tuieditor.fields import MarkdownFormField, MarkdownViewerFormField
from .models import Entry


def lb_attrs_to_form_fields(lb_attrs: dict[str, Attribute], data: MultiValueDict=None) -> dict:
    fields = {}
    for name, lb_attr in lb_attrs.items():   
        if lb_attr.options_type in ("ROptions", "MOptions"):
            # Show choices(options) in current logbook config, and if entry has another, add them to choices
            choices = lb_attr.options
            if data and name.lower() in data:
                for entry_choice in data.getlist(name.lower()):
                    if entry_choice not in choices:
                        choices.append(entry_choice)

            fields[name.lower()] = MultipleChoiceField(
                widget=RadioSelect if lb_attr.options_type == "ROptions" else CheckboxSelectMultiple, 
                required=lb_attr.required, 
                choices=[(choice, choice) for choice in choices],
                error_messages={"required": _("Please enter attribute '%s'") % name},
            )
        else:
            fields[name.lower()] = CharField(
                required=lb_attr.required,
                max_length=1500,
                widget = TextInput(attrs={"size": 80}),
                error_messages={"required": _("Please enter attribute '%s'") % name},
            )  # xX for file psi-elog used size="60" maxlength="200"
    return fields


class EntryForm(Form):
    date = DateTimeField(label=_("Entry time"), required=True, localize=True, widget=TextInput(attrs={"readonly": "readonly"}))
    text = MarkdownFormField(required=False) # note some logbooks can have no text field
    # Hidden fields to persist info needed:
    page_type = CharField(widget=HiddenInput(), initial="New")
    attr_names = CharField(widget=HiddenInput(), required=False)
    edit_id = IntegerField(widget=HiddenInput(), required=False)
    reply_to = IntegerField(widget=HiddenInput(), required=False)

    def __init__(self, data=None, *args, **kwargs):
        self.entry_attrs = lb_attrs = kwargs.pop("lb_attrs")  # save for conditionals later
        super().__init__(data, *args, **kwargs)

        # XXX need to check entry for attrs that are no longer configd for the logbook
        self.fields.update(lb_attrs_to_form_fields(lb_attrs, data=data))
        attr_names = [x.lower() for x in lb_attrs.keys()]
        self.order_fields(["date", *attr_names, "text"])
        attr_str = ",".join(attr_names)
        self.fields["attr_names"].initial = attr_str


    @classmethod
    def from_entry(cls, entry: Entry, page_type) -> "EntryForm":
        cfg = get_config()
        # XXX add any extra attrs now in lb config that aren't in this entry
        data = MultiValueDict()
        data["date"] = entry.date
        data["reply_to"] = entry.reply_to
        data["edit_id"] = entry.id
        data["text"] = entry.text
        data["page_type"] = page_type
        data["attr_names"] = ",".join(x.lower() for x in entry.attrs.keys())
        for attr_name, val in entry.attrs.items():
            if isinstance(val, list):
                data.setlist(attr_name.lower(), val)
            else:
                data[attr_name.lower()] = val
        lb_attrs = cfg.lb_attrs[entry.lb.name]        
        form = cls(data=data, lb_attrs=lb_attrs)
            
        return form
    


# In future may try to combine edit and view into one form.
# Here just have a kludge to get Viewer widget rendered
class EntryViewerForm(Form):
    text = MarkdownViewerFormField(required=False) # note some logbooks can have no text field


class SearchForm(Form):
    page_type = CharField(widget=HiddenInput(), initial="Search")
    attr_names = CharField(widget=HiddenInput(), required=False)
    mode = MultipleChoiceField(
        widget=RadioSelect(),
        choices = [
            ("Display full", _("Display full entries")), 
            ("Summary", _("Summary only")), 
            ("Threads", _("Display threads")),
        ],
        label=_("Mode"),
    )
    export_to = MultipleChoiceField(
        widget=RadioSelect(),
        choices = [
            ("CSV1", _('CSV ("," separated)')), 
            ("CSV2", _('CSV (";" separated)')), 
            ("CSV3", _('CSV (";" separated) + Text')),
            ("XML", _("XML")),
            ("Raw", _("Raw")),
        ],
        label=_("Export to"),
    )
    options = MultipleChoiceField(
        widget = CheckboxSelectMultiple(),
        choices = [
            ("attach", _("Show attachments")), 
            ("printable", _("Printable output")), 
            ("reverse", _("Sort in reverse order")),
            ("all", _("Search all logbooks")),
        ],
        label=_("Options"),
    )
    npp = IntegerField(widget=TextInput(attrs={"size": 3}), min_value=1, label=_("entries per page"), initial=20)