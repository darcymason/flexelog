from django import template
from django.conf import settings
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape, format_html
from django.template.defaultfilters import stringfilter
import re


register = template.Library()


HIGHLIGHT_OPEN = '<B style="color:black;background-color:#ffff66">'
HIGHLIGHT_CLOSE = "</B>"


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


@register.simple_tag
def summary_line(entry, columns, selected_id, filter_attrs, search_text, cycle):
    # Note double {{ and }} here, so first (Python) format leaves {val} for format_html()
    td_fmt = """<td class="{class_}"{nowrap}>{href_open}{{val}}{href_close}</td>"""

    htmls = []
    url = reverse("flexelog:entry_detail", args=[entry.lb.name, entry.id])
    href_open = f'<a href="{url}">'

    for field in columns.values():
        val = getattr(entry, field, None) or entry.attrs.get(field.removeprefix("attrs__")) or ""
        if isinstance(val, list):
            val = " | ".join(val)
        is_text = (field == "text")
        h_sel = "h" if entry.id == selected_id else ""
        
        format1 = td_fmt.format(
            class_=f"summary{cycle}" if is_text else f"list{cycle}{h_sel}",
            nowrap=" nowrap" if field == "date" else "",
            href_open="" if is_text else href_open,
            href_close="" if is_text else "</a>",
        )
        htmls.append(format_html(format1, val=val))

    return mark_safe("\n".join(htmls))

# <tr>
#   {% for key, val in entry.items %}
#   <td class="{% if key == 'text' %}summary{{ listX }}{% else %}list{{ listX }}{% if entry.id == selected_id %}h{% endif %}{% endif %}"{% if key == "date" %} nowrap{% endif %}>
#     {% if key != "text" %}<a href="{% url 'flexelog:entry_detail' logbook.name entry.id %}">{% endif %}
#     {% if key == "id" %}&nbsp;&nbsp;{% endif %}
#     {% with filter_attrs|get_item:key as search_text %}
#       {% if key in IOptions %}{{ val|icon_show }}
#       {% else %}{{ val|attr_show|highlight:search_text }}
#       {% endif %}
#     {% endwith %}
#     {% if key == "id" %}&nbsp;&nbsp;{% endif %}
#     {% if not key == "text" %}</a>{% endif %}
#   </td>
#   {% endfor %}
#   {% if forloop.last%}<td class="listatt{{ listX }}">&nbsp;&nbsp;{{ val }}</td>{% endif %}
# </tr>
# {% empty %}
#     </table><tr><td class="errormsg">{% translate 'No entries found' %}</td></tr>
# {% endfor %}
