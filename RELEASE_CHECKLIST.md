# Release checklist — NED v0.1.0

Everything that has to happen between this commit and pressing **Publish** on
GitHub. Nothing here is code; it is the paperwork a first release needs.

---

## 1. Publication identity

| Field | Published value |
| --- | --- |
| GitHub owner | [`Sh1oud`](https://github.com/Sh1oud) |
| Repository | [`Sh1oud/NED`](https://github.com/Sh1oud/NED) |
| Conduct / enforcement contact | `zhaoyizhuoying@icloud.com` |

The release-hygiene test fails if an unresolved publication token appears in any
project file.

- [x] Repository URLs, badge, clone instructions and FastAPI contact use `Sh1oud/NED`
- [x] Conduct contact is configured in `CODE_OF_CONDUCT.md`
- [x] No unresolved publication token remains

## 2. Screenshots

Four images are referenced by the README and captured from the real UI/CLI; each
image prints the engine version it was captured from.

```bash
ned serve --port 8742                       # terminal 1
python scripts/capture_screenshots.py       # terminal 2
```

- [x] `docs/screenshots/analysis.png` — Analyze tab, extreme mode, populated report
- [x] `docs/screenshots/asymmetry.png` — Asymmetry Detector, the canonical pair
- [x] `docs/screenshots/fnbp-lab.png` — Lab tab, branch-predictor log
- [x] `docs/screenshots/cli-extreme.png` — real CLI output for `ned analyze "她说喜欢我" --mode extreme`
- [x] README "Status" column names the captured images
- [x] `docs/cli-extreme.txt` matches the current CLI output (`ned analyze "她说喜欢我" --mode extreme`)

Never commit a mockup or a doctored image: the screenshots are evidence about the
UI, and a reviewer will compare them against the running app.

## 3. Quality gates (all four must be green)

```bash
pytest -q
ruff check .
ruff format --check .
mypy ned
```

- [x] `pytest -q` — 224 tests pass
- [x] `ruff check .` — clean
- [x] `ruff format --check .` — clean
- [x] `mypy ned` — clean
- [ ] CI (`.github/workflows/test.yml`) is green on both `test` (3.12/3.13) and `test-windows`

## 4. Verify the running product

```bash
ned serve --port 8742
curl http://127.0.0.1:8742/api/health
curl http://127.0.0.1:8742/api/version
curl -X POST http://127.0.0.1:8742/api/analyze -H "Content-Type: application/json" -d '{"text":"我想你了","mode":"extreme"}'
curl -X POST http://127.0.0.1:8742/api/asymmetry -H "Content-Type: application/json" -d '{"positive_text":"她主动找我聊了两个小时","negative_text":"五分钟没回复"}'
python scripts/verify_http.py 8742

ned version
ned analyze "我想你了"
ned analyze "她说喜欢我" --mode extreme
ned asymmetry --positive "她主动找我聊了两个小时" --negative "五分钟没回复"
ned demo
```

- [ ] All four endpoints answer 200 with the documented shapes
- [ ] `ned demo` runs every example case and exits 0
- [ ] `/` renders with no unrendered Jinja placeholders

## 5. Clean install from scratch

Proves the wheel ships its data files (rule packs, templates, static assets,
examples) and that the console script works outside the source tree.

```bash
python -m venv .venv-clean          # disposable; delete it when done
# Windows: .venv-clean\Scripts\Activate.ps1  |  macOS/Linux: source .venv-clean/bin/activate
pip install .                   # NOT -e: a real wheel install
cd /tmp && ned version && ned analyze "我想你了"
```

- [ ] `import ned` works outside the project directory
- [ ] `ned/app/rules/*.json`, `templates/index.html`, `static/*` and `examples/cases.json` are all present after install
- [ ] `ned version`, `ned analyze`, `ned serve` work from an unrelated working directory

## 6. Repository hygiene

- [ ] `git status --short` is clean
- [ ] No generated artefacts staged: `__pycache__/`, `*.pyc`, `*.egg-info/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `.coverage`, `.tmp/`, `.venv*/`
- [ ] `git ls-files | wc -l` matches the expected file set (70 files at the RC commit)
- [ ] `LICENSE` year and holder are correct
- [ ] `CHANGELOG.md` has the real release date on `## [0.1.0]`

## 7. GitHub repository setup

- [ ] Repository created, default branch `main`
- [ ] Description: `NED — Nov1ce Evidence Denier: an offline, satirical emotional evidence de-weighting engine.`
- [ ] Topics: `satire`, `python`, `fastapi`, `cognitive-bias`, `cli`, `offline`, `no-telemetry`
- [ ] License recognised as MIT
- [ ] Actions enabled (the workflow uses only GitHub-hosted runners)
- [ ] Issues enabled; the two issue templates render correctly
- [ ] "Require status checks to pass" enabled for `test` and `test-windows` if branch protection is desired
- [ ] Social preview set (optional)

## 8. Tag and publish

```bash
git tag -a v0.1.0 -m "NED v0.1.0 — Nov1ce Evidence Denier"
git push origin main --tags
```

- [ ] Release title: `NED v0.1.0 — Nov1ce Evidence Denier`
- [ ] Release body taken from the `## [0.1.0]` section of `CHANGELOG.md`
- [ ] Release notes repeat the disclaimer: NED cannot determine whether someone likes you; it is satire, not a psychological instrument
- [ ] Badge URLs in `README.md` resolve (they only work once the repo is public)

## 9. Things this release does *not* do (keep them out of the announcement)

- No LLM, no external API, no database, no accounts, no telemetry. `LLMProvider` is a
  declared stub that raises on use.
- No claim about anyone's real feelings, anywhere in the output or the docs.
- Fuyuki is a fictional internal codename, not a real person.

---

Last verified: 2026-09-13, on Windows 11 / Python 3.13.15, commit at the RC cut
(`pytest` 224 passed, `ruff` clean, `mypy` clean, live HTTP and CLI checks green).

---

## 10. v0.1.7 Comedy Recovery — closing record

Recorded at the release candidate cut. Nothing here replaces the checks above;
it is the evidence for this particular version.

| Check | Result |
| --- | --- |
| Version identity | `__version__ = "0.1.7"`, `/api/health` and `/api/version` report it |
| Tests | see `## [0.1.7]` in `CHANGELOG.md`; full suite green at the RC commit |
| Rule pack | 38 signals, unchanged shapes; three guards added, no new family |
| Boundary safety | `明确边界。NED 停止狡辩。🚧`, no comedy on boundary or hostile screens |
| Clean install | launcher created a fresh `.venv` from the extracted ZIP and served the UI |
| First screen | representative screens verified in `normal` mode through the real CLI and web assets |

Release name: **NED v0.1.7 — Comedy Recovery**

---

## 11. v0.1.8 Release Closing

Documentation closing only. Nothing in this section re-opens behaviour: v0.1.8 is at
functional freeze, and the items below are recorded facts from the Final Integration
Review.

| Check | Result |
| --- | --- |
| Version identity | `__version__ = "0.1.8"`, bumped in this closing; `/api/health` and `/api/version` report it |
| Stage 1 commit | `2c13b84` — `feat: add alternative explanation audit` |
| Stage 2 commit | `fc3356c` — `feat: add multiple aspects presentation` |
| Final Integration Review | passed (mission review, personality review, Stage 1 x Stage 2 mixed matrix) |
| Tests | 1054 passed, 0 failed |
| Lint / types | `ruff check` clean, `ruff format --check` 67 files, `mypy ned` 30 files |
| Render parity | 114/114 personality, 64/64 NEA, 20/20 layers |
| Copy safety scan | 571 strings, 0 hits |
| Hard lines | 3 original + 2 v0.1.8 lines verified on real inputs |
| Behaviour delta vs v0.1.7 | 4 R1/R2 recognition inputs, 2 Explanation Audit, 4 Multiple Aspects; 0 unclassified; 0 verdict changes |
| Boundary safety | 16 boundary inputs, first screen unchanged; second material recorded underneath only |
| Documentation closing | performed: README (declaration, stale examples, v0.1.8 section, features, architecture, API), CHANGELOG, PERSONALITY_BIBLE, this record |

Not part of this closing (left for the Release Candidate / Release phase):

- `main` update
- tag creation
- artifact build
- release publication

Release name: **NED v0.1.8 — Alternative Explanation Audit & Multiple Aspects**

## 12. v0.1.9 Release Preparation

Hard-line maintenance release. Two fixes only: a hedged or hypothetical rejection
claim is an inference rather than a stated boundary, and a stated relationship
boundary is recognised so that a positive or comedic screen cannot cover it.

| Check | Result |
| --- | --- |
| Version identity | `__version__ = "0.1.9"`, bumped in this preparation; `/api/health` and `/api/version` report it |
| CG-7 commit | `4dc9f9b` — `fix: keep uncertain rejection claims out of explicit boundaries` |
| CG-3 commit | `8b30b55` — `fix: recognize explicit relationship boundaries` |
| Production surface | `ned/app/rules/signals.json` only, rule `zh.direct_rejection`: patterns 15 -> 18, exclude 27 -> 30; the other 37 rules byte-identical |
| Measured change set | 36 boundary gains over the audit inputs, 0 losses; 306-input sweep, 50-input playtest and 551-input pool all unchanged |
| Full gates | pytest, ruff check, ruff format --check, mypy, personality/nea/layers render, copy-safety scan all clean |
| Not part of this preparation | commit, push, tag creation, artifact upload, release publication |

Release name: **NED v0.1.9 — Hard-line Maintenance**

## 13. v0.1.10 Release Preparation

Front Desk Renewal, the boundary-ownership and material-layer corrections merged after `v0.1.9`,
and one quoted-boundary fix. The local page reads as a service hall whose copy comes from the
shared catalogue (shell, intake window, staged material registry, review record, serious
register, issuance stamp), and an explicit boundary written inside the corner brackets
`「」`/`『』` is recognised again instead of dropping out of the boundary family and leaking the
fragment it negates as a positive page. The version source moves to `0.1.10`; `API_VERSION`
stays `1` because no REST contract changed.

| Check | Result |
| --- | --- |
| Version identity | `__version__ = "0.1.10"`; `/api/health`, `/api/version` and the web badge report it |
| Version pin | `tests/test_packaging.py` asserts the single-source version, updated with the bump |
| Front-desk commits | `9dc776d` shell/intake, `625218a` staged registry, `08d6f24` dossier rhythm, `74accbd` serious register, `47cbd95` terminal verdict, `1ab2c13` responsive/accessibility, `8c0188d` catalogue copy, `a0ea854` quoted-boundary fix |
| Production surface | `ned/app/static/{app.js,style.css}`, `ned/app/templates/index.html`, `ned/app/ui/personality.py`, `ned/app/core/boundary.py`, `ned/app/rules/signals.json`; the boundary fix touches only the quote set and the boundary rule's own quote class |
| Full gates | pytest 1981, ruff check, ruff format --check (90 files), mypy, release-hygiene, docs checks, README claims, reference audit all clean |
| Semantic gates (RH-4 range) | against the RH-3 tip: 9819-input corpus `0/9471` unchanged, ownership matrices 0 changed (240 core 0, COMPOSITE-CONCAT-1 = 18), AS-2 0, material rewire 50/0, report-head eligibility 0, CLI JSON contract 0/0 |
| Release delta vs `v0.1.9` | contract: `engine.version` on every case plus one semantic case (`她只是善良`, `ned.no_signal` -> `ned.self_discount_noted`); `matrix_all` 29/77 rows move, every one a self-discount verdict; corpus 6,050/9,471 rows differ and every row is accounted for by the engine's own taxonomy — 3,433 copy-only, 1,983 situation transitions, 99 boundary-span extensions, 5 contained-fragment removals, 530 same-situation re-scores (measured this preparation; the full row-by-row evidence is kept with the batch records) |
| Documentation truthfulness | version samples read 0.1.10; the bilingual claim is scoped to what is measured; all four screenshot rows are current for 0.1.10; the 0.1.10 changelog entry carries no date, claims no publication, and states the measured judgement-layer delta against `v0.1.9` |
| Release evidence | all four images are current at 0.1.10: the three web screenshots were re-captured from the 0.1.10 UI with each readiness gate verified before the shot, and the CLI capture was regenerated from the 0.1.10 CLI (release width, LF, trailing whitespace stripped — environment-only) before its image was re-rendered and placed |
| Release executor | `_rc/rh4/release_0110_execute.py` with stages `local / artifact / smoke / remote / rehearse` (read-only, all executed) and `main / push-main / tag / push-tag / release / verify` (implemented, not executed); runbook `_rc/rh4/RELEASE_RUNBOOK_v0.1.10.md` |
| Source archive | built from the release commit, verified entry-for-entry and byte-for-byte against that commit's tree, reproduced twice with identical sha256; facts recorded in `_rc/rh4/artifact_0110.json` |
| Not part of this preparation | commit, push, tag creation, artifact upload, release publication, and any deferred capability work |

### Deferred and compatibility boundaries recorded for this release

| Item | Status |
| --- | --- |
| English reported-material / report-frame layer | **Unsupported** (deferred); an English reported negative is read as the reader's own conclusion |
| Quote perspective (`AS2-QUOTE-1`) | Registered, not fixed |
| Report-act expansion (`MATERIAL-REPORT-ACT-EXPANSION-CANDIDATE`) | Registered, not fixed (capability) |
| Reader-firewall whitespace residue (`READER-WS-FIREWALL-1`) | Registered, not fixed |
| `MATERIAL-SPEECH-VERBS-SCHEMA-COMPAT-1` | **Deliberately kept** rule-pack schema shim, not dead code |
| `COMPOSITE-CONCAT-1 = 18` | **Fixed compatibility baseline**, not 18 new regressions |
| Bare imperatives (`别烦我`, `滚出去`, `Do not contact me again`) | POLICY A: no speaker, so they belong to the reader; only framed refusals certify her boundary |
| Automated real-browser regression | **None**; real-UI evidence is per-batch browser runs plus the capture script |
| Capture tooling debts | Readiness hooks fixed; out-dir / canvas padding / status note open |
| Front-desk cosmetics | Mobile directory swipe, 10.2-10.6 px label register, 26 px nested disclosure hit area: recorded, not fixed |

Release name: **NED v0.1.10 — Front Desk Renewal** (prepared, not yet published)
