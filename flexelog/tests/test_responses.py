from datetime import datetime
import re
from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import translation, timezone

from textwrap import dedent

from flexelog.models import Logbook, ElogConfig, Entry
from flexelog.elog_cfg import LogbookConfig, get_config



lb_config = dedent(
    """\
    Comment = Comment for Log 1
    Attributes = Status, Category, Subject
    ROptions Status = Not started, Started, Done
    MOptions Category =  Cat 1, Cat 2, Cat 3
    Required Attributes = Category, Subject
    Page Title = Log 1 - $Subject
    Quick filter = Category, Status
    """
)



global_config = dedent(
    """\
    [global]
    Default Encoding = 0
    Reverse sort = 1
    Main Tab = Index
    """
)

global_config += f"[Log 1]\n{lb_config}"
global_config += f'[Log2]\n{lb_config.replace("Log 1", "Log2")}'



class TestResponsesEmptyDb(TestCase):
    """No ElogConfig or Logbooks set up - check error messages"""
    def test_index_no_logbooks(self):
        """Index page displays message if no active logbooks defined"""
        url = reverse("flexelog:index")
        response = self.client.get(url)
        self.assertContains(response, "No logbook defined on this server")
        self.assertContains(response, "Admin")

        # Different language
        response = self.client.get(url, headers={"accept-language": "fr"})
        self.assertContains(response, "Aucun registre n'est défini sur ce serveur")
        self.assertContains(response, "Administration")
    
    def test_logbook_list_no_lb_exists(self):
        """Proper message given if specified logbook does not exist"""
        url = reverse("flexelog:logbook", kwargs={"lb_name": "DoesntExist"})
        response = self.client.get(url)
        self.assertContains(response, "does not exist on remote server")

        # Different language
        response = self.client.get(url, headers={"accept-language": "de"})
        self.assertContains(response, "existiert nicht auf entferntem Server")


class TestResponsesNoAuth(TestCase):
    """Test basic CRUD operations via django test Client tests"""

    @classmethod
    def setUpTestData(cls):
        # Set up data for the whole TestCase
        cls.global_config = ElogConfig.objects.create(
            name="default",
            config_text=global_config,
        )

        cls.lb1 = Logbook.objects.create(
            name="Log 1",  # NOTE: has space for url quoting testing
            # config=lb_config,
        )
        cls.lb2 = Logbook.objects.create(
            name="Log2",
            # config=lb_config.replace("Log 1", "Log2"),
        )

        # Add some entries
        cls.entry1 = Entry(
            lb=cls.lb1,
            id=1,
            date=timezone.make_aware(datetime(2025,1,1,9,0,0)),
            attrs={"subject": "First entry", "category": ["Cat 1", "Cat 2"], "status": "Started"},
            text = "Log 1 entry 1",
        )
        cls.entry2 = Entry(
            lb=cls.lb1,
            id=2,
            date=timezone.make_aware(datetime(2025,1,1,9,0,0)),
            attrs={"subject": "Second entry", "category": ["Cat 2"], "status": "Done"},
            text = "Log 1 entry 2",
        )
        cls.entry1.save()
        cls.entry2.save()
        cls.lb1.save()
        cls.lb2.save()

    def test_logbook_list(self):
        url = reverse("flexelog:index")
        response = self.client.get(url)
        
        self.assertContains(response, "Entries")
        rstr = response.content.decode()

        pattern = (
            r"<tr>.*<th.*Logbook.*<th.*Entries.*<th.*Last submission.*</tr>"
            r".*<tr>.*<td.*Log 1.*</td>.*<td.*2.*</td>"
            r".*<tr>.*<td.*Log2.*</td>.*<td.*0.*</td>"
        )
        self.assertTrue(re.search(pattern, rstr, re.DOTALL))

    def test_logbook_entry_list(self):
        """Test html returned from listing of a log books entries"""
        url = reverse("flexelog:logbook", kwargs={"lb_name": "Log+1"})
        response = self.client.get(url)
        rstr = response.content.decode()
        print(rstr)

        # Note Reverse Sort is true
        pattern = (
            r"<tr.*ID.*Date.*Status.*Category.*Subject.*Text.*</tr>"
            r".*<tr.*2.*Done.*Cat 2.*Second entry.*Log 1 entry 2.*</tr>"
            r".*<tr.*1.*Started.*Cat 1\|Cat 2.*First entry.*</tr>"
        )
        self.assertTrue(re.search(pattern, rstr, re.DOTALL))
