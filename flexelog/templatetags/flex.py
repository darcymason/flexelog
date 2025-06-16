import textwrap
from typing import List
from django import template
from django.conf import settings
from django.templatetags.static import static
from django.urls import reverse
from django.utils import formats
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape, format_html
from django.template.defaultfilters import stringfilter

import re

from flexelog.elog_cfg import get_config
from flexelog.editor.widgets_toastui import MarkdownViewerWidget
from flexelog.models import Entry

register = template.Library()


HIGHLIGHT_OPEN = '<span class="highlight">'
HIGHLIGHT_CLOSE = "</span>"


# XXX need to check that still escapes html properly
#   Django help suggests `format_html` instead to help with that
@register.filter(needs_autoescape=True)
@stringfilter
def highlight(value, search_term, autoescape=True):
    if autoescape:
        esc = conditional_escape
    else:
        esc = lambda x: x
    if search_term is None:
        return mark_safe(esc(value))
    return mark_safe(
        esc(value).replace(
            esc(search_term), f"{HIGHLIGHT_OPEN}{esc(search_term)}{HIGHLIGHT_CLOSE}"
        )
    )

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def attr_show(val):
    if isinstance(val, list):
        return " | ".join(val)
    return val

@register.filter
def icon_show(val):
    if isinstance(val, str):
        return mark_safe(  # XXX security - should escape the icon name
            f'<img src="{settings.STATIC_URL}flexelog/icons/{val}" '
            f'alt="{val}" title="{val}" '
            " />"
        )
    return val


@register.filter
def list_replies(entry):
    if not isinstance(entry, Entry) or not entry.replies:
        return mark_safe("")
    lb_name = entry.lb.name
    reply_htmls = []
    for reply in entry.replies.all():
        link = reverse('flexelog:entry_detail', args=[lb_name, reply.id])
        reply_htmls.append(f'&nbsp;<a href="{link}">{reply.id}</a>')
    return mark_safe("&nbsp;".join(reply_htmls))
 

def _text_summary_lines(text, width, max_lines):
    if not text:
        return ""

    text_wrapper = textwrap.TextWrapper(
        width=width,
        max_lines=max_lines,
        placeholder="",
    )

    lines = []
    for line in text.splitlines():
        lines += text_wrapper.wrap(line)
        if len(lines) > max_lines:
            break
    return lines[:max_lines]


def highlight_text(text, pattern, case_sensitive=False, autoescape=True):
    """Place html highlighting around matched pattern in the string
    
    Does NOT return a safe string in general, because it is used for
    markdown text with possibly span and br and latex brackets, etc. 
    and the EDITOR / viewer MUST sanitize the markdown to present as html.

    However, if a search pattern is used, then escapes all values to avoid any issues
    with the search string entered by the user, when used in Summary listing mode.
    """
    esc = conditional_escape if autoescape else lambda x:x
    if not pattern:
        return text
    
    # Note is case-sensitive, so if need insensitive pattern should start with "(?i)"
    case_sens = "" if case_sensitive else "(?i)"
    pattern = rf"{case_sens}({pattern})"

    
    parts = re.split(f"{pattern}", text)  # parentheses so match is output in list
    return mark_safe(
        "".join(
            format_html(f"{HIGHLIGHT_OPEN}{{}}{HIGHLIGHT_CLOSE}", part) if re.match(pattern, part) else esc(part)
            for part in parts
        )
    )

@register.simple_tag
def entry_listing(entry, columns, selected_id, filter_attrs, casesensitive, mode, cycle, index, autoescape=True):
    text_fmt_summary = """<td class="summary{cycle}">{val}</td>"""
    text_fmt_full = """<tr><td class="messagelist" colspan="{colspan}">{val}</td></tr>"""
    non_text_fmt = {
        "summary": '<td class="list{cycle}{h_sel}"{nowrap}>{href_open}{val}</a></td>',
        "full": '<td class="list1full{h_sel}"{nowrap}>{href_open}{val}</a></td>',
    }
    attachment_fmt = """<td class="listatt{cycle}">{linked_icons}</td>"""

    cfg = get_config()
    htmls = [] 
    detail_url = reverse("flexelog:entry_detail", args=[entry.lb.name, entry.id])
    href_open = f'<a href="{detail_url}">'
    h_sel = "h" if entry.id == selected_id else ""

    esc = conditional_escape if autoescape else lambda x: x

    # For mode=full track text and attachments separately
    mode_full_row1_tds = []
    mode_full_row2 = ""
    mode_full_row3 = ""
    
    if mode == "summary":
        htmls.append("<tr>")
    
    for field in columns.values():
        val = getattr(entry, field, None) or entry.attrs.get(field.removeprefix("attrs__")) or ""
        if isinstance(val, list):
            val = " | ".join(val)
        is_text = (field == "text")
        if field == "date":  # XX need to localize other date fields, XX need to use configd date format
            val = str(formats.localize(val, use_l10n=True))
        search_pattern = filter_attrs.get(field)

        if is_text and mode == "summary":
            # if entry.encoding == "HTML":
            #     text = markdownify(self.text)
            width = cfg.get(entry.lb, "summary line length", valtype=int, default="100")
            max_lines = cfg.get(entry.lb, "summary lines", valtype=int, default="3")
            lines =  _text_summary_lines(entry.text, width, max_lines)
            if search_pattern:
                val = "<br/>".join(highlight_text(line, search_pattern, casesensitive) for line in lines)
            else:
                val = "<br/>".join(esc(line) for line in lines)
            htmls.append(text_fmt_summary.format(cycle=cycle, val=val))                    
        elif is_text and mode == "full":
            highlighted_lines = (highlight_text(line, search_pattern, casesensitive) for line in entry.text.splitlines())
            widget = MarkdownViewerWidget(attrs={"id": f"viewer{index}"})
            mode_full_row2 = text_fmt_full.format(
                val = widget.render(name=f"viewer_name{index}", value="\n".join(highlighted_lines)),
                colspan=len(columns) -2,
            )
            # mode_full_row2 = text_fmt_full.format(
            #     val="<br/>".join(highlighted_lines),
            #     colspan=len(columns)-1
            # )
            
        elif field == "attachments":
            if entry.attachments.count():
                attachment_img_fmt = """<img border="0" align="absmiddle" src="{img_src_url}" alt="{attach_name}" title="{attach_name}" />"""
                link_icons = []
                for attachment in entry.attachments.all():
                    attachment_img = attachment_img_fmt.format(
                        img_src_url=static("flexelog/attachment.png"),
                        attach_name=attachment.filename,
                    )
                    link_icons.append(
                        f"""<a href="{attachment.attachment_file.url}" target="_blank">{attachment_img}</a>""".format(
                            attachment=attachment, 
                            attachment_img=attachment_img,
                        )
                    )
                linked_icons = "&nbsp;".join(link_icons)
            else:
                linked_icons = "&nbsp;"                
            if mode == "summary":
                htmls.append(attachment_fmt.format(linked_icons=linked_icons, cycle=cycle))
            elif mode == "full":
                pass  # XXX needs fix to display attachements
                # mode_full_row3 = attachment_fmt.format(linked_icons=linked_icons, cycle=cycle)  
        else:
            attr_td = non_text_fmt[mode].format(
                cycle=cycle,
                h_sel = h_sel,
                nowrap=" nowrap" if field == "date" else "",
                href_open=href_open,
                val = highlight_text(val, search_pattern), 
            )

            if mode == "summary":
                htmls.append(attr_td)
            elif mode == "full":
                mode_full_row1_tds.append(attr_td)

    if mode == "full":
        htmls.append("<tr>" + "".join(mode_full_row1_tds) + "</tr>")
        htmls.append(mode_full_row2)
        htmls.append(mode_full_row3)
    elif mode == "summary":
        htmls.append("</tr>")

    return mark_safe("\n".join(htmls))

# THREAD_INDENT_CHARACTER = "↳"  # \u21b3, Downwards Arrow With Tip Rightwards
# THREAD_INDENT_CHARACTER = '⇨'  # ⇒
THREAD_INDENT_CHARACTER = '<span style="background-color:white">⇒</span>' 
INDENT = "&nbsp;&nbsp;&nbsp;"
MAX_SUMMMARY_WIDTH = 200  # XX make a config items for this?

thread_line_fmt = (
    '<tr><td align="left" class="threadreply">'
    '{indent}<a href="{link}">'
    '{indent_chr}&nbsp;{entry_summary}'
    '</a></td></tr>'
)


def _entry_thread_summary(entry, esc):
    """Return a brief summary of the entry: date, attr vals, some of text"""
    cfg = get_config()    
    parts = [f"&nbsp;{entry.date}&nbsp;"]
    if entry.attrs:
        parts.append("; ".join(esc(attr_show(val)) for val in entry.attrs.values()))
    if entry.text:
        parts.append("\N{RIGHTWARDS ARROW} " + esc(entry.text[:MAX_SUMMMARY_WIDTH]))
    return textwrap.shorten("  ".join(parts), MAX_SUMMMARY_WIDTH)


def _thread_tree(entry, indent_level, selected_id, esc) -> List[str]:
    """Return html lines for an entry and descendants.  Used recursively"""
    lines = []
    # Render self first
    entry_summary = _entry_thread_summary(entry, esc)
    if entry.id == selected_id:
        entry_summary = "<b>" + entry_summary + "</b>"
    
    lines.append(
        thread_line_fmt.format(
            indent = INDENT * indent_level,
            link = reverse("flexelog:entry_detail", args=[entry.lb.name, entry.id]),
            indent_chr = THREAD_INDENT_CHARACTER,
            entry_summary=entry_summary,
        )
    )
    for reply in entry.replies.all():
        lines.extend(_thread_tree(reply, indent_level + 1, selected_id, esc))
    
    return lines
    

@register.simple_tag
def thread_tree(entry: Entry, autoescape=True):
    # <a href="../Biz/227">
    root = entry.reply_ancestor()
    esc = conditional_escape if autoescape else lambda x:x
    lines = _thread_tree(root, 0, entry.id, esc)
    return mark_safe("\n".join(lines))