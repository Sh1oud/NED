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

[Unreleased]: https://github.com/Sh1oud/NED/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Sh1oud/NED/releases/tag/v0.1.0
