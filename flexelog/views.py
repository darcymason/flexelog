from copy import copy
import logging
from typing import Any
from django.conf import settings
from django.shortcuts import redirect, render, get_object_or_404
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
# Create your views here.
from django.db.models.functions import Lower
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


def logbook(request, lb_name):
    # XX Config to port over from PSI elog settings:
    # Main Tab = <string> -- extra tab to go back to logbook selection page
    #  ... and Main Tab URL = <string> to go to a different page instead
    if not request.user.is_authenticated:
        return redirect(f"{settings.LOGIN_URL}?next={request.path}")
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
    commands = [(cmd, f"?cmd={cmd}") for cmd in command_names]
    commands[4] = (_("Last day"), "past1?mode=Summary")

    modes = (  # First text is translated, url param is not
        (_("Full"), "?mode=full"),
        (_("Summary"), "?mode=summary"),
        (_("Threaded"), "?mode=threaded"),
    )
    current_mode = _(get_param(request, "mode", default="Summary").capitalize())

    attrs = list(cfg.lb_attrs[logbook.name].keys())  # XX can also config Attributes shown
    col_names = ["ID", "Date"] + attrs 
    
    attr_args = (f"attrs__{attr}" for attr in attrs)
    summary_lines = cfg.get(lb_name, "Summary lines", valtype=int)
    show_text = cfg.get(lb_name, "Show text", valtype=bool)
    if show_text and summary_lines > 0:
        col_names.append("Text")
        text_arg = ["text"]
    else:
        text_arg = []
    
    # determine sort order of entries
    # default is by date
    # check if query args have sort specified
    if sort_attr := request.GET.get("rsort"):
        is_rsort = True
    elif sort_attr := request.GET.get("sort"):
        is_rsort = False
    else:
        is_rsort = cfg.get(lb_name, "Reverse sort")
        sort_attr = "date"

    if sort_attr in attrs:
        sort_attr = f"attrs__{sort_attr}"
    order_by = -Lower(sort_attr) if is_rsort else Lower(sort_attr)
    entries = logbook.entry_set.values("id", "date", *attr_args, *text_arg).order_by(
        order_by)
    
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
        page_n_of_N = _("Page {num:d} of {count:d}").format(num=page_obj.number, count=num_pages)
    else:
        page_n_of_N = None
    
    context = {
        "logbook": logbook,
        "logbooks": Logbook.objects.all(),  # XX will need to restrict to what user auth is
        "commands": commands,
        "modes": modes,
        "current_mode": current_mode,
        "col_names": col_names,
        "page_obj": page_obj,
        "page_range": list(paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=3)),
        "page_n_of_N": page_n_of_N,
        "selected_id": selected_id,
        "summary_lines": summary_lines,
        "main_tab": cfg.get(lb_name, "main tab", valtype=str,default=""),
        "cfg_css": cfg.get(lb_name, "css", valtype=str, default=""),
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
