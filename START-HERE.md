# Resume AgenticArch

1. Read [SESSION-HANDOFF](docs/SESSION-HANDOFF.md), [OWNER-REQUIREMENTS](docs/OWNER-REQUIREMENTS.md) and [RUNTIME](docs/RUNTIME.md).
2. On the workstation run `aa doctor` and `aa status -a`; check `git status` and the remote head.
3. Run `python3 -m unittest discover -s tests` and `python3 tools/check_kit.py` before and after changes.
4. Work on a branch, open a PR per milestone; never force-push over other work.
5. At closeout update SESSION-HANDOFF, IMPLEMENTATION-STATUS and DECISIONS with what actually ran.

Never commit credentials, case content, private chat links or customer data; cases belong in the private case repo.
