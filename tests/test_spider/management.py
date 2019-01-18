from django.core.management import call_command
from django.test import TestCase
from django.utils.six import StringIO


class ManagementTests(TestCase):
    def test_update_dynamic_content(self):
        out = StringIO()
        call_command('update_dynamic_content', stdout=out)
        self.assertNotIn('invalid', out.getvalue())
