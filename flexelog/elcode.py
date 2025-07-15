# Copyright 2025 flexelog authors. See LICENSE file for details.
"""Handling of PSI elog's ELCode encoding"""

import bbcode # ELCode almost identical to BBcode
from django.utils.translation import gettext as _

elcode_parser = bbcode.Parser()


def elcode2html(elcode: str) -> str:
    """Convert ELCode text to html (markdown superset)"""
    # ELcode allows "escaping" tags by putting backslash in front.
    # Here replace and "\[" with a non-printable character after the bracket,
    # so parsing will leave it alone

    # XX should theoretically leave any inside code blocks, but ...
    escaped_elcode = elcode.replace(r"\[", "[\0")
    return elcode_parser.format(escaped_elcode).replace("[\0", r"\[")

# bbcode parser covers most things, but we have to add some
def render_table(tag_name, value, options, parent, context):
    row_split = "|-"
    col_split = "|"

    quoted_opts = {k: f'''"{v.replace('"', '')}"''' if v else '' for k,v in options.items()}

    opt_list = [
        f'{opt}{"=" if opt_val else ""}{opt_val}'
        for opt, opt_val in quoted_opts.items()
    ]

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
    return f'<table {" ".join(opt_list)}>\n{table_contents}\n</table>\n'
elcode_parser.add_formatter("table", render_table)


def render_email(tag_name, value, options, parent, context):
    return f'<a href="mailto:{value}">{value}</a>'
elcode_parser.add_formatter("email", render_email)


def render_font(tag_name, value, options, parent, context):
    if 'font' not in options:
        return value
    
    return f"""<span style="font-family:{options['font']}">{value}</span>"""

elcode_parser.add_formatter("font", render_font)

# Override bbcode quote handling to "Quote" or add author
def render_quote(tag_name, value, options, parent, context):
    if "quote" in options:
        header = _("%s wrote") % options['quote']
    else:
        header = _("Quote")
    return f"{header}:<br/><blockquote>{value}</blockquote>"
elcode_parser.add_formatter("quote", render_quote)

elcode_parser.add_simple_formatter('line', '<hr />', standalone=True)

for h_tag in ("h1 h2 h3 h4 h5 h6".split()):
    elcode_parser.add_simple_formatter(h_tag, f"<{h_tag}>%(value)s</{h_tag}>")

elcode_parser.add_simple_formatter("anchor", f'<a name="%(value)s"></a>')

if __name__ == "__main__":
    s = """\
    A|B|C
    |-
    1|2|3
    |-
    4|5|6
    |-Seven|Eight|Nine
    """
    print(render_table("table", s, {"border": "1", "nowrap": "", "cellspacing":20}, None, None))

    s = "[h1]Heading 1[/h1]"
    print(elcode_parser.format(s))

    s = "[FONT=Arial]New font here[/FONT]"
    print(elcode2html(s))

    print()
    s = "[QUOTE=Mr. Jack]Here is previous written stuff[/quote]"
    print(elcode2html(s))