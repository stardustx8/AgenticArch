from dataclasses import dataclass
from decimal import Decimal

from .grouping import group_by
from .money import format_money, round_cents


@dataclass(frozen=True)
class ReportLine:
    group: tuple
    count: int
    total: Decimal


@dataclass(frozen=True)
class Report:
    keys: tuple
    currency: str
    lines: list
    grand_total: Decimal


def build_report(transactions, keys, rates):
    """Total converted amounts per group; ``rates`` converts into the report currency."""
    keys = tuple(keys)
    grouped = group_by(transactions, keys)
    lines = []
    for group in sorted(grouped):
        rows = grouped[group]
        total = sum((round_cents(rates.convert(t.amount, t.currency)) for t in rows), Decimal(0))
        lines.append(ReportLine(group, len(rows), total))
    grand = sum((line.total for line in lines), Decimal(0))
    return Report(keys, rates.base, lines, grand)


def render_report(report):
    header = ' / '.join(report.keys)
    out = [f'{header}: count, total ({report.currency})']
    for line in report.lines:
        label = ' / '.join(line.group)
        out.append(f'{label}: {line.count}, {format_money(line.total, report.currency)}')
    count = sum(line.count for line in report.lines)
    out.append(f'TOTAL: {count}, {format_money(report.grand_total, report.currency)}')
    return '\n'.join(out)
