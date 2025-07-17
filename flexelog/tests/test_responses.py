from datetime import datetime
from io import BytesIO
import re
from django.conf import settings
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse
from django.utils import translation, timezone

from textwrap import dedent

from flexelog.models import Logbook, ElogConfig, Entry, Attachment
from flexelog.elog_cfg import LogbookConfig, get_config


lb_config = dedent(
    """\

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
log_1_config = dedent(
    """\
    Comment = Comment for Log 1
    Attributes = Status, Category, Subject
    ROptions Status = Not started, Started, Done
    MOptions Category =  Cat 1, Cat 2, Cat 3
    Required Attributes = Category, Subject
    Page Title = Log 1 - $Subject
    Quick filter = Category, Status
    Preset on first reply Subject = Re: $Subject
    """ 
)

log2_config = dedent(
    """\
    Comment = Comment for Log 2
    Attributes = Status, Category, Subject
    ROptions Status = Not started, Started, Done
    MOptions Category =  Cat 1, Cat 2, Cat 3
    Required Attributes = Category, Subject
    Page Title = Log 2 - $Subject
    Quick filter = Category, Status
    """
)

emptylog_config = dedent(
    """\
    Comment = No entries to start
    Attributes = Subject
    """
)


empty_attachment_data = {
    'attachments-TOTAL_FORMS': '3',
    'attachments-INITIAL_FORMS': '0',
    'attachments-MIN_NUM_FORMS': '0',
    'attachments-MAX_NUM_FORMS': '1000',
    'attachments-0-attachment_file': '',
    'attachments-0-id':  '',
    'attachments-1-attachment_file': '',
    'attachments-1-id':  '',
    'attachments-2-attachment_file': '',
    'attachments-2-id':  '',
}
    

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


class TestEmptyLogbook(TestCase):
    """Test basic CRUD operations via django test Client tests starting with empty Logbook"""

    @classmethod
    def setUpTestData(cls):
        # Set up data for the whole TestCase
        cls.global_config = ElogConfig.objects.create(
            name="global",
            config_text=global_config,
        )
        cls.lb = Logbook.objects.create(name="EmptyLog", auth_required=False)
        cls.lb.config = emptylog_config
        cls.lb.save()

    def test_empty_list_entries(self):
        url = reverse("flexelog:logbook", kwargs={"lb_name": "EmptyLog"})
        response = self.client.get(url)
        self.assertContains(response, "No entries found")
    
    def test_empty_logbook_new_entry(self):
        data = {
            'cmd': 'Submit',
            'date': '2025-05-23 22:05:40',
            'Subject': 'Test edit',
            'page_type': 'New',
            'attr_names': 'Subject',
            'edit_id': '',
            'reply_to': '',
            'text': 'Test New entry empty logbook',
        } | empty_attachment_data
        url = reverse("flexelog:logbook", kwargs={"lb_name": "EmptyLog"})
        response = self.client.post(url, data=data)

        # check entry in db created
        entry = self.lb.entries.last()
        self.assertEqual(entry.id, 1)
    
    def test_delete_last_entry_redirect(self):
        pass


class TestResponsesNoAuth(TestCase):
    """Test basic CRUD operations via django test Client tests"""

    @classmethod
    def setUpTestData(cls):
        # Set up data for the whole TestCase
        cls.global_config = ElogConfig.objects.create(
            name="global",
            config_text=global_config,
        )

        cls.lb1 = Logbook.objects.create(
            name="Log 1",  # NOTE: has space for url quoting testing
            config=log_1_config,
            auth_required=False,
        )
        cls.lb2 = Logbook.objects.create(
            name="Log2",
            config = log2_config,
            auth_required = False,
        )

        # Add some entries
        cls.entry1 = Entry(
            lb=cls.lb1,
            id=1,
            date=timezone.make_aware(datetime(2025,1,1,9,0,0)),
            attrs={"Subject": "First entry", "Category": ["Cat 1", "Cat 2"], "Status": "Started"},
            text = "Log 1 entry 1",
        )
        cls.entry2 = Entry(
            lb=cls.lb1,
            id=2,
            date=timezone.make_aware(datetime(2025,1,1,9,0,0)),
            attrs={"Subject": "Second entry", "Category": ["Cat 2"], "Status": "Done"},
            text = "Log 1 entry 2",
        )

        cls.entry_elcode = Entry(
            lb=cls.lb1,
            id=3,
            date=timezone.make_aware(datetime(2025,1,1,10,0,0)),
            attrs={"Subject": "ELCode entry", "Category": ["Cat 2"], "Status": "Done"},
            text = "This entry has fonts [font=Comic]Different font[/font][size=6]Different size[/size]" + " blah "*50, # make long enough to get shortened text tested
            encoding="elcode",
        )


        cls.entry1.save()

        # Create an entry 2 attachment for testing
        cls.att_buffer = BytesIO()
        cls.att_buffer.write(b"Test plain text file")
        cls.entry2.in_reply_to = cls.entry1
        cls.entry2.save()
        cls.attachment1 = Attachment(entry=cls.entry2)
        cls.attachment1.attachment_file.save('memory_file.txt', ContentFile(cls.att_buffer.getvalue()), save=True)
        cls.attachment1.save()
        cls.entry2.save()
        cls.entry_elcode.save()

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
            # plus more for third entry...
        )
        self.assertTrue(re.search(pattern, rstr, re.DOTALL))

    def test_logbook_entry_list(self):
        """Test html returned from listing of a log books entries"""
        url = reverse("flexelog:logbook", kwargs={"lb_name": "Log+1"})
        response = self.client.get(url)
        rstr = response.content.decode()

        # Note Reverse Sort is config'd
        pattern = (
            r"<th.*ID.*Date.*Status.*Category.*Subject.*Text.*</th>"
            r".*<tr.*3.*Done.*Cat 2.*ELCode entry.*font.*</tr>"
            r".*<tr.*2.*Done.*Cat 2.*Second entry.*Log 1 entry 2.*</tr>"
            r".*<tr.*1.*Started.*Cat 1 \| Cat 2.*First entry.*</tr>"
        )
        self.assertTrue(re.search(pattern, rstr, re.DOTALL))

    def test_entry_list_with_search_text(self):
        """Test html returned from listing of a log books entries"""
        url = reverse("flexelog:logbook", kwargs={"lb_name": "Log+1"})
        response = self.client.get(url + "?text=entry")

        # Note Reverse Sort is config'd
        self.assertContains(response, '<span class="highlight">entry</span>')

    def test_entry_detail(self):
        url = reverse("flexelog:entry_detail", kwargs={"lb_name": "Log+1", "entry_id": "2"})
        response = self.client.get(url)
        rstr = response.content.decode()
        # print(rstr)
        pattern = (
            r"<tr.*Subject:.*Second entry.*</tr>"
            r".*<tr.*Category:.*Cat 2.*</tr>"
            r".*<tr.*Status:.*Done.*</tr>"
            r".*<tr.*>.*<textarea.*>.*Log 1 entry 2.*</textarea>.*</tr>"
        )
        self.assertTrue(re.search(pattern, rstr, re.DOTALL))

    def test_entry_detail_id_not_exists(self):
        url = reverse("flexelog:entry_detail", kwargs={"lb_name": "Log+1", "entry_id": "9999"})
        response = self.client.get(url)
        self.assertContains(response, "This entry has been deleted")

    def test_entry_detail_elcode(self):
        url = reverse("flexelog:entry_detail", kwargs={"lb_name": "Log+1", "entry_id": "3"})
        response = self.client.get(url)
        rstr = response.content.decode()
        # print(rstr)
        pattern = (
            r'&lt;span style=&quot;font-family:Comic'  # why is it escaped?  But still works??
            r'.*&lt;span style=&quot;font-size:xx-large'
        )
        self.assertTrue(re.search(pattern, rstr, re.DOTALL))

    def test_reply_get(self):
        """Test a new entry updates Subject Re: preset"""
        url = reverse("flexelog:entry_detail", kwargs={"lb_name": "Log+1", "entry_id": 1})
        response = self.client.get(url + "?cmd=Reply")
        self.assertContains(response, "Re: First entry")

    def test_new_entry_post(self):
        data = {
            'cmd': 'Submit',
            'date': '2025-05-23 22:05:40',
            'Status': 'Started',
            'Category': ['Cat 2'],
            'Subject': 'Test edit',
            'page_type': 'New',
            'attr_names': 'Status,Category,Subject',
            'edit_id': '',
            'reply_to': '',
            'text': 'Test New entry',
        } | empty_attachment_data
        url = reverse("flexelog:logbook", kwargs={"lb_name": "Log+1"})
        response = self.client.post(url, data=data)

        # check entry in db created
        lb = Logbook.objects.get(name="Log 1")
        entry = lb.entries.last()

        self.assertEqual(entry.attrs, {'Status': 'Started', 'Category': ['Cat 2'], 'Subject': 'Test edit'})
        self.assertEqual(entry.text, data['text'])
        self.assertEqual(entry.id, 4)

    def test_entry_delete(self):
        """Delete a new entry that has an attachment"""
        entry = Entry(
            lb=self.lb1,
            id=42,
            date=timezone.make_aware(datetime(2025,1,1,10,42,0)),
            attrs={"Subject": "Gonna delete me", "Category": ["Cat 2"], "Status": "Done"},
            text = "This entry has an attachment",
            encoding="plain",
        )
        entry.save()
        attachment1 = Attachment(entry=entry)
        attachment1.attachment_file.save('delete-me.txt', ContentFile(self.att_buffer.getvalue()), save=True)
        attachment1.save()
        url = reverse("flexelog:entry_detail", kwargs={"lb_name": "Log+1", "entry_id": 42})
        response = self.client.post(url, data={"cmd": "Delete", "confirm": "Yes"})

