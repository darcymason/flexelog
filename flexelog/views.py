from copy import copy
import logging
from typing import Any
from django.shortcuts import render, get_object_or_404
from django.utils.translation import gettext_lazy as _

# Create your views here.

from django.http import HttpResponse, QueryDict
from django.core.paginator import Paginator
from .models import Logbook, Entry
from .elog_cfg import get_config

from htmlobj import HTML
from urllib.parse import urlencode


def paging_offered(page_num: int, page_count: int) -> list[int | None]:
    """List the pages offered for top/bottom of listing page

    List will have None where an ellipsis is needed
    e.g. if 15 pages, page_num is 6, then return
        [1, 2, 3, None, 5, 6, 7, None, 13, 14, 15]

    """

    if page_count == 1:
        return []
    if page_count <= 7:
        return list(range(1, page_count + 1))
    s = set((1, 2, 3))
    s.update((max(page_num - 1, 1), page_num, min(page_num + 1, page_count)))
    s.update((page_count - 2, page_count - 1, page_count))
    li = sorted(s)
    for i, val in enumerate(li):
        if i < 3:
            continue
        if (prev := li[i - 1]) is not None and val != prev + 1:
            li.insert(i, None)
    return li


def pagination_html(
    page_num: int | None, page_count: int, query_dict: QueryDict = None
) -> str:
    if page_num is None:
        page_num = 1

    pages = paging_offered(page_num, page_count)
    pages_len = len(pages)
    if pages_len < 2:
        return "\n"
    if query_dict is None:
        query_dict = QueryDict()
    query_args = copy(query_dict)

    h = HTML()
    with h.td(class_="menuframe"):
        with h.span(class_="menu3"):
            h.text(_("Goto page"))
            # Add Previous if not first page
            if page_num != 1:
                query_args["page"] = page_num - 1
                h.a(
                    _("Previous"),
                    href=f"?{query_args.urlencode(safe="&")}",
                )
                h.raw_text("&nbsp;&nbsp;")
            for i, pg in enumerate(pages):
                comma = "," if i != pages_len - 1 and pages[i + 1] is not None else ""
                if pg is None:
                    h.raw_text("&nbsp;...&nbsp;")
                elif pg is page_num:
                    h.raw_text(str(pg) + comma)
                else:
                    query_args["page"] = pg
                    h.a(str(pg) + comma, href=f"?{query_args.urlencode(safe="&")}")

            # Add Next if not on last page
            if page_num != page_count:
                h.raw_text("&nbsp;&nbsp;")
                query_args["page"] = page_num + 1
                h.a(_("Next"), href=f"?{query_args.urlencode(safe="&")}")

            # Add All option
            # XX need to check config file for max limit to offer this
            h.raw_text("&nbsp;&nbsp;")
            query_args["page"] = "all"
            query_args.pop("npp", None)
            h.a(_("All"), href=f"?{query_args.urlencode(safe="&")}")
    return str(h)


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
    except Logbook.DoesNotExist:
        context = {
            "message": _('Logbook "%s" does not exist on remote server') % lb_name
        }
        return render(request, "flexelog/show_error.html", context)

    selected_id = get_param(request, "id", valtype=int)
    query_dict = request.GET
    query_id = f"?id={selected_id}&amp;" if selected_id else ""

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

    modes = (  # First text is translated url param is not
        # XX need to carry over other url params
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
    
    page_number = request.GET.get("page") or "1"
    if page_number.lower() == "all":
        page_number = 1
        per_page = entries.count() + 1
    else:
        per_page = get_param(request, "npp", valtype=int) or cfg.get(lb_name, "entries per page")

    

    paginator = Paginator(entries, per_page=per_page)
    page_obj = paginator.get_page(page_number)
    num_pages = page_obj.paginator.num_pages 
    if num_pages > 1:
        page_n_of_N = _("Page %d of %d") % (page_obj.number, num_pages)
    else:
        page_n_of_N = None
    
    paging_html = pagination_html(page_obj.number, num_pages, query_dict)

    # rows = [
    #     entry.attrs[key]
    #     for key in headers
    #     for entry in entries
    # ]

    context = {
        "logbook": logbook,
        "logbooks": Logbook.objects.all(),
        "commands": commands,
        "modes": modes,
        "current_mode": current_mode,
        "col_names": col_names,
        "page_obj": page_obj,
        "paging_html": paging_html,
        "page_n_of_N": page_n_of_N,
        # "rows": rows,
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
