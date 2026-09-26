from .parsing import parse_date


def days_between(start, end):
    return (parse_date(end) - parse_date(start)).days


def in_range(value, start, end):
    return parse_date(start) <= parse_date(value) <= parse_date(end)
