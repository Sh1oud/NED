# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned

- LLM provider implementation behind an opt-in flag.
- More languages.
- Timeline / event-log analysis.
- Web UI i18n.
- Saved report export.

## [0.1.5] - 2026-09-14

### Fixed

- Verdicts: `cold_reply` and `plan_cancelled` were detected but had no verdict of
  their own, so an input that carried evidence reached the catch-all
  `ned.no_signal`, whose text claims that no evidence exists. Negative signals no
  longer fall through to the no-signal verdict.
- Web UI and CLI: the amplified reading is now framed as the interpretation under
  test ("这是 NED 正在检查的夸大解读，不是 NED 的结论。") instead of being presented
  as a finding of NED's. The boundary reality check also states that an explicit
  boundary deserves respect.

### Changed

- All five negative families share one subjective voice for the amplified reading
  ("我是不是开始觉得，……？" / "Am I starting to feel that ...?"), including the
  fallback used when a custom rule pack ships no reading of its own. An extreme
  conclusion may appear only inside that frame.
- Verdicts: added `nea.cold_reply_insufficient` (priority 36) and
  `nea.plan_cancelled_insufficient` (priority 37). Both acknowledge the observed
  signal and refuse the strong conclusion. No existing priority changed.
- `ned.no_signal` English copy widened to "No clear emotional evidence detected.
  NED stands down. 👍" so it matches the Chinese. The rule is now reached only when
  nothing at all was detected.

### Unchanged

- Detection patterns, weights, information content, the scoring model, the
  amplification formula, the asymmetry detector, the `direct_rejection` rule and
  its priority, and the REST schema. The two new verdicts reuse the existing
  `Verdict` shape, so no API field was added.

## [0.1.4] - 2026-09-14

### Added

- Rule packs: a `direct_rejection` signal type with Chinese and English rules for
  explicit rejection and boundary statements (`别烦我`, `不要再联系我`, `滚出去`,
  `离我远点`, `别再给我发消息`, `leave me alone`, …). The patterns are generative
  rather than fixed sentences, so narrative forms (`他让我滚出去别烦他了`,
  `她叫我以后不要再联系她`) and reported statements (`对方明确说不想再和我说话`)
  are covered too.
- Rule packs: the `ned.direct_rejection` verdict (warning severity) and a
  `direct_rejection` reality check, so a stated boundary is reported as a boundary.

### Fixed

- An explicitly stated refusal is no longer answered with `signal_type = none`, an
  evidence strength of zero and the `ned.no_signal` verdict. The negative pack only
  knew about reply latency, cold replies, cancelled plans and self-authored
  conclusions, so a refusal matched no rule at all. Uncertainty is not the same as
  denying clear evidence.
- A boundary is no longer reinterpreted as a fuzzy signal. The boundary verdict
  outranks the asymmetry headline, which would otherwise describe a strong refusal
  as weak negative evidence being amplified, and when there is no positive evidence
  in the input no semantic escape hypothesis is generated for it at all.

### Changed

- The new rules carry a weight of 96 and an information content of 90 — the
  deliberate mirror of the reply-latency rule (weight 90, information 5): a stated
  boundary is an observed behaviour, not an inference.
- Context exclusions keep the signal precise: word homographs (`滚烫`, `翻滚`,
  `滚去睡觉`), jokes, game talk, meta-discussion, being fired, and sentences that
  deny or question the wording (`他没有让我滚`, `他是不是想让我滚？`) are not
  boundaries.
- No other rule pack, scoring formula, API field, web asset or launcher changed.

### Known follow-up

- `positive_evidence_discount` is still reported for inputs that contain no positive
  evidence (35.5 with the default mode): it is the mode baseline plus the
  amplification term. This patch does not change that logic; it is tracked as a
  separate issue.

## [0.1.3] - 2026-09-14

### Fixed

- Web UI: the FNBP "NED Reminder" card was rendered inside the Asymmetry panel,
  so running the branch predictor in the Lab tab never displayed it. The reminder
  now appears in the Lab panel, directly under the FNBP verdict, and the existing
  verdict line is preserved.
- Web UI: both FNBP outcomes now show their personality copy — a prediction miss
  adds "NED 提醒：预测不是事实。期待也不是证据。🤠", a prediction hit adds
  "🎯 命中了。但 NED 提醒：一次预测成功，不等于发现了规律。🤠" — and the English
  line stays as auxiliary information.

### Unchanged

- Branch prediction, hit/miss counting, the pipeline trace, the statistics, the
  seed behaviour and the REST payloads are untouched: the reminder is display-only
  personality copy and never reaches an API response.

## [0.1.2] - 2026-09-14

### Fixed

- Windows launcher: `start_ned.bat` is now ASCII-only, so it no longer depends on
  the console codepage of the machine. On Windows with a non-Chinese codepage the
  previous non-ASCII file was decoded as mojibake, and cmd.exe executed fragments
  of the mis-decoded text as unrelated commands (one of them triggered the AT
  command help).
- Windows launcher: Python detection now judges `py -3 --version` by the output it
  prints rather than by its exit code, so a Microsoft Store placeholder or a
  launcher without a usable Python 3 is no longer accepted.

### Changed

- Windows launcher: the first run now creates and uses a project-local `.venv`
  (Python, pip and `ned.exe` all come from that environment) instead of installing
  into the system Python.
- Windows launcher: NED is started through the entry point declared in
  `pyproject.toml`, by absolute path; the launcher never relies on `ned` being on
  `PATH`.
- Windows launcher: the project-local environment is validated before use, so
  renaming or moving the extracted folder repairs itself instead of failing.
- No changes to the analysis engine, the rule packs or the REST contract.

## [0.1.1] - 2026-09-14

### Added

- NED Personality Layer: centralized, bilingual, display-only feedback for
  Analyze Evidence, the Evidence Asymmetry Detector and the FNBP easter egg.
- `start_ned.bat`, a Windows double-click launcher that installs and starts NED
  without requiring the `ned` console command to be on `PATH`.

### Changed

- The human-readable Web and CLI reports now add satirical feedback after a
  score has been computed; scores, verdict selection and API JSON are unchanged.
- The FNBP easter egg now gives outcome-specific reminders for prediction hits
  and misses while preserving its branch-prediction trace and statistics.

## [0.1.0] - 2026-09-13

Initial public release of **NED — Nov1ce Evidence Denier**, a fully-offline
emotional evidence de-weighting engine.

### Added

- Offline rule engine: paste a chat message or event description and NED detects
  possible positive-affection signals, generates alternative explanations,
  discounts the positive evidence, and emits a NED Verdict — with no network
  access at any point.
- PED (Positive Evidence Denier): detects possible positive-affection signals and
  systematically discounts them.
- NEA (Negative Evidence Amplifier) with a reality check, so that negative
  evidence is amplified without letting the structure collapse into plain
  catastrophizing.
- Semantic Escape Module with escalation tiers and the
  `NED is currently reaching.` state.
- Evidence Asymmetry Detector with a 0–100 asymmetry score.
- FNBP (Fuyuki Notification Branch Predictor) easter egg.
- Three analysis modes: `normal`, `scientific`, and `extreme`.
- FastAPI REST API: `/api/health`, `/api/version`, `/api/analyze`,
  `/api/asymmetry`, `/api/fnbp`, `/api/modes`, `/api/examples`.
- Typer CLI (`ned`): `analyze`, `asymmetry`, `fnbp`, `demo`, `examples`,
  `version`, `serve`.
- Zero-dependency web UI (Jinja2 templates and static assets only).
- `rules/*.json` configurable rule packs: `signals.json`, `escaping.json`,
  `verdicts.json`, `reality_checks.json`, `modes.json`, `easter_eggs.json`,
  `asymmetry.json`.
- pytest suite under `tests/`, with example cases in `ned/examples/cases.json`.
- ruff and mypy configuration (ruff line length 100, `mypy ned` clean).
- Dockerfile and docker-compose for running the API locally.
- GitHub Actions CI (`.github/workflows/test.yml`) covering Linux on Python 3.12
  and 3.13 plus a Windows job.

### Changed

- Nothing yet — this is the first release. Future releases will summarize
  user-visible behavior changes here, including rule pack schema changes, since
  the rule packs are a public interface.

### Notes

- All outputs are satire. NED cannot determine whether anyone likes you, and the
  project makes no claim about anyone's real feelings. It demonstrates
  interpretation space and cognitive bias (evidence asymmetry). It is not
  psychology, not diagnosis, and not mind-reading.
- Privacy: local-first, fully offline, no telemetry, no analytics, no trackers,
  no database, no accounts, no paid APIs. v0.1 never calls an external LLM; the
  `LLMProvider` interface exists as a stub for future work.

[Unreleased]: https://github.com/Sh1oud/NED/compare/v0.1.5...HEAD
[0.1.5]: https://github.com/Sh1oud/NED/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/Sh1oud/NED/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/Sh1oud/NED/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/Sh1oud/NED/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Sh1oud/NED/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Sh1oud/NED/releases/tag/v0.1.0
