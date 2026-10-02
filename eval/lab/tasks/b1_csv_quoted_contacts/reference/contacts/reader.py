import csv
import io


def read_contacts(text):
    """Parse CSV text (first row is the header) into a list of dicts.

    Standard CSV quoting is honoured, a leading UTF-8 BOM is ignored and
    blank lines are skipped.
    """
    if text.startswith("\ufeff"):
        text = text[1:]
    header = None
    rows = []
    for record in csv.reader(io.StringIO(text, newline="")):
        values = [v.strip() for v in record]
        if not any(values):
            continue
        if header is None:
            header = values
            continue
        rows.append(dict(zip(header, values)))
    return rows
