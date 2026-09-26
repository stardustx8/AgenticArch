"""Bounded, deterministic evidence excerpts; these are not executable patches.

Character limits are deliberately named as such: they are not tokenizer counts.
Small inputs are returned byte-for-byte (as text). No model or repository execution.
"""
from __future__ import annotations

import re
from pathlib import Path

DIAGNOSTIC = re.compile(
    r'Traceback|AssertionError|\b(?:Error|Exception):|^FAIL:|^ERROR:|^FAILED\b|'
    r'^\s*E\s|^npm ERR|panic:|^error(?:\[|:)', re.I)
MARKER = (Path(__file__).parent / 'prompts' / 'context_omitted.txt').read_text().strip()


def head_tail(text: str, limit: int) -> str:
    """Keep both ends with an explicit omission marker and a hard character cap."""
    if limit < 0:
        raise ValueError('character limit must be nonnegative')
    if len(text) <= limit:
        return text
    marker = '\n' + MARKER + '\n'
    if limit < len(marker):
        return marker[:limit]
    room = limit - len(marker)
    left = (room + 1) // 2
    return text[:left] + marker + (text[-(room - left):] if room > left else '')


def balanced_diff(text: str, limit: int) -> str:
    """Allocate the budget across changed files rather than dropping later files.

    Short file diffs get their complete allocation first. Long ones receive a
    head/tail excerpt. If even one header per file will not fit, the outer
    head/tail fallback says information is omitted instead of claiming coverage.
    """
    if limit < 0:
        raise ValueError('character limit must be nonnegative')
    if len(text) <= limit:
        return text
    starts = list(re.finditer(r'^diff --git .*$', text, re.M))
    if not starts:
        return head_tail(text, limit)
    chunks = [text[m.start():starts[i + 1].start() if i + 1 < len(starts) else len(text)]
              for i, m in enumerate(starts)]
    notice = MARKER + '\n'
    headers = [c.split('\n', 1)[0] + '\n' for c in chunks]
    minimum = sum(len(h) for h in headers) + len(notice)
    if minimum + len(chunks) * (len(MARKER) + 2) > limit:
        return head_tail(text, limit)
    available = limit - len(notice)
    allocation = [len(h) for h in headers]
    remaining = available - sum(allocation)
    active = set(range(len(chunks)))
    # Water filling: do not waste the quota of a short file on another truncated
    # header. The stable ordering makes replay independent of hash randomization.
    while remaining and active:
        share = max(1, remaining // len(active))
        for i in sorted(active):
            add = min(share, len(chunks[i]) - allocation[i], remaining)
            allocation[i] += add
            remaining -= add
            if allocation[i] >= len(chunks[i]):
                active.remove(i)
            if not remaining:
                break
    out = [notice]
    for c, h, size in zip(chunks, headers, allocation):
        body = c[len(h):]
        out.append(h + head_tail(body, size - len(h)))
    return ''.join(out)


def focused_failure(text: str, limit: int) -> str:
    """Retain diagnostic windows plus both ends, in original chronological order.

    Pure presentation: never converts a failed check into a passing one. Repeated
    diagnostics are sampled evenly if there are too many to fit; omissions are
    explicit. Lines may be clipped, so full check logs remain the source of truth.
    """
    if limit < 0:
        raise ValueError('character limit must be nonnegative')
    if len(text) <= limit:
        return text
    lines = text.splitlines(keepends=True)
    anchors = [i for i, line in enumerate(lines) if DIAGNOSTIC.search(line)]
    if not anchors:
        return head_tail(text, limit)
    # Bound the number of windows independently of adversarial log length.
    if len(anchors) > 12:
        anchors = [anchors[round(i * (len(anchors) - 1) / 11)] for i in range(12)]
    selected = set(range(min(3, len(lines)))) | set(range(max(0, len(lines) - 3), len(lines)))
    for anchor in anchors:
        selected.update(range(max(0, anchor - 1), min(len(lines), anchor + 3)))
    groups = []
    for i in sorted(selected):
        if not groups or i != groups[-1][-1] + 1:
            groups.append([])
        groups[-1].append(i)
    marker = '\n' + MARKER + '\n'
    room = limit - len(marker) * (len(groups) - 1)
    if room <= 0:
        return head_tail(text, limit)
    pieces = [''.join(lines[i] for i in group) for group in groups]
    # Give every selected window a share; small windows free space for long ones.
    allocations = [0] * len(pieces)
    active = set(range(len(pieces)))
    while room and active:
        share = max(1, room // len(active))
        for i in sorted(active):
            add = min(share, len(pieces[i]) - allocations[i], room)
            allocations[i] += add
            room -= add
            if allocations[i] >= len(pieces[i]):
                active.remove(i)
            if not room:
                break
    return marker.join(head_tail(p, n) for p, n in zip(pieces, allocations))
