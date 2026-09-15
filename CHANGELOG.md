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

## [0.1.9] - 2026-09-15

**NED v0.1.9 — Hard-line Maintenance**

Maintenance release. Two fixes, both about the same hard line: an uncertain claim
may not be presented as a stated boundary, and a stated boundary may not be
covered by anything else. No new verdict, no new signal family, no new score, no
new UI, no new schema, and no feature expansion beyond these two.

### Fixed

- Uncertain or hypothetical rejection claims are no longer presented as explicit
  relationship boundaries. `我可能被拒绝了` no longer reaches the boundary screen,
  along with the related modal forms covered by this patch.
- Additional explicit relationship-boundary forms are recognised, so the covered
  forms can no longer be hidden behind a positive or comedic screen.
  `她说不想见我`, `她说她只想当普通朋友` and `她说她不想发展成恋爱关系` now take
  the existing boundary path; material the input also reports stays on file
  underneath that screen instead of deciding it.

### Known limitation

- Hypothetical wording around the family's older triggers keeps its shipped
  answer (`她未必拒绝了我` still reaches the boundary screen). Registered, not
  changed in this release.
- A boundary whose subject is elided behind a receiver that contains the reader
  (`她跟我说只想当普通朋友`) is still not recognised. Registered.

## [0.1.8] - 2026-09-15

**NED v0.1.8 — Alternative Explanation Audit & Multiple Aspects**

NED now audits the reader's own explanation with the same window it uses for
everything else, and files several materials as several pages instead of merging
them into one answer. 👍

### Added

- **Alternative Explanation Audit.** When the reader supplies their own explanation
  (`她说喜欢我，但我觉得她只是人好。`), that explanation is filed
  with its attachments counted, the material it is about is quoted back verbatim, and
  the unknowns are listed instead of filled in. A card shows the material, the
  explanation, whether the input reports material for it, what is still unknown and how
  far the material reaches.
- **Multiple Aspects presentation.** When the input itself reports more than one
  material that can stand on its own page (`她夸我可爱，但她三天没回我消息。`),
  NED keeps every page with its own grade and refuses to add them up. A stated boundary
  keeps its screen word for word, with the second page recorded underneath it.

### Changed

- R1 recognition patch: the ordinary offer (`想/要/愿意/希望 + 和我做男女朋友`)
  is recognised, with a guard for its negations.
- R2 recognition patch: the self-discount frame accepts explicit first-person wording
  (`我觉得 / 我认为 / 我感觉`) and no longer accepts a bare `感觉`.
- Chinese project declaration updated.

### Safety and behaviour

- Pessimistic alternative explanations no longer receive a special exemption: the same
  window applies to every explanation.
- Multiple materials are preserved without aggregation: no average, no merge, no
  ranking, no overall relationship score, no probability.
- Explicit boundaries remain authoritative under any combination of materials, and
  hostile input gets no combined view at all.

### Known limitation

- Stage 1 English Audit presentation remains partially Chinese (NED's first-screen lines
  and the Epistemic Breakdown card). Stage 2 English coverage is more complete. Runtime
  correctness is unaffected.

## [0.1.7] - 2026-09-14

**NED v0.1.7 — Comedy Recovery**

NED no longer only refuses good news: it refuses good news in the register of
whichever department the evidence belongs to. 👍

### Added

- Personality recovery: the 30-second screen is built for a person, not for a
  schema. A title, one observed fact, a plain-language evidence quality, one or
  two lines of NED, and one short reality check.
- Comedy packs: seven families of recognised positive evidence now get copy about
  that family instead of one generic screen — invitation, initiation, gift, care,
  sustained interaction, reported affection/longing, and compliment. Each pack
  carries one or two main lines and three to five topic-specific alternative
  explanations. Families without a pack keep the generic screen.
- Natural-language coverage: the ordinary ways people describe the same events
  are recognised — `他约我周末去看电影`, `她问我周末有没有空`,
  `他今天第一次主动给我发消息`, `他给我点了一杯奶茶`, `他记得我爱吃什么`,
  `他说了一百遍“想我了”`, `她说我们还是做朋友吧`, `我表白被拒了`.
- Quote fidelity: a screen that quotes the reader now quotes their own words,
  captured from the input, or shows no quotation at all.
- Perspective safety: `我想你了` is the reader's own feeling and is no longer
  reported as the other person's expressed longing; a quoted counterpart line
  (`她对我说“我想你了”`) still is.
- Negation and reversal guards: a reported clause that the same sentence reverses
  (`他从来不说喜欢我`, `以前秒回，现在半天才回`) is no longer read as present
  positive evidence.
- Attribution guards: `秒回别人` is not `秒回我`, and `她说她只是把我当朋友` is
  her statement, not the reader's own discount.

### Changed

- The positive screens are family-aware in the default mode; the scientific and
  extreme modes keep their own register.
- A single greeting is no longer described as 规律性: the display says one
  greeting happened unless the input states a frequency. Display only — the
  engine sentence and the payload are unchanged.
- Copy safety: no user-facing line certifies the reported event any more.
  "线下邀约已确认" became "线下邀约材料已进入卷宗", and "物资援助已确认" became
  "卷宗中出现了一杯奶茶". NED files reports; it does not investigate them.
- Comedy escalation: one line per family is deliberately unhinged, and every
  other line keeps a real reasoning principle attached, with NED itself as the
  butt of the joke (`本机构决定继续嘴硬`).

### Fixed

- `他从来不说喜欢我` no longer produces "对方据称表达了喜欢".
- `我想你了` / `我好想你` / `我想见你` no longer produce "对方表达了想念".
- `她总是秒回别人，却不回我` no longer produces "对方回复速度很快".
- `她说她只是把我当朋友` no longer counts as the reader's self-discount.
- `她昨天跟我说晚安` no longer claims a routine greeting pattern.

### Unchanged

- Detection patterns of every family except the three guards above, every weight,
  `information_content`, `salience`, the scoring model, the amplification
  formula, the reaching level, the asymmetry detector, comparability, the REST
  schema and the verdict priorities. Rule pack: 38 signals.
- Boundary and hostile screens carry no comedy at all, in any mode.
- Explicit boundaries keep their rule: 明确边界。NED 停止狡辩。🚧

### Known limitations

- Recognition stays where it is: eleven ordinary inputs from the 50-input
  playtest are still silently unmatched, including `他把我微信删了`,
  `她把我介绍给她朋友了` and `他今天突然不理我了`.
- Three families' positive screens still share copy inside the family (up to
  four inputs), by design.
- English personality copy and the scientific/extreme coverage remain generic.

## [0.1.6] - 2026-09-14

### Added

- Rule packs: a `hostile_expression` signal family with Chinese and English rules
  for explicit hostility and abuse — direct insults (`去你妈的`, `滚你妈的`,
  `你有病吧`, `闭嘴`, `你算什么东西`) and reported hostile acts (`她怒骂我`,
  `他辱骂我`, `她骂了我一顿`, `对方冲我破口大骂`, `她对我恶语相向`). Weight 92 and
  information content 72: hostility is an observed act that NED does not
  de-weight, while telling less about the relationship's trajectory than an
  explicit boundary.
- Verdicts: `nea.hostile_expression_insufficient` (priority 38) acknowledges the
  reported expression and refuses the conclusions drawn from it.
- Reality checks: a `hostile_expression` check, used by the NEA panel for this
  family.

### Fixed

- Hostile input is no longer classified as `signal_type = none`: the pack had no
  rule for hostility at all, so "她说去你妈的了" and "她怒骂我" reached the
  catch-all verdict with an evidence strength of zero.

### Changed

- The raw reading, the reality check and the verdict of this family all state what
  the input reports and what NED does with it ("输入报告了…", "NED 按输入所述保留这
  条负向证据"), instead of asserting that the event happened.
- `zh.direct_rejection` no longer claims the insult form `滚你妈的` as a boundary,
  so the hostile family reports it instead.
- Joking and banter, game trash talk, media quotes, articles about abuse,
  meta-discussion of the wording, homographs, third parties and the reader's own
  characterisation of someone else stay outside the family.

### Unchanged

- Detection patterns and weights of every existing family, the scoring model, the
  amplification formula, the asymmetry detector, the `direct_rejection` rule and
  its priority, every existing verdict priority and the REST schema. The new
  verdict reuses the existing `Verdict` shape, so no API field was added.

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

[Unreleased]: https://github.com/Sh1oud/NED/compare/v0.1.9...HEAD
[0.1.9]: https://github.com/Sh1oud/NED/compare/v0.1.8...v0.1.9
[0.1.8]: https://github.com/Sh1oud/NED/compare/v0.1.7...v0.1.8
[0.1.7]: https://github.com/Sh1oud/NED/compare/v0.1.6...v0.1.7
[0.1.6]: https://github.com/Sh1oud/NED/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/Sh1oud/NED/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/Sh1oud/NED/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/Sh1oud/NED/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/Sh1oud/NED/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Sh1oud/NED/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Sh1oud/NED/releases/tag/v0.1.0
