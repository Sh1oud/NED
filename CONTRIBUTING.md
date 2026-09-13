# Contributing to NED

Thanks for wanting to help. NED — **Nov1ce Evidence Denier** — is a fully-offline satire engine: you paste a chat message or event description, it detects possible positive-affection signals, generates alternative explanations, discounts the positive evidence, and emits a **NED Verdict** with an evidence asymmetry score.

> When reality becomes suspiciously positive, NED restores uncertainty.
>
> Everything may be affection. Everything may also be 人好. 👍

The project exists to demonstrate **interpretation space** and **evidence asymmetry in your own reasoning**. It is entertainment. It is not psychology, not diagnosis, and not mind-reading — and it must never be presented as any of those things.

## The one rule that matters most: NED is satire, keep it funny but not cruel

- Contributions must **not punch down**. Jokes target the *pattern of over-interpretation and self-denial*, never a vulnerable group, a protected characteristic, or a specific person.
- Contributions must **not be usable to justify harassment, stalking, surveillance, or pressure**. If a feature makes it easier to obsess over someone who has shown disinterest, it does not belong here.
- Contributions must **never claim to detect real feelings**. Detection output must always be phrased as *possible signals* and *alternative hypotheses*, with explicit uncertainty.
- Do not add anything that encourages uploading other people's private chat logs. Test data must be anonymized or invented.

If a change is technically clever but fails these, it will be declined. That is not a judgment on the contributor.

## Development setup

NED targets **Python 3.12+** (it is developed on 3.13). Plain `pip` inside a virtual environment is all you need — no Poetry, no uv.

```bash
git clone https://github.com/REPLACE-WITH-GITHUB-OWNER/ned.git
cd ned
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1   |   macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
```

Then the everyday loop:

```bash
pytest -q
ruff check .
ruff format --check .
mypy ned
uvicorn ned.app.main:app --reload
ned demo
```

- `pytest -q` runs the test suite in `tests/`.
- `ruff check .` and `ruff format --check .` enforce lint and formatting.
- `mypy ned` runs the type checker over the package.
- `uvicorn ned.app.main:app --reload` serves the FastAPI app (see `/api/health`, `/api/version`, `/api/modes`, and the zero-dependency web UI).
- `ned demo` runs the canned end-to-end demonstration — a good smoke test after any change.

Working offline is a hard requirement: do not add anything that phones home at import time, build time, or run time.

## How to add a rule

Detection rules and alternative-explanation ladders are **data, not code**. Almost every "NED should also catch X" issue is a JSON edit, not a Python edit.

Rule packs live in `ned/app/rules/`:

| File | Holds |
| --- | --- |
| `signals.json` | Positive-affection signal patterns (PED input) and negative signals (NEA input) |
| `theories.json` | Alternative-explanation ladders (the "maybe they're just 人好" branches) |
| `escaping.json` | Semantic escape routes and escalation tiers |
| `verdicts.json` | Verdict templates and severity bands |
| `easter_eggs.json` | Easter eggs, including FNBP |
| `asymmetry.json` | Weights and bands for the 0–100 evidence asymmetry score |

Steps:

1. Edit the relevant pack. Keep the existing schema; add new entries rather than reshaping the file.
2. Add a test in `tests/` that pins the new behavior (see `ned/examples/cases.json` for realistic inputs you may reuse or extend).
3. Keep **both Chinese and English coverage**. A rule that only fires on one language is a half-finished rule; if a language legitimately cannot express it, say so in the test or in a comment.
4. Never hardcode user-facing strings in Python when a rule pack can hold them. If you find yourself writing a literal verdict sentence in `analyzer.py`, that sentence belongs in `verdicts.json`.

Rule packs are also user-tunable at runtime, so treat them as a public interface: renaming a key or changing a value's meaning is a breaking change and belongs in the CHANGELOG.

## Adding a new explanation provider

An explanation provider supplies the alternative explanations that NED uses to discount evidence.

1. Read `ned/app/providers/base.py`. It defines the provider protocol plus the `LLMProvider` stub that v0.1 ships but never calls.
2. Implement the protocol in a new module under `ned/app/providers/` (see `local.py` for the offline reference implementation).
3. Return `AlternativeExplanation` objects. Do not return raw strings, dicts, or provider-specific payloads.
4. Register the provider in the provider registry so it can be selected by name.
5. Add tests in `tests/`, including at least one test proving the provider works with no network access.

A provider added in this version must still work fully offline. `LLMProvider` exists as a stub for future opt-in work; wiring it up is a separate, explicitly opt-in change and is not accepted as a silent default.

## Code style

- **Formatting and linting:** `ruff`, line length **100**. Run `ruff format .` before opening a PR.
- **Types:** annotate every public function, method, and module-level constant. `mypy ned` must pass.
- **Models:** use **Pydantic v2** models for all structured data crossing a function, API, or CLI boundary. No ad-hoc dicts for anything that leaves the core.
- **Dependencies:** do not add a new heavy dependency without discussing it in an issue first. The promise is local-first, fully offline, no telemetry, no analytics, no trackers, no database, no accounts, no paid APIs — a dependency that breaks any of that is a non-starter.
- **Strings:** user-facing text lives in rule packs or templates, not inline in logic.
- Keep functions small and pure where possible; scoring and asymmetry math should be trivially testable without the API layer.

## Commit message convention

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary>
```

Common types: `feat`, `fix`, `docs`, `test`, `chore`, `refactor`.

Examples:

```
feat(rules): add zh escalation tier for marriage evidence
fix(scoring): clamp asymmetry score at 100
docs(contributing): document rule pack schema
test(asymmetry): cover empty positive and negative inputs
refactor(verdict): move verdict templates into rules/verdicts.json
```

Keep the summary in the imperative mood. Reference issues in the body when relevant.

## Pull request checklist

Before requesting review, confirm:

- [ ] Tests added or updated for the change, and `pytest -q` passes.
- [ ] `ruff check .` and `ruff format --check .` pass.
- [ ] `mypy ned` passes.
- [ ] Docs / README updated if the change is user-facing.
- [ ] No new heavy dependency.
- [ ] No telemetry, analytics, trackers, or network calls added.
- [ ] Outputs remain clearly labelled as satire / alternative hypotheses.
- [ ] No real person's private messages used as test data.
- [ ] Jokes target the pattern, not people.

Small, focused PRs get reviewed fastest. If you are unsure whether an idea fits, open a feature request issue first and ask.
