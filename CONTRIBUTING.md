# Contributing

Keep the implementation small and the specifications, reference kernel and tests consistent. Separate generic reusable material from all runtime context. Add failure-path tests with each transport or state-machine change.

Run `python3 -m unittest discover -s tests -v` and `python3 tools/check_kit.py`. Add real local integration evidence separately; do not present mocks as live qualification. Respect `AGENTS.md` and do not add broad permissions or guessed model IDs.

No license has been selected for this repository. The owner should choose a license before inviting redistribution. Do not copy external code or model weights into the kit without their applicable notices and permission.
