from django import template
from django.conf import settings
from django.utils.safestring import mark_safe
from django.utils.html import conditional_escape
from django.template.defaultfilters import stringfilter

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
