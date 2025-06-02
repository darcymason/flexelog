from django.test import TestCase
from django.contrib.auth.models import AnonymousUser
from flexelog.models import User, Logbook
from flexelog.views import available_logbooks


class MockRequest:
    user = None


class TestPermissions(TestCase):
    """Check that permissions are respected"""
    fixtures = ["test_stargate", "test_auth_stargate"]
    def test_available_logbooks_authd(self):
        """Auth'd user only gets offered logbooks they have view permission for"""
        req = MockRequest()
        req.user = User.objects.get(username="Sam")
        empty_lb = Logbook.objects.get(name="Empty Log")
        logbooks = available_logbooks(req)
        self.assertFalse(empty_lb in logbooks)

    def test_available_logbooks_not_authd(self):
        """Anonymous user gets offered logbooks as long as they are not 'unlisted'"""
        req = MockRequest()
        req.user = AnonymousUser()
        empty_lb = Logbook.objects.get(name="Empty Log")
        aliens_only = Logbook.objects.get(name="AliensOnly")  # unlisted
        logbooks = available_logbooks(req)
        self.assertTrue(empty_lb in logbooks)
        self.assertTrue(aliens_only not in logbooks)
