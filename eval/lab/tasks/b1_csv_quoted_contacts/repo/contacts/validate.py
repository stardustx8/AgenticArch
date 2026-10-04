import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_contact(row):
    errors = []
    if not row.get("name"):
        errors.append("missing name")
    email = row.get("email", "")
    if not EMAIL_RE.match(email):
        errors.append(f"invalid email: {email!r}")
    return errors
