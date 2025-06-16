from django.test import TestCase
from textwrap import dedent

from flexelog.models import Logbook, Entry, ValidationError, User
from flexelog.elog_cfg import LogbookConfig, get_config
from flexelog import subst

class _MockEntry:
    pass

class ConfigTests(TestCase):
    def test_restricted_logbook_name(self):
        lb = Logbook(name="admin")
        self.assertRaises(ValidationError, lb.full_clean)


class TestConditionalConfig(TestCase):
    """Test conditional configuration"""
    config_text = dedent(
        """\
        [Travel]
        Comment = Summarizing trips
        Attributes = Start Date, Duration, Where, Where2, Who, Subject
        MOptions Who = Alice, Bob, Christine, Dave
        Options Where = Canada{ca}, Europe{eu}, US{us}, Other{oth}
        {ca} MOptions Where2 = AB, BC, MB, NB, NL, NS, ON, PE, QC, SK
        {eu} MOptions Where2 = Germany, France, UK, Italy, Slovenia, Czech, Hungary
        {us} MOptions Where2 = FL, NY, Other
        {oth} MOptions Where2 = Somewhere
        Extendable Options = Who, Where, Where2
        Type Start Date = date
        Page Title = $subject
        Reverse sort = 1
        Sort Attributes = Start Date
        """
    )

    def setUp(self):
        self.cfg = LogbookConfig(self.config_text)

    def test_attr_conditions_parsed(self):
        """Ensure Attributes with vals, e.g. Linux{1}, Windows{2} are parsed"""
        lb_attrs = self.cfg.lb_attrs["Travel"]
        where = lb_attrs["Where"]
        self.assertEqual(where.options, "Canada Europe US Other".split())
        self.assertEqual(
            where.val_conditions, 
            {
                "Canada": "ca",
                "Europe": "eu",
                "US": "us",
                "Other": "oth",
            }   
        )

    def test_no_condition(self):
        # one not in the file:
        required = self.cfg.get("Travel", "Required Attributes", as_list=True)
        assert required == []

        # non-list with a value
        assert self.cfg.get("Travel", "Comment") == "Summarizing trips"

        # list of values:
        who = self.cfg.get("Travel", "MOptions Who", as_list=True)
        assert who == ["Alice", "Bob", "Christine", "Dave"]

    def test_conditional_config(self):
        # conditional value with condition set
        with self.cfg:
            self.cfg.add_condition("eu")
            where2 = self.cfg.get("Travel", "MOptions Where2", as_list=True)
            assert where2 == "Germany France UK Italy Slovenia Czech Hungary".split()

        with self.cfg:
            self.cfg.add_condition("us")
            where2 = self.cfg.get("Travel", "MOptions Where2", as_list=True)
            assert where2 == "FL NY Other".split()

        # test condition is case-insensitive
        with self.cfg:
            self.cfg.add_condition("US")
            where2 = self.cfg.get("Travel", "MOptions Where2", as_list=True)
            assert where2 == "FL NY Other".split()            

# XXX TO DO:
# * logbook name "urlsafe" - spaces, etc.
# * check index page when latest_date has no entries 

class TestSubstitutions(TestCase):
    def setUp(self):
        self.logbook = Logbook(name="test")
        self.entry = Entry(lb=self.logbook)
        self.entry.attrs = {}
        self.user = User(username="sam", last_name="Carter", first_name="Samantha", email="sam@example.com")
    def test_re_on_reply(self):
        self.entry.attrs = {"subject": "Subject of entry"}
        subst_text = "Re: $Subject"
        expected = "Re: Subject of entry"
        got = subst.subst(subst_text, logbook=self.logbook, user=self.user, entry=self.entry)
        self.assertEqual(got, expected)
    def test_other_subst(self):
        subst_text = (
            "On $date (UTC: $utcdate), "
            "user '$short_name' ($long_name, email:$user_email) "
            "made an entry in logbook '$logbook' "
            "using flexelog v$version"
        )
        got = subst.subst(subst_text, logbook=self.logbook, user=self.user, entry=self.entry)
        self.assertTrue("$" not in got)
        # XX could actually check some substituted values to be more complete
        