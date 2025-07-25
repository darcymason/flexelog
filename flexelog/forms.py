# Copyright 2025 flexelog authors. See LICENSE file for details.
from django import forms
from django.conf import settings
from django.forms import (
    BooleanField,
    CharField,
    CheckboxSelectMultiple,
    ChoiceField,
    DateInput,
    DateTimeInput,
    EmailField,
    FloatField,
    Form,
    DateField,
    DateTimeField,
    Select,
    SplitDateTimeField,
    SplitDateTimeWidget,
    inlineformset_factory,
)
from django.forms import (
    HiddenInput,
    IntegerField,
    MultipleChoiceField,
    RadioSelect,
    TextInput,
    Textarea,
)
from django.utils.translation import gettext_lazy as _
from django.utils.safestring import mark_safe
from django.utils.datastructures import MultiValueDict

from flexelog.elog_cfg import Attribute, get_config
from flexelog.models import User
from .models import Attachment, Entry
from flexelog.editor.widgets_toastui import MarkdownEditorWidget, MarkdownViewerWidget


class MarkdownFormField(CharField):
    widget = MarkdownEditorWidget

class MarkdownViewerFormField(CharField):
    widget = MarkdownViewerWidget


formfield_for_type = dict(
    # Form field, widget
    date=(DateField, DateInput),
    datetime=(DateTimeField, SplitDateTimeWidget),
    numeric=(FloatField, TextInput),
    userlist=(ChoiceField, Select),
    useremail=(ChoiceField, Select),
    muserlist=(MultipleChoiceField, CheckboxSelectMultiple),
    museremail=(MultipleChoiceField, CheckboxSelectMultiple),
)

def lb_attrs_to_form_fields(
    lb_attrs: dict[str, Attribute], data: MultiValueDict | None = None
) -> dict:
    fields = {}
    for name, lb_attr in lb_attrs.items():
        if lb_attr.val_type:
            field_cls, widget = formfield_for_type[lb_attr.val_type.lower()]  # XX could error here unless cfg ensures Type <attr> is in list
            if widget is SplitDateTimeWidget:
                widget = SplitDateTimeWidget(attrs={"type": "datetime-local"})
            if lb_attr.val_type in ("userlist", "muserlist"):
                choices = [
                    (user.get_username(), user.get_username())  # ? f"{user.get_full_name}") 
                    for user in User.objects.all()
                    if not user.is_anonymous
                ]
            elif lb_attr.val_type in ("useremail", "museremail"):
                choices = [
                    (user.email, user.email)
                    for user in User.objects.all()
                    if user.email
                ]
            fields[name] = field_cls(
                widget=widget,
                required=lb_attr.required,
                label=name,
            )
            if field_cls in (ChoiceField, MultipleChoiceField):
                fields[name].choices = choices

        elif lb_attr.options_type in ("Options", "ROptions", "MOptions", "IOptions"):
            # Show choices(options) in current logbook config, and if entry has another, add them to choices
            choices = lb_attr.options
            if data and name in data:
                for entry_choice in data.getlist(name):
                    if entry_choice not in choices:
                        choices.append(entry_choice)

            choices = [(choice, choice) for choice in choices]
            if lb_attr.options_type == "Options":
                field_cls = ChoiceField
                widget = Select
            elif lb_attr.options_type in ("ROptions", "IOptions"):
                field_cls = ChoiceField
                widget = RadioSelect
                if lb_attr.options_type == "IOptions":
                    choices = [
                        (
                            choice[0],
                            mark_safe(
                                f'<img src="{settings.STATIC_URL}flexelog/icons/{choice[1]}" '
                                f'alt="{choice[1]}" title="{choice[1]}" '
                                " />"
                            ),
                        )  # XX need alt, title
                        for choice in choices
                    ]
            else:  # MOptions
                field_cls = MultipleChoiceField
                widget = CheckboxSelectMultiple

            fields[name] = field_cls(
                widget=widget,
                required=lb_attr.required,
                choices=choices,
                label=name,
            )
        else:
            fields[name] = CharField(
                required=lb_attr.required,
                max_length=1500,
                widget=TextInput(attrs={"size": 80}),
                label=name,
                error_messages={"required": _("Please enter attribute '%s'") % name},
            )  # xX for file psi-elog used size="60" maxlength="200"
    return fields


class EntryForm(Form):
    date = DateTimeField(
        label=_("Entry time"),
        required=True,
        localize=True,
        widget=TextInput(attrs={"readonly": "readonly"}),
    )
    text = MarkdownFormField(
        required=False
    )  # note some logbooks can have no text field
    # Hidden fields to persist info needed:
    page_type = CharField(widget=HiddenInput(), initial="New")
    attr_names = CharField(widget=HiddenInput(), required=False)
    edit_id = IntegerField(widget=HiddenInput(), required=False)
    in_reply_to = IntegerField(widget=HiddenInput(), required=False)

    def __init__(self, data=None, *args, **kwargs):
        self.entry_attrs = lb_attrs = kwargs.pop(
            "lb_attrs"
        )  # save for conditionals later
        super().__init__(data, *args, **kwargs)

        # XXX need to check entry for attrs that are no longer configd for the logbook
        self.fields.update(lb_attrs_to_form_fields(lb_attrs, data=data))
        attr_names = list(lb_attrs.keys())
        self.order_fields(["date", *attr_names, "text"])
        attr_str = ",".join(attr_names)
        self.fields["attr_names"].initial = attr_str

    @classmethod
    def from_entry(cls, entry: Entry, page_type, lb_attrs) -> "EntryForm":
        cfg = get_config()
        # XXX add any extra attrs now in lb config that aren't in this entry
        data = MultiValueDict()
        data["date"] = entry.date
        data["in_reply_to"] = entry.in_reply_to.id if entry.in_reply_to else ""
        data["edit_id"] = entry.id
        data["text"] = entry.text
        data["page_type"] = page_type
        attr_names = list(lb_attrs.keys())
        if entry.attrs:
            attr_names += [name for name in entry.attrs.keys() if name not in attr_names]
        data["attr_names"] = ",".join(attr_names)
        if entry.attrs is not None:
            for attr_name, val in entry.attrs.items():
                if isinstance(val, list):
                    data.setlist(attr_name, val)
                else:
                    data[attr_name] = val
        lb_attrs = cfg.lb_attrs[entry.lb.name]
        form = cls(data=data, lb_attrs=lb_attrs)

        return form


# In future may try to combine edit and view into one form.
# Here just have a kludge to get Viewer widget rendered
class EntryViewerForm(Form):
    text = MarkdownViewerFormField(
        required=False
    )  # note some logbooks can have no text field


class SearchForm(Form):
    mode = MultipleChoiceField(
        required=False,
        widget=RadioSelect(),
        choices=[
            ("Display full", _("Display full entries")),
            ("Summary", _("Summary only")),
            ("Threads", _("Display threads")),
        ],
        label=_("Mode"),
    )
    export_to = MultipleChoiceField(
        required=False,
        widget=RadioSelect(),
        choices=[
            ("CSV1", _('CSV ("," separated)')),
            ("CSV2", _('CSV (";" separated)')),
            ("CSV3", _('CSV (";" separated) + Text')),
            ("XML", _("XML")),
            ("Raw", _("Raw")),
        ],
        label=_("Export to"),
    )
    options = MultipleChoiceField(
        required=False,
        widget=CheckboxSelectMultiple(),
        choices=[
            ("attach", _("Show attachments")),
            ("printable", _("Printable output")),
            ("reverse", _("Sort in reverse order")),
            ("all", _("Search all logbooks")),
        ],
        label=_("Options"),
    )
    npp = IntegerField(
        widget=TextInput(attrs={"size": 3}),
        min_value=1,
        label=_("entries per page"),
        initial=20,
    )
    # ----- bottom half
    # XX does datetime-local need to be converted to server time?
    start_date = DateTimeField(
        required=False,
        widget=DateTimeInput(attrs={"type": "datetime-local"}),
        label=_("Start"),
    )
    end_date = SplitDateTimeField(
        required=False,
        widget=DateTimeInput(attrs={"type": "datetime-local"}),
        label=_("End"),
    )
    last = MultipleChoiceField(
        required=False,
        widget=Select(),
        choices=[
            ("", ""),
            ("1", _("Day")),
            ("3", _("3 Days")),
            ("7", _("Week")),
            ("31", _("Month")),
            ("92", _("3 Months")),
            ("182", _("6 Months")),
            ("364", _("Year")),
        ],
        label=_("Show last"),
    )
    # Then attrs added in __init__
    subtext = CharField(
        required=False,
        widget=TextInput(attrs={"size": 30, "maxlength": 80}),
        label=_("Text"),
    )
    sall = BooleanField(required=False, label=_("Search text also in attributes"))
    casesensitive = BooleanField(required=False, label=_("Case sensitive"))

    def __init__(self, data=None, *args, **kwargs):
        self.entry_attrs = lb_attrs = kwargs.pop(
            "lb_attrs"
        )  # save for conditionals later
        super().__init__(data, *args, **kwargs)

        # XXX need to check entry for attrs that are no longer configd for the logbook
        attr_fields = lb_attrs_to_form_fields(lb_attrs, data=data)
        for field in attr_fields.values():
            field.required = False
        self.fields.update(attr_fields)

        # Get bound fields used in html template
        self.attr_bound_fields = {
            name: field.get_bound_field(self, name)
            for name, field in attr_fields.items()
        }

class ListingModeFullForm(Form):
    """dummy form to get media loaded on the page"""
    text = MarkdownViewerFormField()


class AttachmentForm(forms.ModelForm):
    # This field will be used for displaying existing attachments with a delete checkbox
    delete_attachment = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

    class Meta:
        model = Attachment
        fields = ['attachment_file'] # manage 'entry' through the formset below


AttachmentFormSet = inlineformset_factory(
    Entry,
    Attachment,
    form=AttachmentForm,
    fields=['attachment_file'],
    extra=3, # Number of empty forms to display for new attachments
    can_delete=True,
    widgets={
        'attachment_file': forms.FileInput(attrs={'class': 'form-control'}),
    }
)