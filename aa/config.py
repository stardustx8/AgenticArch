"""Runtime configuration: defaults merged with ~/.config/agenticarch/aa.toml."""
from __future__ import annotations

import copy
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path(os.environ.get('AA_CONFIG', '~/.config/agenticarch/aa.toml')).expanduser()

DEFAULTS: dict[str, Any] = {
    'paths': {
        'state_dir': '~/.local/share/agenticarch',
    },
    'case_repo': {
        'url': 'git@github.com:stardustx8/GPT-Pro-Escalation.git',
        'slug': 'stardustx8/GPT-Pro-Escalation',
    },
    'ntfy': {
        'url': 'http://127.0.0.1:8093',
        # Address your phone uses (tailnet); action buttons post replies here.
        'public_url': 'http://100.114.173.57:8093',
        'topic': 'agenticarch',
        'reply_topic': 'agenticarch-replies',
        'enabled': True,
    },
    'decider': {
        # Local semantic decider for tier/peer votes and context ranking. SemIf won the
        # 2026-09-25 benchmark (86% vs 39% tier accuracy on the test split).
        'backend': 'semif',
        # Below this confidence (top minus mean of the rest) a vote is an abstention.
        'min_confidence': 0.2,
    },
    'semif': {
        'enabled': True,
        'socket': '~/.local/share/agenticarch/semif/run/semif.sock',
        'timeout_s': 30,
    },
    'clm': {
        'enabled': True,
        'url': 'http://127.0.0.1:8700',
        'tokenize_url': 'http://127.0.0.1:8090/tokenize',
        'encoder_model': 'qwen3-8b',
        'model': 'clm-latest',
        'max_tokens': 2048,
        'checkpoint': '~/.cache/clm/CLM_v0.1-8B.pt',
        'timeout_s': 30,
    },
    'workers': {
        'codex': '~/.local/bin/codex',
        'claude': '~/.local/bin/claude',
        'timeout_s': 3600,
        'max_parallel': 3,
    },
    'triage': {
        # Codex model that proposes the tier (read-only inspection of the repo).
        'model': 'gpt-6-luna',
        'effort': 'high',
        # codex: Codex triage decides, local decider = shadow vote + fallback (benchmark best);
        # higher_if_1: take the higher vote if 1 tier apart, ask owner on bigger gaps;
        # ask_on_disagreement: ask owner whenever Codex and the decider differ.
        'policy': 'codex',
    },
    'retry': {
        'max_passes_per_lane': 2,
        'max_total_passes': 5,
    },
    'deep': {
        'challenge_rounds': 5,
        'max_pro_reviews': 2,
        'poll_s': 60,
        'challengers': ['opus_high', 'astra_high'],
    },
    'delivery': {
        'push_branch': True,
    },
    'git': {
        'name': 'AgenticArch aa',
        'email': 'stardustx8@users.noreply.github.com',
    },
    'daemon': {
        'tick_s': 5,
    },
}


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


@dataclass
class Config:
    data: dict

    def __getitem__(self, key: str) -> dict:
        return self.data[key]

    def path(self, section: str, key: str) -> Path:
        return Path(self.data[section][key]).expanduser()

    @property
    def state_dir(self) -> Path:
        return self.path('paths', 'state_dir')

    @property
    def db_path(self) -> Path:
        return self.state_dir / 'aa.sqlite'

    @property
    def worktrees(self) -> Path:
        return self.state_dir / 'worktrees'

    @property
    def case_repo_dir(self) -> Path:
        return self.state_dir / 'case-repo'

    @property
    def logs(self) -> Path:
        return self.state_dir / 'logs'


def load(path: Path | None = None, overrides: dict | None = None) -> Config:
    data = copy.deepcopy(DEFAULTS)
    p = path or DEFAULT_PATH
    if p.exists():
        with open(p, 'rb') as fh:
            data = _merge(data, tomllib.load(fh))
    if overrides:
        data = _merge(data, overrides)
    return Config(data)
