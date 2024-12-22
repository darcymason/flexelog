from django.test import TestCase

from flexelog.models import Logbook, GeneralConfig, ValidationError


# Create your tests here.
class ConfigTests(TestCase):
    def test_restricted_logbook_name(self):
        lb = Logbook(name="admin")
        self.assertRaises(ValidationError, lb.full_clean)

    def test_no_sections(self):
        conf = GeneralConfig(
            section="global",
            config="Test=1\n[Section]x=2",
        )
        self.assertRaises(ValidationError, conf.full_clean)
