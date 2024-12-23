from django.test import TestCase
from textwrap import dedent

from flexelog.models import Logbook, ElogConfig, ValidationError
from flexelog.elog_cfg import LogbookConfig, get_config


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
        ElogConfig.objects.create(name="default", config_text=self.config_text)

    def test_attr_conditions_parsed(self):
        """Ensure Attributes with vals, e.g. Linux{1}, Windows{2} are parsed"""
        cfg = get_config()
        lb_attrs = cfg.lb_attrs["Travel"]
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
        cfg = get_config()
        required = cfg.get("Travel", "Required Attributes", as_list=True)
        assert required == []

        # non-list with a value
        assert cfg.get("Travel", "Comment") == "Summarizing trips"

        # list of values:
        who = cfg.get("Travel", "MOptions Who", as_list=True)
        assert who == ["Alice", "Bob", "Christine", "Dave"]

    def test_conditional_config(self):
        # conditional value with condition set
        cfg = get_config()
        with cfg:
            cfg.add_condition("eu")
            where2 = cfg.get("Travel", "MOptions Where2", as_list=True)
            assert where2 == "Germany France UK Italy Slovenia Czech Hungary".split()

        with cfg:
            cfg.add_condition("us")
            where2 = cfg.get("Travel", "MOptions Where2", as_list=True)
            assert where2 == "FL NY Other".split()

        # test condition is case-insensitive
        with cfg:
            cfg.add_condition("US")
            where2 = cfg.get("Travel", "MOptions Where2", as_list=True)
            assert where2 == "FL NY Other".split()            