# Portable runtime loader

For Hermes or OpenClaw, load this skill by reading `SKILL.md` and then `references/methodology.md` when formulas or boundaries are needed. Run `scripts/diagnose.py` for deterministic CSV analysis and report the generated JSON/TXT/HTML paths.

For Codex and Claude Code, use the same `SKILL.md` entrypoint. Cursor uses `agents/cursor-rule.mdc`. Do not request credentials or network access: this skill is intentionally offline. Keep `normal`, `watch`, `warning`, and `insufficient_data` as research statuses, and state evidence gaps before proposing further validation.
