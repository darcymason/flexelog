from django.test import TestCase
from textwrap import dedent
from flexelog.elcode import elcode2html

class TestELCode(TestCase):
    """Test ELCode conversions"""

    def test_table(self):
        elcode = dedent(
            """\
            [TABLE border=1]
            A|B|C
            |-
            1|2|3
            """
        )
        expected = dedent(
            """\
            <table border="1">
            <tr><td>A</td><td>B</td><td>C</td></tr>
            <tr><td>1</td><td>2</td><td>3</td></tr>
            </table>
            """
        )
        got = elcode2html(elcode)
        self.assertEqual(expected, got)

    def test_quote(self):
        content = "Here is previous written stuff"
        elcode = f"[QUOTE=Mr. Jack]{content}[/quote]"
        self.assertEqual(elcode2html(elcode), f"Mr. Jack wrote:<br/><blockquote>{content}</blockquote>")

    def test_size(self):
        content = "Here is size 3"
        elcode = f"[size=3]{content}[/size]"
        expected = f'<span style="font-size:medium">{content}</span>'
        self.assertEqual(elcode2html(elcode), expected)

    def test_img(self):
        content = "http://example.com/image.png"
        # use the value itself as url
        elcode = f"[img]{content}[/img]"
        expected = f'<img src="{content}" alt="image.png">'
        self.assertEqual(elcode2html(elcode), expected)