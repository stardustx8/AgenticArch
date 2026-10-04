"""Decision wordings shared by the runtime and tools/eval_decisions.py.

Semantic deciders are sensitive to how options are phrased, so every wording is a
named variant; the benchmark picks one per backend on the dev split (see
eval/README.md and the latest report in eval/results/).
"""
from __future__ import annotations

TIERS = ['routine', 'bounded', 'medium_tough', 'tough']

TIER_OPTIONS = {
    'short': {
        'routine': 'A trivial edit: rename, typo, config value or one-line change.',
        'bounded': 'A normal bug fix or small feature in a few files.',
        'medium_tough': 'A hard bug or complex change spanning several interacting modules.',
        'tough': 'A new architecture, system design, research or migration plan.',
    },
    'guide': {
        'routine': 'A narrow mechanical change with a known contract: rename, config tweak, one-place fix, formatting, trivial documentation.',
        'bounded': 'A substantive but bounded implementation or debugging task inside the existing design: one feature or bug across a few files with clear acceptance.',
        'medium_tough': 'Medium-tough implementation inside an existing or approved design: several interacting components, non-obvious logic, concurrency, performance or hard debugging, but no new architecture.',
        'tough': 'Tough work: architecture or system design, research, security design, data migration design, irreversible changes, or a problem whose approach is unclear.',
    },
    'work': {
        'routine': 'Trivial mechanical work such as renaming, fixing typos, changing a value, reformatting or converting a document.',
        'bounded': 'Ordinary work with a clear result such as a small feature, a bug fix with a test, summarizing a document or drafting an email.',
        'medium_tough': 'Difficult work inside a known approach such as concurrency or performance problems, multi-module changes, or careful synthesis of several sources.',
        'tough': 'Open-ended design or research such as system architecture, migrations, security design, strategy or decisions with long-term consequences.',
    },
    'effort': {
        'routine': 'Minutes of mechanical work; no judgement needed.',
        'bounded': 'An hour or two of normal work with an obvious approach.',
        'medium_tough': 'A day of careful expert work; the approach is known but the details are hard.',
        'tough': 'The approach itself must be designed or researched before any work starts.',
    },
}
TIER_QUESTIONS = {
    'difficulty': 'How difficult is this task?',
    'lowest': 'Which tier of worker should handle this request? Pick the lowest tier that can do it well.',
}

PEER_OPTIONS = {
    'models': {
        'astra': 'GPT-6 Astra: strong at backend logic, systems code, algorithms, data, infrastructure and debugging.',
        'opus': 'Claude Opus 5.5: strong at frontend, UI, visual and interaction design, product thinking and writing.',
    },
    'worktype': {
        'astra': 'Backend, systems, algorithms, data, infrastructure or debugging work.',
        'opus': 'Frontend, user interface, visual, interaction, product or writing work.',
    },
}
PEER_QUESTIONS = {
    'fit': 'Which worker fits this task best?',
    'kind': 'What kind of work is this mainly?',
}

# Winners on the dev split (2026-09-25 benchmark; test results in eval/results/).
CHOSEN = {
    'semif': {'tier': ('work', 'difficulty'), 'peer': ('models', 'fit')},
    'clm': {'tier': ('effort', 'lowest'), 'peer': ('worktype', 'kind')},
}
# Peer choice selects the MODEL only; effort per peer is fixed (owner, 2026-09-25).
PEER_LANES = {'astra': 'astra_high', 'opus': 'opus_high'}


def tier_question(backend: str) -> tuple[str, dict[str, str]]:
    o, q = CHOSEN[backend]['tier']
    return TIER_QUESTIONS[q], TIER_OPTIONS[o]


def peer_question(backend: str) -> tuple[str, dict[str, str]]:
    o, q = CHOSEN[backend]['peer']
    return PEER_QUESTIONS[q], PEER_OPTIONS[o]
