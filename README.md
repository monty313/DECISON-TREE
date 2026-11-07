# DECISON-TREE

## Project mission
Build and maintain the DECISON TREE project with reliable setup, execution, and delivery workflows.

## What this repository currently contains
Top-level structure:
- `.gitattributes` (file)
- `.gitignore` (file)
- `AGENT_PROMPT.md` (file)
- `archive` (dir)
- `DTResources` (dir)
- `FINALIZATION_PLAN.md` (file)
- `framework` (dir)
- `ftmo_dt_bot` (dir)
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
- `us30_rf_bot.py` (file)

Primary languages/tooling detected: Python (33), Markdown (18), MQL5 (2), Jupyter Notebook (1)

Likely key implementation files:
- `README.md`

## Quickstart (operator + LLM friendly)
Use this sequence first, then adapt to repo-specific details.

1. Clone and enter repo:
   ```bash
   git clone https://github.com/monty313/DECISON-TREE.git
   cd DECISON-TREE
   ```
2. Setup environment/dependencies:
   ```bash
   Inspect dependencies from project files before first run.
   ```
3. Run locally:
   ```bash
   Run the main entrypoint/script discovered in the repository structure.
   ```
4. Validate changes:
   ```bash
   Run the repository test command once identified (or add one if missing).
   ```

## Operating intent (CEO-mode guide for future LLMs)
When continuing this project, optimize for business outcome first:

- Preserve or improve strategy quality, reliability, and reproducibility.
- Prefer small, testable, reversible changes over broad rewrites.
- Keep docs synchronized with code behavior.
- Add explicit assumptions, constraints, and success criteria in every major change.

## Delivery checklist
- [ ] Environment setup is deterministic.
- [ ] Primary run path is documented and works.
- [ ] Validation/test path is documented and works.
- [ ] Key risks and TODOs are tracked in the handoff file.

## Branch and release notes
- Default branch: `main`
- Keep PRs focused and attach proof-of-run or proof-of-test for behavior changes.
