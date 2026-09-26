import re
from decimal import Decimal, InvalidOperation

_CURRENCY_RE = re.compile(r"(?<![A-Za-z])(?:EUR|USD|GBP|CHF)(?![A-Za-z])|[€$£]", re.IGNORECASE)
_NUMBER_RE = re.compile(r"[0-9.,]*[0-9][0-9.,]*")


def _is_grouped(number: str, sep: str) -> bool:
    """True if `number` looks like 1,234,567 with `sep` as the group separator."""
    groups = number.split(sep)
    return (
        1 <= len(groups[0]) <= 3
        and all(len(g) == 3 for g in groups[1:])
        and all(g.isdigit() for g in groups)
    )


def _normalise(number: str, original: str) -> str:
    """Turn digits with '.'/',' separators into a plain Decimal literal."""
    invalid = ValueError(f"invalid amount: {original!r}")
    has_dot, has_comma = "." in number, "," in number
    if has_dot and has_comma:
        decimal_sep = "." if number.rfind(".") > number.rfind(",") else ","
        group_sep = "," if decimal_sep == "." else "."
        integer_part, _, fraction = number.rpartition(decimal_sep)
        if decimal_sep in integer_part or not fraction.isdigit() or not _is_grouped(integer_part, group_sep):
            raise invalid
        return integer_part.replace(group_sep, "") + "." + fraction
    if has_dot or has_comma:
        sep = "." if has_dot else ","
        parts = number.split(sep)
        if len(parts) > 2:
            if not _is_grouped(number, sep):
                raise invalid
            return number.replace(sep, "")
        integer_part, fraction = parts
        if not fraction.isdigit():
            raise invalid
        if len(fraction) == 3 and _is_grouped(number, sep):
            return integer_part + fraction
        return (integer_part or "0") + "." + fraction
    return number


def parse_amount(text):
    """Parse a statement amount into a Decimal.

    Handles US (1,234.56) and European (1.234,56) separators, currency symbols
    or codes before/after the number, a leading minus and accounting-style
    parentheses for negatives. A single separator followed by exactly three
    digits is treated as a thousands separator.
    """
    if text is None:
        raise ValueError("invalid amount: None")
    s = _CURRENCY_RE.sub("", text).strip()
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1].strip()
    if s.startswith("-"):
        if negative:
            raise ValueError(f"invalid amount: {text!r}")
        negative = True
        s = s[1:].strip()
    elif s.startswith("+"):
        s = s[1:].strip()
    if not _NUMBER_RE.fullmatch(s):
        raise ValueError(f"invalid amount: {text!r}")
    try:
        value = Decimal(_normalise(s, text))
    except InvalidOperation:
        raise ValueError(f"invalid amount: {text!r}") from None
    return value.copy_negate() if negative else value
