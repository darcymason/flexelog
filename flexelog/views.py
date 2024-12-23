import logging
from django.shortcuts import render, get_object_or_404

# Create your views here.

from django.http import HttpResponse
from .models import Logbook, Entry
from .elog_cfg import get_config


def index(request):
    cfg = get_config()
    logbooks = [
            lb for lb in Logbook.objects.all() if lb.name in cfg.logbook_names()
        ]
    logging.warning(logbooks[0].latest_date())
    context = {
        "cfg": cfg,
        "logbooks": logbooks,
    }
    return render(request, "flexelog/index.html", context)

def logbook(request, lb_name):
    try:
        logbook = Logbook.objects.get(name=lb_name)
    except Entry.DoesNotExist:
        # 'Logbook "%s" does not exist on remote server'
        raise  # XXX

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

    