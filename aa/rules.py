"""Deterministic keyword decider: the zero-cost baseline for tier and peer votes.

Same interface as aa.semif.SemIf / aa.clm.CLM. Rules follow eval/README.md's
labelling guide (written from the guide, tuned on the dev split only). Order:
tough > medium_tough > routine > bounded (default). Peer: opus for UI/visual/writing
work, else astra.
"""
from __future__ import annotations

import json
import re
from typing import Mapping

from .db import DB

TOUGH = [
    r'\bdesign (?:the|a|an|how|our)\b', r'\barchitect', r'\bstrategy\b', r'\bresearch\b', r'\bmigrat',
    r'\bplan (?:the|and|changing|how)\b', r'\bthreat[- ]model', r'\bdecide whether\b', r'\bevaluate whether\b',
    r'\bdecision document\b', r'\bsurvey\b', r'\binvestigate (?:why|across)\b', r'\bpropose\b', r'\bcompliance\b',
    r'\broadmap\b', r'\bbuild or buy\b', r'\bactive-active\b', r'\bchoose between\b', r'\bpermission model\b',
    r'\bkey rotation\b', r'\bpermanently delete\b', r'\bmulti-tenant\b', r'\bexactly-once\b',
    r'\bplugin system\b', r'\bscaling architecture\b', r'\bopen-source our\b', r'\bpricing model\b',
]
MEDIUM = [
    r'\brace\b', r'\bconcurren', r'\bleak\b', r'\bp9[59]\b', r'\bspeed up\b', r'\bslow\b', r'\bidempotent\b',
    r'\batomic\b', r'\bflaky\b', r'\brefactor\b', r'\bport the\b', r'\btracing\b', r'\brate limit',
    r'\boptimistic locking\b', r'\bvirtualiz', r'\bresponsive\b', r'\baccessib', r'\banimat', r'\bdrag-and-drop\b',
    r'\bdrag\b', r'\bsynthesis\b', r'\bcompare\b', r'\banaly[sz]e\b', r'\breconcile\b', r'\bexplainer\b',
    r'\bpkce\b', r'\boauth', r'\bshard', r'\bparser\b', r'\bconsistent-hashing\b', r'\bdeterministic\b',
    r'\bduplicat\w+ rows\b', r'\bprocessed twice\b', r'\b\d+m rows\b', r'\bmaterialized\b', r'\buser guide\b',
    r'\blanding-page\b', r'\bcase study\b', r'\bonboarding flow\b', r'\brich-text\b', r'\bdashboard\b',
    r'\bmap view\b', r'\bproduct tour\b', r'\bform builder\b', r'\bpolish\b', r'\bredesign\b', r'\bcost waste\b',
]
ROUTINE = [
    r'\brename\b', r'\btypo\b', r'\bbump\b', r'\bpin \w+ to\b', r'\bfrom [\w#.:-]+ to [\w#.:-]+\b',
    r'\bremove the unused\b', r'\bdelete the commented', r'\bto \.gitignore\b', r'\bformatter\b',
    r'\bspelling\b', r'\btranslate\b', r'\bsort the\b', r'\bround all\b', r'\breplace every\b', r'\bshorten\b',
    r'\bconvert (?:the|this)\b', r'\bcopyright year\b', r'\bpage title\b', r'\bplaceholder text\b',
    r'\badd a debug log\b', r'\bmissing link\b', r'\bput today',
]
OPUS = [
    r'\bui\b', r'\bfrontend\b', r'\bpage\b', r'\blayout\b', r'\bresponsive\b', r'\banimat', r'\bcss\b',
    r'\bdesign system\b', r'\baccessib', r'\bdrag', r'\bonboarding\b', r'\blanding', r'\bcopy\b', r'\bwrite\b',
    r'\bguide\b', r'\bnarrative\b', r'\bvisual', r'\bmap view\b', r'\btour\b', r'\bform builder\b',
    r'\bmobile layout\b', r'\beditor\b', r'\bempty states\b', r'\billustration', r'\bkanban\b', r'\bchart\b',
    r'\binterview notes\b', r'\bcheckout\b', r'\btable\b.*\b(?:rows|sticky)\b', r'\bexplainer\b', r'\bscreens?\b',
]


def _hits(patterns: list[str], text: str) -> int:
    return sum(1 for p in patterns if re.search(p, text, re.I))


def tier_of(text: str) -> str:
    if _hits(TOUGH, text):
        return 'tough'
    if _hits(MEDIUM, text):
        return 'medium_tough'
    if _hits(ROUTINE, text):
        return 'routine'
    return 'bounded'


def peer_of(text: str) -> str:
    return 'opus' if _hits(OPUS, text) else 'astra'


class Rules:
    backend = 'rules'

    def __init__(self, cfg=None, db: DB | None = None):
        self.db = db

    def available(self) -> bool:
        return True

    def choose(self, kind: str, task_id: str | None, state: str, question: str,
               options: Mapping[str, str]) -> tuple[str | None, dict | None, int]:
        pick = tier_of(state) if kind == 'tier' else peer_of(state) if kind == 'peer' else None
        probs = {k: (1.0 if k == pick else 0.0) for k in options} if pick in options else None
        did = self.db.decision(kind, task_id, state, dict(options), probs, pick, None) if self.db else 0
        return (pick if probs else None), probs, did

    def rank(self, task_id, context: str, question: str, candidates: list[str], k: int) -> list[str]:
        words = {w.lower() for w in re.findall(r'[A-Za-z_]{4,}', context)}
        ranked = sorted(candidates, key=lambda c: -sum(w in c.lower() for w in words))[:k]
        if self.db:
            self.db.decision('context', task_id, context[:4000], {'candidates': candidates}, None,
                             None, json.dumps(ranked))
        return ranked
