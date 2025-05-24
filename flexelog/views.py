from copy import copy
from datetime import datetime
import logging
import textwrap
from typing import Any
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.core.paginator import Paginator, Page
from django.db.models.functions import Lower
from django.http import HttpResponse, QueryDict
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from flexelog.forms import EntryForm, EntryViewerForm, SearchForm


from .models import Logbook, Entry
from .elog_cfg import get_config

from urllib.parse import unquote_plus

from django_tuieditor.widgets import MarkdownViewerWidget


def get_param(
    request, key: str, *, valtype: type = str, default: Any = None, force_single=True
) -> Any:
    """Return the GET query value for key, but default if not found or not of right type

    get_single only affects what happens if a value in the query string is repeated.
    If True, it is standard Django 'get' behaviour - the last value is returned.

    If any value of the parameter can't be converted to `valtype`, then `default` is returned.
    """
    if force_single:
        val = request.GET.get(key, default)
        if val == default:
            return val
        try:
            return valtype(val)
        except ValueError:
            return default

    val = request.GET.getlist(key, default)
    if len(val) == 0 or val == default:
        return default
    try:
        val = [valtype(x) for x in val]
    except ValueError:
        val = default

    return val[0] if len(val) == 1 else val


def do_logout(request):
    return render(request, "flexelog/do_logout.html")


def index(request):
    # XXX need to check Protect Selection page whether the list is shown only to registered users,
    #   (or do equivalent permissions "view logbook index" or similar)
    # OR Selection page = <file> / Guest Selection page = <file> equiv (latter if 'global' password file used in PSI elog)
    # Welcome Title = <html code> equivalent needed
    # Page title from [global] section
    #
    cfg = get_config()
    logbooks = [lb for lb in Logbook.objects.all() if lb.name in cfg.logbook_names()]

    context = {
        "cfg": cfg,
        "logbooks": logbooks,
        "heading": "FlexElog Logbook Selection",
        "cfg_css": cfg.get(
            "global", "css", valtype=str, default=""
        ),  # XXX admin forces global since lb can't exist
    }
    return render(request, "flexelog/index.html", context)


def logbook_post(request, logbook):
    """Handle POST to logbook page - can be New, Reply, Edit form results"""
    # XX auth - need to confirm user can New or Reply or Edit or Delete

    cfg = get_config()
    if request.POST.get("cmd") in (_("Submit"), _("Save")):
        page_type = request.POST["page_type"]
        attr_names = request.POST["attr_names"].split(",")
        lb_attrs = cfg.lb_attrs[logbook.name]
        form = EntryForm(data=request.POST, lb_attrs=lb_attrs)
        if not form.is_valid():
            context = form.get_context()
            context.update(
                {
                    "logbook": logbook,
                    "logbooks": Logbook.objects.all(),  # XX will need to restrict to what user auth is, not show deactivated ones
                    "main_tab": cfg.get(logbook.name, "main tab", valtype=str, default=""),
                    "cfg_css": cfg.get(logbook.name, "css", valtype=str, default=""),
                }
            )
            return render(request, "flexelog/edit.html", context)

        # Form is valid, now save the inputs to a database Entry
        attrs = {attr_name: form.cleaned_data[attr_name] for attr_name in attr_names}
        if page_type == "Edit":
            entry = Entry.objects.get(lb=logbook, id=form.cleaned_data["edit_id"])
            is_new_entry = False
        else:  # New/Reply
            entry = Entry()
            entry.lb = logbook  # XX security - should check logbook = original entry if a reply
            is_new_entry = True
        # Fill in edit object
        entry.attrs = attrs
        entry.text = form.cleaned_data["text"]
        if page_type in ("New", "Reply"):
            entry.date = form.cleaned_data["date"]
            # Find max id for this logbook and add 1
            # XXX is this thread-safe?  
            max_entry = logbook.entry_set.order_by("-id").first()
            entry.id = max_entry.id + 1 if max_entry else 1
        entry.save(force_insert=is_new_entry)  # XXX Could trap exists error and try again id +=1
        redirect_url = reverse("flexelog:entry_detail", args=[logbook.name, entry.id])
        return redirect(redirect_url)
    # XXX need to cover other cases?


# view for route "<str:lb_name>/"
def logbook_view(request, lb_name):
    # if not request.user.is_authenticated:
    #     return redirect(f"{settings.LOGIN_URL}?next={request.path}")
    lb_name = unquote_plus(lb_name)
    try:
        logbook = Logbook.objects.get(name=lb_name)
    except Logbook.DoesNotExist:
        context = {
            "message": _('Logbook "%s" does not exist on remote server') % lb_name
        }
        return render(request, "flexelog/show_error.html", context)

    # New (incl Reply), Edit, Delete all POST to the logbook page
    # (makes some sense as New doesn't have an id yet)
    if request.method == "POST":
        return logbook_post(request, logbook)
    return logbook_get(request, logbook)
    
def logbook_get(request, logbook):    
    cmd = get_param(request, "cmd")
    if cmd == _("New"):
        return entry_detail_get(request, logbook, None)
    elif cmd == _("Find"):
        lb_attrs = cfg.lb_attrs[logbook.name]
        # for lb_attr in lb_attrs.values():
        #     lb_attr.required = False
        form = SearchForm(
            initial={"options": ["reverse"], "mode": "Display full"}, lb_attrs=lb_attrs
        )
        cfg = get_config()
        context = {
            "command_names": [_("Search"), _("Reset Form"), _("Back")],
            "form": form,
            "logbook": logbook,
            "logbooks": Logbook.objects.all(),  # XX will need to restrict to what user auth is, not show deactivated ones
            "main_tab": cfg.get(logbook.name, "main tab", valtype=str, default=""),
            "cfg_css": cfg.get(logbook.name, "css", valtype=str, default=""),
            "regex_message": _("Text fields are treated as %s")
            % f'<a href="https://docs.python.org/3/howto/regex.html">{_("regular expressions")}</a>',
        }

        return render(request, "flexelog/search_form.html", context)

    # Now dealing with GET, listing logbook entries
    selected_id = get_param(request, "id", valtype=int)

    # XX Adjust available commands according to config
    # XX then according to user auth
    # XX Select command not implemented
    cfg = get_config()
    command_names = [
        _("New"),
        _("Find"),
        _("Import"),
        _("Config"),
        _("Last day"),
        _("Help"),
    ]
    lb_url = reverse("flexelog:logbook", args=[logbook.name])
    commands = [(cmd, f"{lb_url}?cmd={cmd}") for cmd in command_names]
    commands[4] = (_("Last day"), f"{lb_url}past1?mode=Summary")

    modes = (  # First text is translated, url param is not
        (_("Full"), "?mode=full"),
        (_("Summary"), "?mode=summary"),
        (_("Threaded"), "?mode=threaded"),
    )
    current_mode = _(get_param(request, "mode", default="Summary").capitalize())

    attrs = list(
        cfg.lb_attrs[logbook.name].keys()
    )  # XX can also config Attributes shown
    attrs_lower = [attr.lower() for attr in attrs]
    # XX col order could be changed in config
    col_names = [_("ID"), _("Date")] + attrs
    col_fields = ["id", "date"] + [f"attrs__{attr.lower()}" for attr in attrs]
    # Add Text column if config'd to do so
    summary_lines = cfg.get(logbook.name, "Summary lines", valtype=int)
    show_text = cfg.get(logbook.name, "Show text", valtype=bool)
    if show_text and summary_lines > 0:
        col_names.append(
            _("Text")
        )  # XX even if text not shown, should still be in filters below
        col_fields.append("text")
    columns = dict(zip(col_names, col_fields))

    col_names_lower = [x.lower() for x in col_names] + ["subtext"]
    # XX could also be in columns not shown in display
    filters = {
        k: v
        for k, v in request.GET.items()
        if k.lower() in col_names_lower and k.lower() != "id" and v != ""
    }
    # need to handle 'subtext' used in original psi elog query string
    if "subtext" in filters:
        filters["text"] = filters.pop("subtext")

    filter_attrs = {  # actually text and attrs
        f"{'attrs__' if k.lower() in attrs_lower else ''}{k.lower()}": v
        for k, v in filters.items()
    }

    # Some db backends (e.g. sqlite, oracle?) do not do case sensitive on unicode,
    # and/or on JSONFields.  So do case insensitive and filter entires in code below
    filter_fields = {f"{k}__icontains": v for k, v in filter_attrs.items()}

    # XX Need to exclude date, id from 'contains'-style search, translate back

    # Determine sort order of entries
    # Default is by date
    # Check if query args have sort specified
    if sort_attr_field := columns.get(get_param(request, "sort")):
        is_rsort = False
    elif sort_attr_field := columns.get(get_param(request, "rsort")):
        is_rsort = True
    else:
        is_rsort = cfg.get(logbook.name, "Reverse sort")
        sort_attr_field = columns[_("Date")]

    # try:
    order_by = Lower(sort_attr_field).desc() if is_rsort else Lower(sort_attr_field)
    qs = (
        logbook.entry_set.values(*columns.values())
        .filter(**filter_fields)
        .order_by(order_by)
    )

    # 'Manually' filter attrs if case sensitive search
    if get_param(request, "casesensitive", valtype=bool):
        filter_qs_case_sensitive(qs, filter_fields)

    # except FieldError:
    #     qs = logbook.entry_set.values(*columns.values()).order_by("-date")

    # Get page requested with "?page=#" or ?page=all else 1
    req_page_number = get_param(request, "page", default="1")
    if req_page_number.lower() == "all":
        req_page_number = 1
        per_page = qs.count() + 1
    else:
        per_page = get_param(request, "npp", valtype=int) or cfg.get(
            logbook.name, "entries per page"
        )

    paginator = Paginator(qs, per_page=per_page)
    # If query string has "id=#", then need to position to page with that id
    # ... assuming it exists.  Check that first. If not, then ignore the setting
    page_obj = paginator.get_page(req_page_number)
    if selected_id and logbook.entry_set.filter(id=selected_id):
        # go through each page to find one with the id.
        # XX  Might be a faster way for very large logbooks
        for page_obj in paginator:
            if selected_id in page_obj.object_list.values_list("id", flat=True):
                break
        else:  # shouldn't be necessary since checked it exists already...
            page_obj = paginator.get_page(req_page_number)

    num_pages = paginator.num_pages
    if num_pages > 1:
        page_n_of_N = _("Page {num:d} of {count:d}").format(
            num=page_obj.number, count=num_pages
        )
    else:
        page_n_of_N = None

    context = {
        "logbook": logbook,
        "logbooks": Logbook.objects.all(),  # XX will need to restrict to what user auth is
        "commands": commands,
        "modes": modes,
        "current_mode": current_mode,
        "columns": columns,
        "page_obj": page_obj,
        "page_range": list(
            paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=3)
        ),
        "page_n_of_N": page_n_of_N,
        "selected_id": selected_id,
        "summary_lines": summary_lines,
        "main_tab": cfg.get(logbook.name, "main tab", valtype=str, default=""),
        "cfg_css": cfg.get(logbook.name, "css", valtype=str, default=""),
        "sort_attr_field": sort_attr_field,
        "is_rsort": is_rsort,
        "filters": filters,
        "filter_attrs": filter_attrs,
    }
    return render(request, "flexelog/entry_list.html", context)


def new_edit_get(request, logbook, command, entry):
    # XXXX check request.user permissions for each of these, for the logbook

    if command == _("New"):
        entry = Entry(lb=logbook)
        page_type = "New"
    if command == _("Edit"):
        # XXX last_mod_author  = <current user>, original author stays
        page_type = "Edit"
    else:  # _("Reply"), _("Duplicate")
        entry = copy(entry)
        entry.pk = None
        entry.id = None
        entry.reply_to = None
        # XXXX entry.author = <current user>
        page_type = "Duplicate"
        if command == _("Reply"):
            page_type = "Reply"
            entry.reply_to = entry.id
            entry.text = (
                f"\n{_('Quote')}:\n"
                + textwrap.indent(entry.text or "", "> ", lambda _: True)
                + "\n"
            )

    if command != _("Edit"):
        entry.date = timezone.now()
        # XXX update last modified date

    if command == _("New"):
        cfg = get_config()
        form = EntryForm(
            lb_attrs=cfg.lb_attrs[logbook.name],
            initial={"date": timezone.now()},
        )
    else:
        form = EntryForm.from_entry(entry, page_type)

    context = {
        "entry": entry,
        "logbook": logbook,
        "logbooks": Logbook.objects.all(),
        "commands": [],
    }
    context.update(form.get_context())
    return render(request, "flexelog/edit.html", context)


def entry_detail_post(request, logbook: Logbook, entry: Entry):
    """POST method for "<str:lb_name>/<int:entry_id>/"""
    cmd = request.POST.get("cmd")
    url_detail = reverse("flexelog:entry_detail", args=[logbook.name, entry.id])
    if cmd == "Delete":  # hidden field from POSTed Confirmation form
        if request.POST.get("confirm") != _("Yes"):
            return redirect(url_detail)

        entry.delete()

        # Find new entry to redirect to ... next higher available number or the last entry
        next_entry = logbook.entry_set.filter(id__gt=entry.id).order_by("id").first()
        if not next_entry:
            next_entry = logbook.entry_set.order_by("-id").first()  # max id entry
            if not next_entry:  # no entries at all, go to logbook main listing:
                return redirect(reverse("flexelog:logbook", args=[logbook.name]))

        return redirect(
            reverse("flexelog:entry_detail", args=[logbook.name, next_entry.id])
        )

    # XXX else?
    return redirect(url_detail)


# ---------------------
# view for route "<str:lb_name>/<int:entry_id>/" and ?cmd={Delete, Find, Edit, etc.}
def entry_detail(request, lb_name, entry_id):
    lb_name = unquote_plus(lb_name)
    try:
        logbook = Logbook.objects.get(name=lb_name)
    except Logbook.DoesNotExist:
        # 'Logbook "%s" does not exist on remote server'
        raise  # XXX
    entry = get_object_or_404(Entry, lb=logbook, id=entry_id)

    if request.method == "POST":
        return entry_detail_post(request, logbook, entry)

    return entry_detail_get(request, logbook, entry)


def entry_detail_get(request, logbook, entry):
    command = get_param(request, "cmd")
    # Delete starts with GET request, confirmation form does POST
    if command == _("Delete"):
        context = dict(
            title=_("Delete"),
            method="POST",
            action=f".",
            cmd="Delete",
            prompt=_("Are you sure to delete this entry?"),
            message = f"#{entry.id}",
            true_label = _("Yes"),
            false_label = _("No"),
        )
        return render(request, "flexelog/confirmation.html", context)
    
    elif command in (_("New"), _("Edit"), _("Reply"), _("Duplicate")):
        return new_edit_get(request, logbook, command, entry)
    
    cfg = get_config()
    # XXX need to take commands from config file, not just default
    command_names = [
        _("List"),
        _("New"),
        _("Edit"),
        _("Delete"),
        _("Reply"),
        _("Duplicate"),
        # _("Find"),
        # _("Config"),
        # _("Help"),
    ]
    url_detail = reverse("flexelog:entry_detail", args=[logbook.name, entry.id])
    commands = [(cmd, f"{url_detail}?cmd={cmd}") for cmd in command_names]
    commands[0] = (
        _("List"),
        reverse("flexelog:logbook", args=[logbook.name]) + f"?id={entry.id}",
    )

    command = get_param(request, "cmd")
    if command:
        if command not in command_names:
            context = {"message": _('Error: Command "<b>%s</b>" not allowed') % command}
            return render(request, "flexelog/show_error.html", context)
            # if command not in command_dispatch:
            #     return show_error(
            #         _('Error: Command "<b>%s</b>" not allowed') % command
            #         + " (not currently implemented)"
            #     )

    context = {
        "entry": entry,
        "logbook": logbook,
        "logbooks": Logbook.objects.all(),
        "commands": commands,
    }
    # If get here, then are just doing the detail view, no editing
    form = EntryViewerForm(data={"text": entry.text or ""})
    context["form"] = form
    return render(request, "flexelog/entry_detail.html", context)


def test(request, lb_name, entry_id):
    cfg = get_config()
    try:
        logbook = Logbook.objects.get(name=lb_name)
    except Logbook.DoesNotExist:
        # 'Logbook "%s" does not exist on remote server'
        raise  # XXX
    entry = get_object_or_404(Entry, lb=logbook, id=entry_id)
    lb_attributes = cfg.lb_attrs[logbook.name]
    attr_names = entry.attrs.keys()
    # Error: translate: "Attribute <b>%s</b> not supplied" for required

    # form = EntryForm(instance=entry, initial={"date": timezone.now()})  # instance=entry for edit existing
    initial = {"date": timezone.now()}
    form = EntryForm(lb_attrs=lb_attributes, initial=initial)
    context = form.get_context()
    context.update(
        {
            "logbook": logbook,
            "logbooks": Logbook.objects.all(),  # XX will need to restrict to what user auth is, not show deactivated ones
            "main_tab": cfg.get(logbook.name, "main tab", valtype=str, default=""),
            "cfg_css": cfg.get(logbook.name, "css", valtype=str, default=""),
        }
    )
    return render(request, "flexelog/edit.html", context)
