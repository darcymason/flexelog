import logging
from typing import Any
from django.shortcuts import render, get_object_or_404
from django.utils.translation import gettext as _

# Create your views here.

from django.http import HttpResponse
from .models import Logbook, Entry
from .elog_cfg import get_config


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
    logbooks = [
            lb for lb in Logbook.objects.all() if lb.name in cfg.logbook_names()
        ]
    
    instruct1 = _("Several logbooks are defined on this host")
    instruct2 = _("Please select the one to connect to")
    logging.warning(logbooks[0].latest_date())
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
    except Entry.DoesNotExist:
        context = {"message": _('Logbook "%s" does not exist on remote server')}
        return render(request, "flexelog/show_error.html", context)
    
    selected_id = get_param(request, "id", valtype=int)
    query_id = f"?id={selected_id}&amp;" if selected_id else ""
    
    # XX Adjust available commands according to config
    # XX Select command not implemented
    command_names = [_("New"), _("Find"), _("Import"), _("Config"), _("Last day"), _("Help") ]
    commands = [(cmd, f"?cmd={cmd}") for cmd in command_names]
    commands[4] = (_("Last day"), "past1?mode=Summary")

    modes = (  # First text is translated url param is not
        # XX need to carry over other url params
        (_("Full"), "?mode=full"), 
        (_("Summary"), "?mode=summary"),
        (_("Threaded"), "?mode=threaded"),
    )
    current_mode = _(get_param(request, "mode", default="Summary").capitalize())

    entries = logbook.entry_set.all()
    headers = cfg.lb_attrs[logbook.name]
    # rows = [
    #     entry.attrs[key]
    #     for key in headers
    #     for entry in entries
    # ]

    context = {
        "logbook": logbook,
        "logbooks": Logbook.objects.all(),
        "headers": headers,
        "commands": commands,
        "modes": modes,
        "current_mode": current_mode,
        # "rows": rows,
    }
    return render(request, "flexelog/entry_list.html", context)


def detail(request, lb_name, entry_id):
    # Commands
    # XXX need to take from config file, not just default
    # New |  Find |  Select |  Import |  Config |  Last day |  Help
    # Make assuming standard url, fix after for those that differ
    # XX _("Select") (multi-select editing) not offered currently
    command_names = [_("New"), _("Find"), _("Import"), _("Config"), _("Last day"), _("Help") ]
    commands = [(cmd, f"?cmd={cmd}") for cmd in command_names]

    # commands[2] = (_("Select"), query_id + "?select=1")
    commands[4] = (_("Last day"), "past1?mode=Summary")

    command = get_param(request, "cmd")
    if command:
        if command not in command_names:
            context = {
                "message": _('Error: Command "<b>%s</b>" not allowed')
            }
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

    