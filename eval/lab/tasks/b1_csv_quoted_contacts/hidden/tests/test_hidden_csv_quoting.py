import unittest

from contacts.importer import import_contacts
from contacts.reader import read_contacts


class QuotedFieldsTest(unittest.TestCase):
    def test_comma_inside_quotes(self):
        text = 'name,email\n"Smith, John",john@example.com\n'
        self.assertEqual(read_contacts(text), [{"name": "Smith, John", "email": "john@example.com"}])

    def test_escaped_quotes(self):
        text = 'name,email\n"Dwayne ""The Rock"" Johnson",rock@example.com\n'
        self.assertEqual(read_contacts(text)[0]["name"], 'Dwayne "The Rock" Johnson')

    def test_newline_inside_quotes(self):
        text = 'name,email,notes\nAnn,ann@example.com,"line one\nline two"\nBob,bob@example.com,\n'
        rows = read_contacts(text)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["notes"], "line one\nline two")
        self.assertEqual(rows[1], {"name": "Bob", "email": "bob@example.com", "notes": ""})

    def test_quoted_header(self):
        text = '"name","email"\n"Ann","ann@example.com"\n'
        self.assertEqual(read_contacts(text), [{"name": "Ann", "email": "ann@example.com"}])

    def test_crlf_line_endings(self):
        text = 'name,email\r\n"Lee, Ann",ann@example.com\r\n'
        self.assertEqual(read_contacts(text), [{"name": "Lee, Ann", "email": "ann@example.com"}])


class BomTest(unittest.TestCase):
    def test_bom_stripped_from_first_header(self):
        rows = read_contacts("\ufeffname,email\nAnn,ann@example.com\n")
        self.assertEqual(rows, [{"name": "Ann", "email": "ann@example.com"}])

    def test_bom_with_quoted_header(self):
        text = '\ufeff"name","email"\n"Smith, John",john@example.com\n'
        self.assertEqual(read_contacts(text), [{"name": "Smith, John", "email": "john@example.com"}])


class ImporterQuotedTest(unittest.TestCase):
    def test_quoted_names_are_valid(self):
        text = '\ufeffname,email\n"Smith, John",john@example.com\n"O\'Neil, Pat",pat@example.com\n'
        valid, errors = import_contacts(text)
        self.assertEqual(errors, [])
        self.assertEqual([r["name"] for r in valid], ["Smith, John", "O'Neil, Pat"])

    def test_row_numbers_after_quoted_rows(self):
        text = 'name,email\n"Smith, John",john@example.com\n"Doe, Jane",not-an-email\n'
        valid, errors = import_contacts(text)
        self.assertEqual(len(valid), 1)
        self.assertEqual(errors[0][0], 2)


if __name__ == "__main__":
    unittest.main()
