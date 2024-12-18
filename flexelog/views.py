from django.shortcuts import render

# Create your views here.
from .models import logbook_names
from django.http import HttpResponse


def index(request):
    return HttpResponse(str(logbook_names()))