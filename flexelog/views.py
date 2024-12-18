from django.shortcuts import render, get_object_or_404

# Create your views here.
from .models import logbook_names, Entry
from django.http import HttpResponse

class Logbook:
    def __init__(self, name, comment):
        self.name = name
        self.comment = comment


def index(request):

    logbooks = [
        Logbook(lb, f"Comment for {lb}")
        for lb in logbook_names()
    ]
    context = {
        "logbooks": logbooks
    }

    return render(request, "flexelog/index.html", context)


def detail(request, lb, entry_id):
    entry = get_object_or_404(Entry, lb=lb, id=entry_id)

    return render(request, "flexelog/detail.html", {"entry": entry})

