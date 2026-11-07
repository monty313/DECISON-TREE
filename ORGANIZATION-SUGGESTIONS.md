# ORGANIZATION-SUGGESTIONS

Repository: `monty313/DECISON-TREE`
Date: `2026-11-07`

## Purpose-aligned opinion
Production-ready software project with clear separation between core logic, interfaces, and operations.

## Current snapshot (for orientation)
Detected primary languages: **Python, MQL5, Notebook**

Top-level entries seen:
- `.gitattributes` (file)
- `.gitignore` (file)
- `AGENT_PROMPT.md` (file)
- `archive` (dir)
- `DTResources` (dir)
- `FINALIZATION_PLAN.md` (file)
- `framework` (dir)
- `ftmo_dt_bot` (dir)
- `HANDOFF-2026-11-07.md` (file)
- `HANDOFF_IRAC.md` (file)
- `how to use momentum.md` (file)
- `PROGRESS.md` (file)
- `README.md` (file)
- `report.html` (file)
- `runner_config.json` (file)
- `s11.py` (file)
- `s11_diag.py` (file)
- `S11_Runner.mq5` (file)
- `s11_stage1.json` (file)
- `s11_stage2.json` (file)

## Recommended target structure
```text
DECISON-TREE/
  experts/             # Expert Advisors (.mq5)
  indicators/          # custom indicators (.mq5)
  include/             # shared MQL5 headers/helpers
  configs/             # symbol/timeframe/parameter presets
  tests/               # strategy tester scenarios + expected metrics
  docs/                # deployment + broker setup instructions
  scripts/             # export/import and utility tooling
```

## Why this structure fits this repo
- Separates **core logic** from **operations/configuration**, reducing rework when context is lost.
- Improves onboarding for both humans and LLMs by making intent obvious from file location.
- Makes testing and deployment more deterministic by standardizing run and validation paths.

## Priority reorganization backlog
- [ ] Lock one canonical run path (single command for local start and single command for validation).
- [ ] Move mixed experimental files into clearly named modules by responsibility.
- [ ] Centralize configuration and remove hardcoded credentials/paths from code.
- [ ] Add/refresh tests for the highest-risk logic first (signals, execution, scheduling, or model outputs).
- [ ] Document architecture decisions in `docs/` and keep them current with code changes.

## Safe migration sequence
1. Create the target folders that do not exist yet (no behavioral change).
1. Relocate files in small batches while preserving imports and entrypoints.
1. Add thin compatibility wrappers for old paths if needed, then remove after validation.
1. Run current validation after each batch and record results in docs.
1. Tag the repo state once the new structure is stable.

## LLM handoff note
When revisiting this repo later, do this first:
1. Read `README.md`, `HANDOFF-2026-11-07.md`, and this file.
2. Confirm current run command and test command still work.
3. Execute one backlog item at a time and update docs in the same commit.
