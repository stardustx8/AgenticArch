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
        # auto | sandbox | acceptEdits — see Workers.__init__ (owner choice 2026-09-26: auto).
        'claude_guard': 'auto',
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
        'max_owner_questions': 3,       # answered questions per task; then workers must decide alone
        'max_model_calls': 40,          # backstop against any runaway loop: then BLOCKED + ntfy
    },
    'deep': {
        'challenge_rounds': 5,
        'max_pro_reviews': 2,
        'poll_s': 60,
        'challengers': ['opus_high', 'astra_high'],
    },
    'local_llm': {
        # Loopback vLLM (deploy/systemd/aa-gemma.service): neutral third-family judge + test writer.
        'enabled': True,
        'url': 'http://127.0.0.1:8100',
        'model': 'gemma-4-31b',
        'timeout_s': 600,
        'max_tokens': 4096,
        # Google's recommended sampling measured best for Gemma 4 test writing (92% vs 88% valid at t=0.2;
        # eval/results/local-llm-bench.jsonl).
        'sampling': {'temperature': 1.0, 'top_p': 0.95, 'top_k': 64},
        'chat_template_kwargs': {},
    },
    'oracle_tests': {
        # Independent acceptance tests before implementation (other vendor than the implementer),
        # must fail on the base commit, read-only for workers; mutation gate after checks pass.
        'enabled': True,
        'tiers': ['bounded', 'medium_tough'],
        'author_for_race': 'gemma_local',     # neutral for both racers; falls back to luna_high
        'extra_author': 'gemma_local',        # single lane: additional independent test set
        'max_mutants': 12,
        'min_mutation_score': 0.5,
    },
    'best_of_2': {
        # Astra and Opus implement in parallel; checks decide, pairwise judge when both pass.
        'enabled': True,
        'tiers': ['medium_tough'],
        'on_escalation': True,          # a Luna task that exhausted its retries races both
        'judge_lanes': ['opus_medium', 'astra_high'],   # both vendors judge; split -> tie-break
        'tiebreak_lane': 'gemma_local',                  # neutral third family, judged in both orders
    },
    'ideas': {
        # Experimental ideas under A/B test in the harness lab (tools/lab.py); all off = baseline.
        'diff_audit': False,        # deterministic audit: test edits, new deps, debug prints, debris
        'authority_order': False,   # owner > criteria > tests > code; workers report spec_conflicts
        'impact_map': False,        # Luna-low impact map shared by the implementer(s)
        'attacker': False,          # local model writes adversarial tests after checks pass
        'defect_twins': False,      # bug fixes must look for the same defect elsewhere
    },
    'failure_triage': {
        # Failed checks: rerun once (flaky), compare with the base commit (pre-existing),
        # local decider flags environment problems (pause + ask owner) — eval/PROBES.md.
        'enabled': True,
        'min_confidence': 0.5,
    },
    'spec_check': {
        # After the checks pass, an independent reviewer judges every acceptance criterion
        # against the diff (owner decision 2026-09-26: Opus 5.5, max 3 loops, then the owner).
        # Opus medium = high = 40/40 on the blind spec probe (eval/PROBES.md), so medium.
        'enabled': True,
        'lane': 'opus_medium',
        'max_loops': 3,
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
