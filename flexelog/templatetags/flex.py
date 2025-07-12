from copy import copy
import textwrap
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



def _nearest_break(text, index, break_tie_left=True):
    if not text:
        return 0

    index = max(0, min(index, len(text)))

    word_breaks = [m.start() for m in re.finditer(r"\b", text)]
    
    # Add start and end of text if not present
    if 0 not in word_breaks:
        word_breaks.insert(0, 0)
    if len(text) not in word_breaks:
        word_breaks.append(len(text))
    
    word_breaks = sorted(set(word_breaks)) # unique and sorted

    if not word_breaks:
        return index

    nearest_break = -1
    min_distance = len(text) + 1

    for wb_i in word_breaks:
        distance = abs(wb_i - index)
        if distance < min_distance:
            min_distance = distance
            nearest_break = wb_i
        elif distance == min_distance:
            # If distances are equal, user tie-break flag
            if break_tie_left:
                if wb_i <= index:
                    nearest_break = wb_i
            elif wb_i >= index:
                nearset_break = wb_i

    return nearest_break


def _text_summary_lines(text, width, max_lines, pattern):
    BREAK_WITHIN = 12 # adjust clips to include a work break within this many characters
    text_wrapper = textwrap.TextWrapper(width, max_lines=max_lines)

    if not text:
        return ""

    # If problem with the search pattern, ignore it    
    if pattern:
        try:
            regex = re.compile(rf"(?i)({pattern})")
        except:
            pattern = None

    if len(text) < width * max_lines:
        lines = []
        for line in text.splitlines():
            lines += text_wrapper.wrap(line)
            if len(lines) > max_lines:
                break
        return lines[:max_lines]

    if pattern:
        breaks = re.compile(r"\W+")
        start_end_match = [(m.start(), m.end(), m.group(0)) for m in regex.finditer(text)]
        
        max_pre = width // 2 
        max_post = width // 3
        clips = [
            (max(0, start-max_pre), end+max_post)
            for (start, end, _) in start_end_match
        ]
        word_break_clips = []
        for start_near, end_near in clips:
            piece_start = max(0, start_near-BREAK_WITHIN)
            post_piece_start = max(0, end_near - BREAK_WITHIN)
            break_start = _nearest_break(text[piece_start:start_near + BREAK_WITHIN], start_near-piece_start)
            break_end = _nearest_break(text[post_piece_start:end_near + BREAK_WITHIN], end_near-post_piece_start, break_tie_left=False)
            word_break_clips.append((break_start+piece_start, break_end+post_piece_start))

        # Merge overlapping clips of text
        merged = []
        start, end = word_break_clips[0]
        for start2, end2 in word_break_clips[1:]:
            if start2 <= end:
                end = max(end, end2)  # use max in case different processing later, e.g. word breaks
            else:
                merged.append((start, end))
                start, end = start2, end2
        # add last one
        merged.append((start, end))
        text = "...".join(text[start:end] for (start, end) in merged)
        prepend = "" if merged[0][0] == 0 else "..."
        postpend = "" if merged[-1][1] >= len(text) else "..."
        text = prepend + text + postpend
    
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

    
    parts = re.split(pattern, text)  # parentheses so match is output in list
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
    attachment_img_fmt = """<img border="0" align="absmiddle" src="{img_src_url}" alt="{attach_name}" title="{attach_name}" />"""

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
            lines =  _text_summary_lines(entry.text, width, max_lines, search_pattern)
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
                link_icons = []
                for attachment in entry.attachments.all():
                    attachment_img = attachment_img_fmt.format(
                        img_src_url=static("flexelog/attachment.png"),
                        attach_name=attachment.display_filename,
                    )
                    link_icons.append(
                        f"""<a href="{attachment.file.url}" target="_blank">{attachment_img}</a>""".format(
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


def _thread_tree(entry, indent_level, selected_id, esc) -> list[str]:
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