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
    """Keep diagnostics and spend spare space on their surrounding lines.

    Preserve the legacy suffix when every diagnostic is already in that suffix.
    Otherwise grow context around *all* diagnostics, rather than sampling twelve
    anchors or returning tiny windows while most of the budget remains unused.
    This is a bounded excerpt, not a guarantee that an arbitrarily large log fits.
    """
    if limit < 0:
        raise ValueError('character limit must be nonnegative')
    if len(text) <= limit:
        return text
    lines = text.splitlines(keepends=True)
    anchors = [i for i, line in enumerate(lines) if DIAGNOSTIC.search(line)]
    if not anchors:
        return head_tail(text, limit)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    if offsets[anchors[0]] >= len(text) - limit:
        return text[-limit:] if limit else ''
    marker = '\n' + MARKER + '\n'
    selected = set(anchors) | set(range(min(3, len(lines))))
    selected.update(range(max(0, len(lines) - 3), len(lines)))

    def render():
        out = []
        previous = -1
        for i in sorted(selected):
            if previous >= 0 and i != previous + 1:
                out.append(marker)
            out.append(lines[i])
            previous = i
        return ''.join(out)

    used = len(render())
    if used > limit:
        # Even bare diagnostics cannot all fit. Mark that loss, never silently
        # claim complete coverage or allocate a negative budget.
        return head_tail(render(), limit)
    import heapq
    pending = [(0, i) for i in selected]
    heapq.heapify(pending)
    visited = set(selected)
    while pending:
        distance, i = heapq.heappop(pending)
        for j in (i - 1, i + 1):
            if not 0 <= j < len(lines) or j in visited:
                continue
            visited.add(j)
            left, right = j - 1 in selected, j + 1 in selected
            change = len(lines[j]) + (0 if left != right else (-len(marker) if left else len(marker)))
            if used + change <= limit:
                selected.add(j)
                used += change
                heapq.heappush(pending, (distance + 1, j))
    return render()
