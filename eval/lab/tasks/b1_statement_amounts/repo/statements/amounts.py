from decimal import Decimal, InvalidOperation


def parse_amount(text):
    """Parse a money amount like '$1,234.56' into a Decimal."""
    cleaned = text.strip().replace("$", "").replace(",", "")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"invalid amount: {text!r}") from None
