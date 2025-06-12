from copy import copy
from datetime import datetime
import logging
from operator import itemgetter
import operator
import textwrap
from typing import Any
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.core.paginator import Paginator, Page
from django.db.models.functions import Lower
from django.db.models import Count
from django.http import HttpResponse, QueryDict
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from flexelog.forms import EntryForm, EntryViewerForm, SearchForm
from guardian.shortcuts import get_perms

from .models import Logbook, LogbookGroup, Entry
from .elog_cfg import get_config

from urllib.parse import unquote_plus

from flexelog.editor.widgets_toastui import MarkdownViewerWidget

def available_logbooks(request) -> list[Logbook]:
    return [
        lb
        for lb in Logbook.objects.filter(active=True).order_by("order")
        if not lb.auth_required
        or (request.user.is_authenticated and request.user.has_perm("view_entries", lb))
        or (not request.user.is_authenticated and not lb.is_unlisted)
    ]


def available_groups(logbooks: list[Logbook]):
    """Return dict of {group name: logbooks for that group}, group name is None if logbook in no groups"""
    groups = {}
    for group in LogbookGroup.objects.all():
        group_logbooks = [lb for lb in group.logbooks.all() if lb in logbooks]
        if group_logbooks:  # don't store it if has no logbooks in the group
            groups[group.name] = group_logbooks

    unassigned = [lb for lb in logbooks if not lb.logbookgroup_set.count()]
    if unassigned:
        groups[None] = unassigned
    return groups


def command_perm_response(request, command, commands, logbook, entry=None) -> HttpResponse | None:
    """Return an error message if the user is not allowed to <cmd> with this entry, else None"""
    # Note `entry`` only matters when editing/deleting one's own entries vs another author
    # If logbook does not require auth - anyone can do anything, 
    # except perhaps delete/edit after time period 
    def err(msg):
        return render(request, "flexelog/show_error.html", {"message": msg})

    def err_command(extra=""):
        msg = _('Error: Command "<b>%s</b>" not allowed') % command
        return err(msg + extra)

    def err_command_user():
        msg = _('Error: Command "<b>{command}</b>" is not allowed for user "<b>{user}</b>"').format(
                command=command,
                user = request.user.get_username()
        )
        return err(msg)

    # XX note - could possibly restrict defaults for no-auth logbook
    #   e.g. not allow deleting entries (but can use time restriction for that)

    if logbook.auth_required and not request.user.is_authenticated:
        return redirect(f"{settings.LOGIN_URL}?next={request.path}")

    perms = get_perms(request.user, logbook) if logbook.auth_required else [p[0] for p in logbook._meta.permissions]

    # If logbook is unlisted, then should look like doesn't exist to those without permissions
    if logbook.is_unlisted and not perms:
        return err(_('Logbook "%s" does not exist on remote server') % logbook.name)
    
    # Just viewing:
    if (not command or command == _("Find")):
        if 'view_entries' in perms:
            return None
        else:
            # From django admin translations
            msg = _(
                "You are authenticated as %(username)s, but are not authorized to access this "
                "page. Would you like to login to a different account?"
            ) % dict(username=request.user.get_username())
            # XX offer link to logout or login as other person  
            # logout_url =  reverse("flexelog:do_logout")
            # link = f'<a href="{logout_url}>{_("Logout")}</a>'
            return err(msg)  

    # if read-only logbook, cannot do anything other than viewing-type commands
    if logbook.readonly:
        extra = "nbsp;nbsp;" + _('Logbook "%s" is read-only') % logbook.name
        return err_command(extra)
 
    if command not in commands:
        return err_command()

    if command in (_("New"), _("Reply"), _("Duplicate")) and "add_entries" in perms:
        return None
    
    # Only 'edit' and 'delete' left, check user permissions first
    can_edit = 'edit_own_entries' in perms or 'edit_others_entries' in perms
    can_delete = 'delete_own_entries' in perms or 'delete_others_entries' in perms
    if (command == _("Edit") and not can_edit) or (command == _("Delete") and not can_delete):
        return err_command_user()
    
    # Now need to check entry vs author
    if entry is None:
        return None  # will have to deal with after POST or something

    if entry.author and request.user != entry.author:
        # XX below messages not quite true.  Some others might be able to edit the entry, just not current one
        # proper message would be 'you do not have rights to edit another user's entry' (in this logbook)
        if command==("Edit") and 'edit_others_entries' not in perms:
            return err(_("Only user <b>%s</b> can edit this entry") % entry.author.get_username())
        if command==("Delete") and 'delete_others_entries' not in perms:
            return err(_("Only user <b>%s</b> can delete this entry") % entry.author.get_username())
    elif (
        (command == _("Edit") and 'edit_own_entries' not in perms) 
        or (command == _("Delete") and 'delete_own_entries' not in perms)
    ):
        return err_command_user()
    
    # User has permission, in general, but now see if time-restricted
    cfg = get_config()
    restrict_hours = cfg.get(logbook, "Restrict edit time", valtype=float)
    if not restrict_hours:
        return None

    timediff = timezone.now() - entry.date   # XXX timezone differences?   
    if timediff.total_seconds > restrict_hours * 60 * 60:
        msg = _("Entry can only be edited %1.2lg hours after creation") % restrict_hours
        return err(msg)

    return None


def get_param(
    request, key: str, *, valtype: type = str, default: Any = None, force_single=True
) -> Any:
    """Return the GET query value for key, but default if not found or not of right type

    get_single only affects what happens if a value in the query string is repeated.
    If True, it is standard Django 'get' behaviour - the last value is returned.

    If any value of the parameter can't be converted to `valtype`, then `default` is returned.
    """
    if force_single:
        val = request.GET.get(key, default)
        if val == default:
            return val
        try:
            return valtype(val)
        except ValueError:
            return default

    val = request.GET.getlist(key, default)
    if len(val) == 0 or val == default:
        return default
    try:
        val = [valtype(x) for x in val]
    except ValueError:
        val = default

    return val[0] if len(val) == 1 else val



def do_logout(request):
    return render(request, "flexelog/do_logout.html")


def attachments(request, lb_name, id, filename):
    return render(request, "flexelog/show_error.html", {"message": _("Not Implemented")})

def index(request):
    # XXX need to check Protect Selection page whether the list is shown only to registered users,
    #   (or do equivalent permissions "view logbook index" or similar)
    # OR Selection page = <file> / Guest Selection page = <file> equiv (latter if 'global' password file used in PSI elog)
    # Welcome Title = <html code> equivalent needed
    # Page title from [global] section
    #
    cfg = get_config()
    logbooks = available_logbooks(request)
    context = dict(
        cfg=cfg,
        group_logbooks=available_groups(logbooks),
        heading="FlexElog Logbook Selection",
        cfg_css=cfg.get(
            "global", "css", valtype=str, default=""
        ),  # XXX admin forces global since lb can't exist
    )
    return render(request, "flexelog/index.html", context)


def logbook_post(request, logbook):
    """Handle POST to logbook page - can be New, Reply, Edit form results"""
    # XX auth - need to confirm user can New or Reply or Edit or Delete

    cfg = get_config()
    if request.POST.get("cmd") in (_("Submit"), _("Save")):
        page_type = request.POST["page_type"]
        attr_names = request.POST["attr_names"].split(",")
        lb_attrs = cfg.lb_attrs[logbook.name]
        form = EntryForm(data=request.POST, lb_attrs=lb_attrs)
        if not form.is_valid():
            context = logbook_tabs_context(request, logbook)
            context.update(form.get_context())
            
            return render(request, "flexelog/edit.html", context)

        # Form is valid, now save the inputs to a database Entry
        attrs = {attr_name: form.cleaned_data[attr_name] for attr_name in attr_names}
        if page_type == "Edit":
            entry = Entry.objects.get(lb=logbook, id=form.cleaned_data["edit_id"])
            is_new_entry = False
            entry.last_modified_author = None if request.user.is_anonymous else request.user
            entry.last_modified_date = timezone.now()
        else:  # New/Reply
            entry = Entry()
            entry.author = None if request.user.is_anonymous else request.user
            entry.lb = logbook  # XX security - should check logbook = original entry if a reply
            is_new_entry = True
        # Fill in edit object
        
        entry.attrs = attrs
        entry.text = form.cleaned_data["text"]
        if page_type in ("New", "Reply"):
            entry.date = form.cleaned_data["date"]
            # Find max id for this logbook and add 1
            # XXX is this thread-safe?  
            max_entry = logbook.entries.order_by("-id").first()
            entry.id = max_entry.id + 1 if max_entry else 1
        entry.save(force_insert=is_new_entry)  # XXX Could trap exists error and try again id +=1
        redirect_url = reverse("flexelog:entry_detail", args=[logbook.name, entry.id])
        return redirect(redirect_url)
    # XXX need to cover other cases?

def logbook_from_name(request, lb_name) -> Logbook | HttpResponse:
    lb_name = unquote_plus(lb_name)
    try:
        logbook = Logbook.objects.get(name=lb_name)
    except Logbook.DoesNotExist:
        msg = _('Logbook "%s" does not exist on remote server') % lb_name
        return render(request, "flexelog/show_error.html", context={"message": msg})    
    
    if logbook.active:
        return logbook

    # XX ?maybe should have its own message here?
    msg = _('Logbook "%s" does not exist on remote server') % lb_name
    return render(request, "flexelog/show_error.html", context={"message": msg})      



# view for route "<str:lb_name>/"
def logbook_view(request, lb_name):
    logbook = logbook_from_name(request, lb_name)
    if isinstance(logbook, HttpResponse):
        return logbook

    # New (incl Reply, Duplicate), Edit, Delete all POST to the logbook page
    # (makes some sense as New doesn't have an id yet)
    if request.method == "POST":
        return logbook_post(request, logbook)
    return logbook_get(request, logbook)

def logbook_tabs_context(request, logbook):
    logbooks = available_logbooks(request)
    groups_dict = available_groups(logbooks)
    selected_group = None
    if len(groups_dict) == 1:
        group_tabs = []  # Won't display any
    else:
        for group_name, group_logbooks in groups_dict.items():
            if logbook in group_logbooks:
                selected_group = group_name
                break
        # Compose (name, url) for the group tabs
        group_tabs = [
            (group_name, reverse("flexelog:logbook", args=[group_logbooks[0].name]))
            for group_name, group_logbooks in groups_dict.items()
        ]
                    
    cfg = get_config()
    return dict(
        logbook=logbook, 
        logbooks=groups_dict[selected_group] if len(groups_dict) > 1 else logbooks,
        group_tabs=group_tabs,
        selected_group=selected_group,
        main_tab=cfg.get(logbook, "main tab", valtype=str, default=""),
        cfg_css=cfg.get(logbook, "css", valtype=str, default=""),
    )
        

def get_list_titles_and_fields(logbook):
    cfg = get_config()

    config_attr_names = list(
        cfg.lb_attrs[logbook.name].keys()
    )
    config_attr_names_lower = [attr.lower() for attr in config_attr_names]

    # Get configured database and column titles
    # Don't include Text even if listed, if config Show text=False
    # "*attributes" puts in the Attributes for the logbook not otherwise listed
    list_display = cfg.get(logbook, "list display", as_list=True) or []
    list_display_lower = [x.lower() for x in list_display]
    try:
        i_star_attr = list_display_lower.index("*attributes")
    except ValueError:
        pass
    else:
        used_attributes = [name for name in config_attr_names if name.lower() in list_display_lower]
        adding_attributes = [name for name in config_attr_names if name not in used_attributes]
        list_display = list_display[:i_star_attr] + adding_attributes + list_display[i_star_attr + 1:]

    col_db_fields = []
    col_titles = []
    show_text = cfg.get(logbook, "Show text", valtype=bool)
    for attr_name in list_display:
        if hasattr(Entry, attr_name.lower()):
            # Don't add Text if configd Show text = False
            if attr_name.lower() != "text" or show_text:
                col_db_fields.append(attr_name.lower())
                col_titles.append(_(attr_name))
        elif attr_name.lower() in config_attr_names_lower:
            col_db_fields.append(f"attrs__{attr_name.lower()}")
            col_titles.append(attr_name)
        # else ignore those not in Entry or config'd
        # ^- XX could allow to show old attributes? 

    return col_titles, col_db_fields


def logbook_get(request, logbook):    
    cmd = get_param(request, "cmd")
    commands = [_("New"), _("Find")] # _("Select"), ("Import"), ("Config"), _("Help")
    if response := command_perm_response(request, cmd, commands, logbook):
        return response
    if cmd == _("New"):
        return entry_detail_get(request, logbook, None)
    elif cmd == _("Find"):
        cfg = get_config()
        lb_attrs = cfg.lb_attrs[logbook.name]
        # for lb_attr in lb_attrs.values():
        #     lb_attr.required = False
        form = SearchForm(
            initial={"options": ["reverse"], "mode": "Display full"}, lb_attrs=lb_attrs
        )
        
        context = logbook_tabs_context(request, logbook)
        context.update(
            command_names=[_("Search"), _("Reset Form"), _("Back")],
            form=form,
            regex_message=_("Text fields are treated as %s")
            % f'<a href="https://docs.python.org/3/howto/regex.html">{_("regular expressions")}</a>',
        )

        return render(request, "flexelog/search_form.html", context)

    # Now doing the logbook entry listing summary page
        # If get here, then are just doing the detail view, no editing
    if logbook.auth_required and not request.user.has_perm("view_entries", logbook):
        context = {
            "message": _('User "%s" has no access to this logbook') % request.user.get_username()
        }
        return render(request, "flexelog/show_error.html", context)
    selected_id = get_param(request, "id", valtype=int)

    # XX Adjust available commands according to config
    # XX then according to user auth
    # XX Select command not implemented
    cfg = get_config()
    command_names = [
        _("New"),
        _("Find"),
        _("Import"),
        _("Config"),
        _("Last day"),
        _("Help"),
    ]
    lb_url = reverse("flexelog:logbook", args=[logbook.name])
    commands = [(cmd, f"{lb_url}?cmd={cmd}") for cmd in command_names]
    commands[4] = (_("Last day"), f"{lb_url}past1?mode=Summary")

    modes = (  # First text is translated, url param is not
        (_("Full"), "full"),
        (_("Summary"), "summary"),
        (_("Threaded"), "threaded"),
    )
    mode = _(get_param(request, "mode", default=cfg.get(logbook, "display mode", default="summary")))

    col_titles, col_db_fields = get_list_titles_and_fields(logbook)
   
    columns = dict(zip(col_titles, col_db_fields))
    col_names_lower = [x.lower() for x in col_titles] + ["subtext"]
    # XX could also be in columns not shown in display
    filters = {
        k: v
        for k, v in request.GET.items()
        if k.lower() in col_names_lower and k.lower() != "id" and v != ""
    }
    # need to handle 'subtext' used in original psi elog query string
    if "subtext" in filters:
        filters["text"] = filters.pop("subtext")

    config_attr_names_lower = [attr.lower() for attr in cfg.lb_attrs[logbook.name].keys()]
    filter_attrs = {  # actually text and attrs
        f"{'attrs__' if k.lower() in config_attr_names_lower else ''}{k.lower()}": v
        for k, v in filters.items()
    }

    # XXX need to handle case-(in)sensitive
    filter_fields = {f"{k}__regex": v for k, v in filter_attrs.items()}

    # XX Need to exclude date, id from 'contains'-style search, translate back

    # Determine sort order of entries
    # Default is by date
    # Check if query args have sort specified
    if sort_attr_field := columns.get(get_param(request, "sort")):
        is_rsort = False
    elif sort_attr_field := columns.get(get_param(request, "rsort")):
        is_rsort = True
    else:
        is_rsort = cfg.get(logbook, "Reverse sort")
        sort_attr_field = columns.get(_("Date"), "id")  # use ID if date not shown, likely id is usually shown
    
    # try:
    if sort_attr_field in ("id", "date"):  # XXXX or attrs that are numeric or date-based
        order_by = f"{'-' if is_rsort else ''}{sort_attr_field}"
    else:  # text=based, make case-insensitive
        order_by = Lower(sort_attr_field).desc() if is_rsort else Lower(sort_attr_field)
    
    cfg_reverse = cfg.get(logbook, "Reverse sort", valtype=bool)
    secondary_order = "-id" if cfg_reverse else "id"
    queryset = (
        logbook.entries # .values(*columns.values())
        .filter(**filter_fields)
        .order_by(order_by, secondary_order)  # secondary so ?id=# page find manageable for huge logbooks
    )

    
    # except FieldError:
    #     qs = logbook.entries.values(*columns.values()).order_by("-date")

    # Get page requested with "?page=#" or ?page=all else 1
    req_page_number = get_param(request, "page", default="1")
    if req_page_number.lower() == "all":
        req_page_number = 1
        per_page = cfg.get(logbook, "all display limit")
    else:
        per_page = get_param(request, "npp", valtype=int) or cfg.get(
            logbook.name, "entries per page"
        )
    per_page = min(per_page, cfg.get(logbook, "all display limit"))

    paginator = Paginator(queryset, per_page=per_page)
    
    # If query string has "id=#", then need to position to page with that id
    # ... assuming it exists.  Check that first. If not, then ignore the setting
    page_obj = paginator.get_page(req_page_number)

    if selected_id:
        try:
            sel_entry = logbook.entries.filter(**filter_fields).get(id=selected_id)
        except Entry.DoesNotExist:
            sel_entry = None
    if selected_id and sel_entry:
        # Get just the sort field and id, even in huge logbooks should still be quick
        pairs = (
            logbook.entries
            .filter(**filter_fields)
            .order_by(order_by, secondary_order)  # secondary so ?id=# page find manageable for huge logbooks
            .values_list(sort_attr_field.removeprefix("-"), "id")
        )
        if sort_attr_field.removeprefix("-") in ("id", "date", "text"):
            sel_sort_val = getattr(sel_entry, sort_attr_field.removeprefix("-"))
        else: # XX just attributes left?
            sel_sort_val = sel_entry.attrs[sort_attr_field.removeprefix("attrs__")]
        
        # Tried bisect, but was quite slow. Instead just count number before it in sort order
        sort_cmp = "gt" if is_rsort else "lt"
        id_cmp = "gt" if cfg_reverse else "lt"
        lo = logbook.entries.filter(**filter_fields, **{f"{sort_attr_field}__{sort_cmp}": sel_sort_val}).count()
        exact_field_find_id = {f"{sort_attr_field}":sel_sort_val, f"id__{id_cmp}": selected_id}
        inner_index = logbook.entries.filter(**filter_fields, **exact_field_find_id).count()  # __gt if -id sort
        
        # For some unknown reason this doesn't always get to the right page
        #   ? difference between ordering and comparing individually?
        # So use that as start index and seek to the correct one.
        # In my tests, page repaint is ~4-8 seconds for 216K entries logbook also with sorted column
        #   (python bisect was ~30-50 seconds for same)
        sel_index = lo + inner_index
        op = operator.gt if is_rsort else operator.lt
        direction = 1 if op(pairs[sel_index][0], sel_sort_val) else -1
        while pairs[sel_index][0] != sel_sort_val:
            sel_index += direction
        # Same, but for id
        op = operator.gt if cfg_reverse else operator.lt
        direction = 1 if op(pairs[sel_index][1], selected_id) else -1
        while pairs[sel_index][1] != selected_id:  # Must know that selected_id is there
            sel_index += direction
        
        # now calc the page we found
        page_obj = paginator.get_page(sel_index // per_page + 1)

    num_pages = paginator.num_pages
    if num_pages > 1:
        page_n_of_N = _("Page {num:d} of {count:d}").format(
            num=page_obj.number, count=num_pages
        )
    else:
        page_n_of_N = None

    context = logbook_tabs_context(request, logbook)
    context.update(
        commands=commands,
        modes=modes,
        mode=mode,
        columns=columns,
        page_obj=page_obj,
        page_range=list(
            paginator.get_elided_page_range(page_obj.number, on_each_side=1, on_ends=3)
        ),
        page_n_of_N=page_n_of_N,
        selected_id=selected_id,
        summary_lines=cfg.get(logbook, "Summary lines"),
        sort_attr_field=sort_attr_field,
        is_rsort=is_rsort,
        filters=filters,
        filter_attrs=filter_attrs,
        casesensitive=get_param(request, "casesensitive", valtype=bool, default=False),
        IOptions=[f"attrs__{attr_name}" for attr_name in cfg.IOptions(logbook, lowercase=True)],
    )
    return render(request, "flexelog/entry_list.html", context)


def new_edit_get(request, logbook, command, entry):
    # XXXX check request.user permissions for each of these, for the logbook

    if command == _("New"):
        entry = Entry(lb=logbook)
        entry.author = None if request.user.is_anonymous else request.user
        page_type = "New"
    if command == _("Edit"):
        page_type = "Edit"
        entry.last_modified_author = None if request.user.is_anonymous else request.user
    else:  # _("Reply"), _("Duplicate")
        entry = copy(entry)
        entry.author = None if request.user.is_anonymous else request.user
        entry.pk = None
        entry.id = None
        entry.reply_to = None
        # XXXX entry.author = <current user>
        page_type = "Duplicate"
        if command == _("Reply"):
            page_type = "Reply"
            entry.reply_to = entry.id
            entry.text = (
                f"\n{_('Quote')}:\n"
                + textwrap.indent(entry.text or "", "> ", lambda _: True)
                + "\n"
            )

    if command != _("Edit"):
        entry.date = timezone.now()
        # XXX update last modified date

    if command == _("New"):
        cfg = get_config()
        form = EntryForm(
            lb_attrs=cfg.lb_attrs[logbook.name],
            initial={"date": timezone.now()},
        )
    else:
        form = EntryForm.from_entry(entry, page_type)

    cfg = get_config()
    context = logbook_tabs_context(request, logbook)
    context.update(
        entry=entry,
        commands=[],
        Required=cfg.Required(logbook, lowercase=True),
    )
    context.update(form.get_context())
    return render(request, "flexelog/edit.html", context)


def entry_detail_post(request, logbook: Logbook, entry: Entry):
    """POST method for "<str:lb_name>/<int:entry_id>/"""
    cmd = request.POST.get("cmd")
    url_detail = reverse("flexelog:entry_detail", args=[logbook.name, entry.id])
    if cmd == "Delete":  # hidden field from POSTed Confirmation form
        if request.POST.get("confirm") != _("Yes"):
            return redirect(url_detail)

        entry.delete()

        # Find new entry to redirect to ... next higher available number or the last entry
        next_entry = logbook.entries.filter(id__gt=entry.id).order_by("id").first()
        if not next_entry:
            next_entry = logbook.entries.order_by("-id").first()  # max id entry
            if not next_entry:  # no entries at all, go to logbook main listing:
                return redirect(reverse("flexelog:logbook", args=[logbook.name]))

        return redirect(
            reverse("flexelog:entry_detail", args=[logbook.name, next_entry.id])
        )

    # XXX else?
    return redirect(url_detail)


# ---------------------
# view for route "<str:lb_name>/<int:entry_id>/" and ?cmd={Delete, Find, Edit, etc.}
def entry_detail(request, lb_name, entry_id):
    logbook = logbook_from_name(request, lb_name)
    if isinstance(logbook, HttpResponse):
        return logbook

    try:
        entry = Entry.objects.get(lb=logbook, id=entry_id)
    except Entry.DoesNotExist:
        msg = _("This entry has been deleted")  # XX or was never made
        return render(request, "flexelog/show_error.html", context={"message": msg})

    if request.method == "POST":
        return entry_detail_post(request, logbook, entry)

    return entry_detail_get(request, logbook, entry)


def entry_detail_get(request, logbook, entry):
    command = get_param(request, "cmd")
    cfg = get_config()
    # XXX need to take commands from config file, not just default
    command_names = [
        _("List"),
        _("New"),
        _("Edit"),
        _("Delete"),
        _("Reply"),
        _("Duplicate"),
        # _("Find"),
        # _("Config"),
        # _("Help"),
    ]

    # Check auth
    if response := command_perm_response(request, command, command_names, logbook, entry):
        return response
    
    # Delete starts with GET request, confirmation form does POST
    if command == _("Delete"):
        context = dict(
            title=_("Delete"),
            method="POST",
            action=f".",
            cmd="Delete",
            prompt=_("Are you sure to delete this entry?"),
            message = f"#{entry.id}",
            true_label = _("Yes"),
            false_label = _("No"),
        )
        return render(request, "flexelog/confirmation.html", context)
    
    elif command in (_("New"), _("Edit"), _("Reply"), _("Duplicate")):
        return new_edit_get(request, logbook, command, entry)
    
    url_detail = reverse("flexelog:entry_detail", args=[logbook.name, entry.id])
    commands = [(cmd, f"{url_detail}?cmd={cmd}") for cmd in command_names]
    commands[0] = (
        _("List"),
        reverse("flexelog:logbook", args=[logbook.name]) + f"?id={entry.id}",
    )

    command = get_param(request, "cmd")
    if command:
        if command not in command_names:
            context = {"message": _('Error: Command "<b>%s</b>" not allowed') % command}
            return render(request, "flexelog/show_error.html", context)
            # if command not in command_dispatch:
            #     return show_error(
            #         _('Error: Command "<b>%s</b>" not allowed') % command
            #         + " (not currently implemented)"
            #     )

    context = logbook_tabs_context(request, logbook)
    context.update(entry=entry, commands=commands)

    # If get here, then are just doing the detail view, no editing
    if logbook.auth_required and not request.user.has_perm("view_entries", logbook):
        context = {
            "message": _('User "%s" has no access to this logbook') % request.user.get_username()
        }
        return render(request, "flexelog/show_error.html", context)
    form = EntryViewerForm(data={"text": entry.text or ""})
    context["form"] = form
    context["IOptions"] = cfg.IOptions(logbook, lowercase=True)
    
    return render(request, "flexelog/entry_detail.html", context)


def test(request, lb_name, entry_id):
    cfg = get_config()
    try:
        logbook = Logbook.objects.get(name=lb_name)
    except Logbook.DoesNotExist:
        # 'Logbook "%s" does not exist on remote server'
        raise  # XXX
    entry = get_object_or_404(Entry, lb=logbook, id=entry_id)
    lb_attributes = cfg.lb_attrs[logbook.name]
    attr_names = entry.attrs.keys() if entry.attrs else []
    # Error: translate: "Attribute <b>%s</b> not supplied" for required

    # form = EntryForm(instance=entry, initial={"date": timezone.now()})  # instance=entry for edit existing
    initial = {"date": timezone.now()}
    form = EntryForm(lb_attrs=lb_attributes, initial=initial)
    context = form.get_context()
    context.update(
        {
            "logbook": logbook,
            "logbooks": available_logbooks(request),  # XX will need to restrict to what user auth is, not show deactivated ones
            "main_tab": cfg.get(logbook, "main tab", valtype=str, default=""),
            "cfg_css": cfg.get(logbook, "css", valtype=str, default=""),
            "content": entry.text,
        }
    )
    return render(request, "flexelog/xx_test_viewer.html", context)
