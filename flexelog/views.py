import logging
from django.shortcuts import render, get_object_or_404
from django.utils.translation import gettext as _

# Create your views here.

from django.http import HttpResponse
from .models import Logbook, Entry
from .elog_cfg import get_config


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

    entries = logbook.entry_set.all()
    headers = logbook.attrs.keys()
    rows = [
        entry.attrs[key]
        for key in headers
        for entry in entries
    ]

    context = {
        "logbook": logbook,
        "logbooks": Logbook.objects.all(),
        "headers": headers,
        "rows": rows,
    }
    return render(request, "flexelog/entry_list.html", context)

def detail(request, lb_name, entry_id):
    # Commands
    # XXX need to take from config file, not just default
    # New |  Find |  Select |  Import |  Config |  Last day |  Help
    # Make assuming standard url, fix after for those that differ
    command_names = [_("New"), _("Find"), _("Select"), _("Import"), _("Config"), _("Last day"), _("Help") ]
    # Translate command names
    commands = [(cmd, f"?cmd={cmd}") for cmd in command_names]
    query_id = f"?id={selected_id}&amp;" if selected_id else ""
    commands[2] = (_("Select"), query_id + "?select=1")
    commands[5] = (_("Last day"), "past1?mode=Summary")

    command = request.get("cmd")
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

    