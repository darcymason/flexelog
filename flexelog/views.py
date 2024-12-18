from django.shortcuts import render

# Create your views here.
from .models import logbook_names
from django.http import HttpResponse



def index(request):
    context = {
        "lb_list": logbook_names()
    }
    return render(request, "flexelog/index.html", context)


def detail(request, entry_id):
    return HttpResponse(f"You're looking at entry {entry_id}")

