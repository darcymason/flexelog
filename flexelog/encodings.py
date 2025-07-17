# Copyright 2025 flexelog authors. See LICENSE file for details.
"""Handling of PSI elog's ELCode and html encodings"""

import bbcode # ELCode almost identical to BBcode
from django.utils.translation import gettext as _
from markdownify import MarkdownConverter

# from https://stackoverflow.com/questions/20805668/
FONT_SIZES = ["xx-small", "x-small", "small", "medium", "large", "x-large", "xx-large", "-webkit-xxx-large"]

elcode_parser = bbcode.Parser(escape_html=False, replace_links=False)

# Make the add_formatter a decorator
# Functions decorated must be "render_<tag>"
def register(func):
    tag = func.__name__.split("_")[1]
    elcode_parser.add_formatter(tag, func)
    return func

def options_string(options):
    # Quote any options, don't do "= val" if val is blank
    #  Don't repeat quotes if already there
    quoted_opts = {k: f'''"{str(v).replace('"', '')}"''' if v else '' for k,v in options.items()}
    return " ".join(
        f'{opt}{"=" if opt_val else ""}{opt_val}' # val already quoted above
        for opt, opt_val in quoted_opts.items()
    )


def elcode2html(elcode: str) -> str:
    """Convert ELCode text to html (markdown superset)"""
    # ELcode allows "escaping" tags by putting backslash in front.
    # Here replace and "\[" with a non-printable character after the bracket,
    # so parsing will leave it alone

    # XX should theoretically leave any inside code blocks, but ...
    escaped_elcode = elcode.replace(r"\[", "[\0")
    return elcode_parser.format(escaped_elcode).replace("[\0", r"\[")

# bbcode parser covers most things, but we have to add some
@register
def render_table(tag_name, value, options, parent, context):
    row_split = "|-"
    col_split = "|"

    cells = [
        [col.strip() for col in row.split(col_split)]
        for row in value.split(row_split)
    ]
    # XX filter out any?
    row_strings = [
        "".join(f'<td>{col}</td>' for col in row)
        for row in cells
    ]

    table_contents = "\n".join(
        f"<tr>{row_string}</tr>"
        for row_string in row_strings
    )
    return f'<table {options_string(options)}>\n{table_contents}\n</table>\n'

@register
def render_email(tag_name, value, options, parent, context):
    return f'<a href="mailto:{value}">{value}</a>'

@register
def render_font(tag_name, value, options, parent, context):
    if 'font' not in options:
        return value
    
    return f"""<span style="font-family:{options['font']}">{value}</span>"""


# Override bbcode quote handling to "Quote" or add author
@register
def render_quote(tag_name, value, options, parent, context):
    if "quote" in options:
        header = _("%s wrote") % options['quote']
    else:
        header = _("Quote")
    return f"{header}:<br/><blockquote>{value}</blockquote>"


elcode_parser.add_simple_formatter('line', '<hr />', standalone=True)

for h_tag in ("h1 h2 h3 h4 h5 h6".split()):
    elcode_parser.add_simple_formatter(h_tag, f"<{h_tag}>%(value)s</{h_tag}>")

elcode_parser.add_simple_formatter("anchor", f'<a name="%(value)s"></a>')

@register
def render_size(tag_name, value, options, parent, context):
    no_op = f"[{tag_name}]{value}[/{tag_name}]"
    if "size" not in options:
        return no_op
    try:
        size = int(options["size"])
    except:
        return no_op
    
    # clamp size to available indexes
    size = max(0, min(size, 7))
    return f"""<span style="font-size:{FONT_SIZES[size]}">{value}</span>"""


@register
def render_img(tag_name, value, options, parent, context):
    # Handle [img=<src>]something[/img]
    #   but checked after and PSI elog doesn't seem to allow this anyway.
    img = options.pop("img", None)
    if not img:  # should be the case
        img = value
        # XX could check for elog:/1 style reference to attachments,
        # need `entry` passed into context, and would only work
        # for viewing, not for editing
    if "alt" not in options:
        try:
            options["alt"] = img.split("/")[-1]
        except:
            pass
    other_attrs = options_string(options)
    return f"""<img src="{img}" {other_attrs}>"""


# -------------------------------
# HTML to markdown
# -------------------------------
class MDConverter(MarkdownConverter):
    """
    Create a custom MarkdownConverter that handles some tags important to us
    """
    def convert_span(self, el, text, parent_tags):
        # keep <span> but only for style attribute, else strip it
        style = el.attrs.get('style', None)
        if style:
            return f"""<span style="{style}">{text}</span>"""
        else:
            return text

md_converter = MDConverter()

def html2md(text: str) -> str:
    """Take html encoding and turn into markdown"""
    return md_converter.convert(text)
