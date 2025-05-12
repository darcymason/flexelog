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

from .forms import EntryForm
from .models import Logbook, Entry
from .elog_cfg import get_config

from htmlobj import HTML
from urllib.parse import unquote_plus, urlencode


def get_param(request, key: str, *, valtype: type = str, default: Any = None) -> Any:
    """Return the GET query value for key, but default if not found or not of right type"""
    val = request.GET.get(key, default)
    if val is not default:
        try:
            val = valtype(val)
        except ValueError:
            val = default
    return val

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
        "cfg_css": cfg.get("global", "css", valtype=str, default=""), # XXX admin forces global since lb can't exist
    }
    return render(request, "flexelog/index.html", context)



def _new_reply_edit_delete(request, lb_name, logbook):
    if request.POST.get("cmd") == "Submit":
        page_type = request.POST["page_type"]
        attr_names = request.POST["attr_names"].split(",")
        attrs = {attr_name: request.POST[attr_name] for attr_name in attr_names}
        if page_type == "Edit":
            entry = Entry.objects.get(lb=logbook, id=request.POST["edit_id"])
            is_new_entry = False
        else:  # New/Reply
            entry = Entry()
            is_new_entry = True
        # Fill in edit object
        entry.attrs = attrs
        entry.text = request.POST["editor_markdown"]
        if page_type in ("New", "Reply"):
            entry.date = request.POST["date"]
            # Find max id for this logbook and add 1
            # XXX is this thread-safe?  Trap exists error and try again 1 higher
            entry.id = Entry.objects.filter(lb__name=lb_name).order_by("-id").first() + 1
        entry.save(force_insert=is_new_entry)
        redirect_url = reverse("flexelog:entry_detail", args=[lb_name, entry.id])
        return redirect(redirect_url)
    # XXX need to cover other cases?

def logbook_or_new_edit_delete_post(request, lb_name):
    # if not request.user.is_authenticated:
    #     return redirect(f"{settings.LOGIN_URL}?next={request.path}")
    cfg = get_config()
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
        return _new_reply_edit_delete(request, lb_name, logbook)

    # New dealing with GET, listing logbook entries
    selected_id = get_param(request, "id", valtype=int)

    # XX Adjust available commands according to config
    # XX then according to user auth
    # XX Select command not implemented
    command_names = [
        _("New"),
        _("Find"),
        _("Import"),
        _("Config"),
        _("Last day"),
        _("Help"),
    ]
    lb_url = reverse("flexelog:logbook", args=[lb_name])
    commands = [(cmd, f"{lb_url}?cmd={cmd}") for cmd in command_names]
    commands[4] = (_("Last day"), f"{lb_url}past1?mode=Summary")

    modes = (  # First text is translated, url param is not
        (_("Full"), "?mode=full"),
        (_("Summary"), "?mode=summary"),
        (_("Threaded"), "?mode=threaded"),
    )
    current_mode = _(get_param(request, "mode", default="Summary").capitalize())

    attrs = list(cfg.lb_attrs[logbook.name].keys())  # XX can also config Attributes shown
    attrs_lower = [attr.lower() for attr in attrs]
    # XX col order could be changed in config
    col_names = [_("ID"), _("Date")] + attrs 
    col_fields = ["id", "date"] + [f"attrs__{attr.lower()}" for attr in attrs]
    # Add Text column if config'd to do so
    summary_lines = cfg.get(lb_name, "Summary lines", valtype=int)
    show_text = cfg.get(lb_name, "Show text", valtype=bool)
    if show_text and summary_lines > 0:
        col_names.append(_("Text"))
        col_fields.append("text")
    columns = dict(zip(col_names, col_fields))    

    col_names_lower = [x.lower() for x in col_names]
    # XX could also be in columns not shown in display
    filters = {
        k: v
        for k, v in request.GET.items()
        if k.lower() in col_names_lower and k.lower() != "id"
    }

    filter_attrs = {
        f"{'attrs__' if k.lower() in attrs_lower else ''}{k.lower()}": v
        for k, v in filters.items()
    }
    filter_fields = {
        f"{k}__icontains": v
        for k, v in filter_attrs.items()
    }
    # XX need to handle 'subtext' used in original psi elog
    # XX Need to exclude date, id from 'contains'-style search, translate back
    
    # determine sort order of entries
    # default is by date
    # check if query args have sort specified
    if sort_attr_field := columns.get(get_param(request, "sort")):
        is_rsort = False
    elif sort_attr_field := columns.get(get_param(request, "rsort")):
        is_rsort = True
    else:
        is_rsort = cfg.get(lb_name, "Reverse sort")
        sort_attr_field = columns[_("Date")]

    # try:
    order_by = Lower(sort_attr_field).desc() if is_rsort else Lower(sort_attr_field)
    entries = logbook.entry_set.values(*columns.values()).filter(**filter_fields).order_by(order_by)

    # except FieldError:
    #     entries = logbook.entry_set.values(*columns.values()).order_by("-date")

    # Get page requested with "?page=#" or ?page=all else 1
    req_page_number = get_param(request, "page", default="1")
    if req_page_number.lower() == "all":
        req_page_number = 1
        per_page = entries.count() + 1
    else:
        per_page = get_param(request, "npp", valtype=int) or cfg.get(lb_name, "entries per page")

    paginator = Paginator(entries, per_page=per_page)
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
        page_n_of_N = _("Page {num:d} of {count:d}").format(num=page_obj.number, count=num_pages)
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
        "page_range": list(paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=3)),
        "page_n_of_N": page_n_of_N,
        "selected_id": selected_id,
        "summary_lines": summary_lines,
        "main_tab": cfg.get(lb_name, "main tab", valtype=str,default=""),
        "cfg_css": cfg.get(lb_name, "css", valtype=str, default=""),
        "sort_attr_field": sort_attr_field,
        "is_rsort": is_rsort,
        "filters": filters,
        "filter_attrs": filter_attrs,
    }
    return render(request, "flexelog/entry_list.html", context)


def entry_detail(request, lb_name, entry_id):
    # Commands
    # XXX need to take from config file, not just default
    cfg = get_config()
    lb_name = unquote_plus(lb_name)
    command_names = [
        _("List"),
        # _("New"),
        _("Edit"),
        # _("Delete"),
        _("Reply"),
        #_("Duplicate"),
        # _("Find"),
        # _("Config"),
        # _("Help"),
    ]
    url_detail = reverse("flexelog:entry_detail", args=[lb_name, entry_id])
    commands = [(cmd, f"{url_detail}?cmd={cmd}") for cmd in command_names]
    commands[0] = (_("List"), reverse("flexelog:logbook", args=[lb_name]) + f"?id={entry_id}")

    command = get_param(request, "cmd")
    if command:
        if command not in command_names:
            context = {"message": _('Error: Command "<b>%s</b>" not allowed')}
            return render(request, "flexelog/show_error.html", context)
            # if command not in command_dispatch:
            #     return show_error(
            #         _('Error: Command "<b>%s</b>" not allowed') % command
            #         + " (not currently implemented)"
            #     )

    try:
        logbook = Logbook.objects.get(name=lb_name)
    except Logbook.DoesNotExist:
        # 'Logbook "%s" does not exist on remote server'
        raise  # XXX
    entry = get_object_or_404(Entry, lb=logbook, id=entry_id)
    context = {
        "entry": entry,
        "logbook": logbook,
        "logbooks": Logbook.objects.all(),
        "commands": commands,
    }
    if command == _("Edit"):
        context["page_type"] = "Edit"
        return render(request, "flexelog/edit.html", context)
    if command == _("New"):
        entry = Entry()
        entry.attrs = cfg.lb_attrs[lb_name]
    if command == _("Reply"):
        context["page_type"] = "Reply"
        new_entry = copy(entry)
        # XXX copy attrs, or blank them?
        new_entry.id = None
        new_entry.date = timezone.now()
        new_entry.reply_to = entry.id
        new_entry.text = (
            f"\n{_('Quote')}:\n"
            + textwrap.indent(entry.text, "> ", lambda _: True)
            + "\n"
        )
        context["entry"] = new_entry
        return render(request, "flexelog/edit.html", context)
    return render(request, "flexelog/entry_detail.html", context)

def test(request, lb_name, entry_id):
    cfg = get_config()
    try:
        logbook = Logbook.objects.get(name=lb_name)
    except Logbook.DoesNotExist:
        # 'Logbook "%s" does not exist on remote server'
        raise  # XXX
    entry = get_object_or_404(Entry, lb=logbook, id=entry_id)
    lb_attributes = cfg.lb_attrs[lb_name]
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
            "main_tab": cfg.get(lb_name, "main tab", valtype=str,default=""),
            "cfg_css": cfg.get(lb_name, "css", valtype=str, default=""),
        }
    )
    return render(request, "flexelog/edit.html", context)