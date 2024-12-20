from django.shortcuts import render, get_object_or_404

# Create your views here.
from .models import Logbook, Entry
from django.http import HttpResponse


def index(request):

    context = {
        "logbooks": Logbook.objects.all()
    }

    return render(request, "flexelog/index.html", context)

def logbook(request, lb_name):
    try:
        logbook = Logbook.objects.get(name=lb_name)
    except Entry.DoesNotExist:
        # 'Logbook "%s" does not exist on remote server'
        raise  # XXX
    return render(request, "flexelog/entry_list.html", {"logbook": logbook})

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
    }
    return render(request, "flexelog/detail.html", context)

    