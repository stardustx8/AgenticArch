import unittest

from contacts.importer import import_contacts
from contacts.reader import read_contacts


class ReaderTest(unittest.TestCase):
    def test_basic(self):
        text = "name,email\nAnn,ann@example.com\nBob,bob@example.com\n"
        self.assertEqual(
            read_contacts(text),
            [{"name": "Ann", "email": "ann@example.com"}, {"name": "Bob", "email": "bob@example.com"}],
        )

    def test_blank_lines_and_whitespace(self):
        text = "name , email\n\n  Ann , ann@example.com \n"
        self.assertEqual(read_contacts(text), [{"name": "Ann", "email": "ann@example.com"}])

    def test_empty(self):
        self.assertEqual(read_contacts(""), [])


class ImporterTest(unittest.TestCase):
    def test_errors_reported_with_row_number(self):
        text = "name,email\nAnn,ann@example.com\n,nobody\n"
        valid, errors = import_contacts(text)
        self.assertEqual(len(valid), 1)
        self.assertEqual(errors[0][0], 2)
        self.assertIn("missing name", errors[0][1])


if __name__ == "__main__":
    unittest.main()
