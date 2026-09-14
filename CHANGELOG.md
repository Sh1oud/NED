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

[Unreleased]: https://github.com/Sh1oud/NED/compare/v0.1.3...HEAD
[0.1.3]: https://github.com/Sh1oud/NED/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/Sh1oud/NED/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Sh1oud/NED/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Sh1oud/NED/releases/tag/v0.1.0
