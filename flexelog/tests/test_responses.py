from datetime import datetime
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
global_config += f'[Log 2]\n{lb_config.replace("Log 1", "Log 2")}'



class TestResponsesEmptyDb(TestCase):
    """No ElogConfig or Logbooks set up - check error messages"""
    def test_index_no_logbooks(self):
        url = reverse("flexelog:index")
        response = self.client.get(url)
        self.assertContains(response, "No logbook defined on this server")
        # self.client.cookies.load({settings.LANGUAGE_COOKIE_NAME: "fr"})
        response = self.client.get(url, headers={"accept-language": "fr"})
        self.assertContains(response, "Aucun registre n'est défini sur ce serveur")
        # self.client.cookies.load({settings.LANGUAGE_COOKIE_NAME: "en"})

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
            name="Log 1",
            # config=lb_config,
        )
        cls.lb2 = Logbook.objects.create(
            name="Log 2",
            # config=lb_config.replace("Log 1", "Log 2"),
        )


        # Add some entries
        cls.entry1 = Entry(
            lb=cls.lb1,
            id=1,
            date=timezone.make_aware(datetime(2025,1,1,9,0,0)),
            attrs='{"subject": "First entry", "category": ["Cat 1", "Cat 2"], "text": "Log 1 entry 1"}',
        )
        cls.entry2 = Entry(
            lb=cls.lb1,
            id=2,
            date=timezone.make_aware(datetime(2025,1,1,9,0,0)),
            attrs='{"subject": "First entry", "category": ["Cat 1", "Cat 2"], "text": "Log 1 entry 2"}',
        )
        cls.entry1.save()
        cls.entry2.save()
        cls.lb1.save()
        cls.lb2.save()

    def test_logbook_list(self):
        response = self.client.get(reverse("flexelog:index"))
        print(response.content.decode())
        self.assertContains(response, b'<th class="seltitle">Entries</th>')

    def test_logbook_entry_list(self):
        """"""
        pass
