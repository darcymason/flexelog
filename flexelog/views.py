from copy import copy
import logging
from typing import Any
from django.shortcuts import render, get_object_or_404
from django.utils.translation import gettext_lazy as _

# Create your views here.

from django.http import HttpResponse, QueryDict
from django.core.paginator import Paginator, Page
from .models import Logbook, Entry
from .elog_cfg import get_config

from htmlobj import HTML
from urllib.parse import urlencode


def get_param(request, key: str, *, valtype: type = str, default: Any = None) -> Any:
    """Return the GET query value for key, but default if not found or not of right type"""
    val = request.GET.get(key, default)
    if val is not default:
        try:
            val = valtype(val)
        except ValueError:
            val = default
    return val


def index(request):
    cfg = get_config()
    logbooks = [lb for lb in Logbook.objects.all() if lb.name in cfg.logbook_names()]

    context = {
        "cfg": cfg,
        "logbooks": logbooks,
        "heading": "FlexElog Logbook Selection",
    }
    return render(request, "flexelog/index.html", context)


def logbook(request, lb_name):
    cfg = get_config()
    try:
        logbook = Logbook.objects.get(name=lb_name)
    except Logbook.DoesNotExist:
        context = {
            "message": _('Logbook "%s" does not exist on remote server') % lb_name
        }
        return render(request, "flexelog/show_error.html", context)

    selected_id = get_param(request, "id", valtype=int)
    query_dict = request.GET

    # XX Adjust available commands according to config
    # XX Select command not implemented
    command_names = [
        _("New"),
        _("Find"),
        _("Import"),
        _("Config"),
        _("Last day"),
        _("Help"),
    ]
    commands = [(cmd, f"?cmd={cmd}") for cmd in command_names]
    commands[4] = (_("Last day"), "past1?mode=Summary")

    modes = (  # First text is translated, url param is not
        (_("Full"), "?mode=full"),
        (_("Summary"), "?mode=summary"),
        (_("Threaded"), "?mode=threaded"),
    )
    current_mode = _(get_param(request, "mode", default="Summary").capitalize())

    attrs = list(cfg.lb_attrs[logbook.name].keys())
    col_names = ["ID", "Date"] + attrs + ["Text"]
    attr_args = (f"attrs__{attr}" for attr in attrs)
    entries = logbook.entry_set.values("id", "date", *attr_args, "text").order_by(
        "-date"
    )  # XX need to allow different orders
    
    # Get page requested with "?id=#" in url, used when click "List" from detail page
    req_page_number = request.GET.get("page") or "1"
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
        page_n_of_N = _("Page %d of %d") % (page_obj.number, num_pages)
    else:
        page_n_of_N = None
    
    context = {
        "logbook": logbook,
        "logbooks": Logbook.objects.all(),
        "commands": commands,
        "modes": modes,
        "current_mode": current_mode,
        "col_names": col_names,
        "page_obj": page_obj,
        "page_range": list(paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=3)),
        "page_n_of_N": page_n_of_N,
        "selected_id": selected_id,
    }
    return render(request, "flexelog/entry_list.html", context)


def detail(request, lb_name, entry_id):
    # Commands
    # XXX need to take from config file, not just default
    # New |  Find |  Select |  Import |  Config |  Last day |  Help
    # Make assuming standard url, fix after for those that differ
    # XX _("Select") (multi-select editing) not offered currently
    command_names = [
        _("New"),
        _("Find"),
        _("Import"),
        _("Config"),
        _("Last day"),
        _("Help"),
    ]
    commands = [(cmd, f"?cmd={cmd}") for cmd in command_names]

    # commands[2] = (_("Select"), query_id + "?select=1")
    commands[4] = (_("Last day"), "past1?mode=Summary")

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
    except Entry.DoesNotExist:
        # 'Logbook "%s" does not exist on remote server'
        raise  # XXX
    entry = get_object_or_404(Entry, lb=logbook, id=entry_id)
    context = {
        "entry": entry,
        "logbook": logbook,
        "logbooks": Logbook.objects.all(),
    }
    return render(request, "flexelog/detail.html", context)
