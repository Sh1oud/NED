# NED

**Nov1ce Evidence Denier**

> When reality becomes suspiciously positive, NED restores uncertainty.

Everything may be affection.
Everything may also be 人好. 👍

[![tests](https://github.com/REPLACE-WITH-GITHUB-OWNER/ned/actions/workflows/test.yml/badge.svg)](https://github.com/REPLACE-WITH-GITHUB-OWNER/ned/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](pyproject.toml)

<!-- Before publishing: replace REPLACE-WITH-GITHUB-OWNER and REPLACE-WITH-CONTACT-EMAIL.
     Every occurrence is listed in RELEASE_CHECKLIST.md. -->

---

## Table of contents

- [What NED is](#what-ned-is)
- [Screenshots](#screenshots)
- [Features](#features)
- [Installation](#installation)
- [Quick start](#quick-start)
- [CLI usage](#cli-usage)
- [API usage](#api-usage)
- [Modes](#modes)
- [How the score works](#how-the-score-works)
- [Examples](#examples)
- [Architecture](#architecture)
- [Configuration: rule packs](#configuration-rule-packs)
- [Privacy](#privacy)
- [Philosophy](#philosophy)
- [Disclaimer](#disclaimer)
- [Development](#development)
- [Testing](#testing)
- [Docker](#docker)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## What NED is

NED takes one message or one event description, finds the possible positive-affection
signals in it, and then — with a rigour that is both real and ridiculous — generates
alternative explanations for them, discounts the evidence, measures how hard it had to
reach, and prints a verdict.

```
$ ned analyze "我想你了"

  signal     : missing_you — 表达的想念（我想你了）
  raw reading: 对方表达了想念。

  Evidence strength        ███████████████░░░░░░░░░░░░░   55.0%
  Positive discount        ███████████░░░░░░░░░░░░░░░░░   40.8%
  NED Reaching Level       █████████████░░░░░░░░░░░░░░░   47.7%
                           Advanced overthinking

  Alternative Hypotheses
    1  可能只是怀旧，而不是当下的情感。      nostalgia     51%
    2  可能只是无聊，当时想找个人说话。      boredom       51%
    3  可能只是当时心情不错，情绪具有情境依赖性。  mood     51%

  Reality Check
    存在真实的正向互动：表达的想念（我想你了）。但样本量 N=1。要支持更强的结论，
    需要更多相互独立的事件，而不是对同一个事件做更深的解读。

  Final Verdict (ped.ren_hao)
    可能只是人好。👍
```

NED v0.1 runs **entirely offline**. There is no database, no account system, no
telemetry, no analytics and no paid API. Your text is analysed in-process and
discarded.

---

## Screenshots

| View | Image | Status |
| --- | --- | --- |
| Web UI — analysis | [`docs/screenshots/analysis.png`](docs/screenshots/analysis.png) | not captured yet |
| Web UI — asymmetry detector | [`docs/screenshots/asymmetry.png`](docs/screenshots/asymmetry.png) | not captured yet |
| Web UI — FNBP lab | [`docs/screenshots/fnpb-lab.png`](docs/screenshots/fnpb-lab.png) | not captured yet |
| CLI — extreme mode | [`docs/screenshots/cli-extreme.png`](docs/screenshots/cli-extreme.png) | not captured yet |

All four views exist and are exercised by the test suite (`tests/test_api.py`,
`tests/test_cli.py`); the PNGs are intentionally not committed yet, because a
screenshot has to be taken on a machine that can run a browser. To capture them on
your machine:

```bash
ned serve --port 8742                          # terminal 1
python scripts/capture_screenshots.py          # terminal 2
```

The raw CLI output for the fourth shot is committed as
[`docs/cli-extreme.txt`](docs/cli-extreme.txt), so the image can be re-taken from a
known-good capture at any time. See [`docs/screenshots/README.md`](docs/screenshots/README.md).

The web UI is designed to look like a clinical instrument panel: dark, hairline
borders, monospace read-outs, one accent colour, and progress bars that escalate
from calm cyan to "Industrial-grade denial" magenta.

---

## Features

- **PED — Positive Evidence Denier.** Detects positive signals and lowers their
  probative value, always labelling the alternatives as *hypotheses*, never facts.
- **NEA — Negative Evidence Amplifier.** Prints the irrational reading of weak
  negative evidence *next to* a reality check that says how little it is worth.
  It exists to display the asymmetry, not to encourage it.
- **Semantic Escape Module.** As the evidence gets stronger, NED's explanations get
  more strained — from "possibly nostalgia" to "marriage is a legal relationship and
  does not independently prove love. 👍"
- **Evidence Asymmetry Detector.** Measures the double standard directly: how heavily
  you discount good news versus how fast you accept bad news. Produces a 0–100 score.
- **FNBP — Fuyuki Notification Branch Predictor.** A Lab easter egg that simulates
  mispredicting every notification as being from one specific person, complete with
  pipeline flushes and wasted cycles.
- **Three modes:** `normal`, `scientific` (peer-review register), `extreme`
  (Nov1ce Mode).
- **Escalation across turns:** pass earlier messages and NED will keep explaining until
  it runs out of explanations, then say so.
- **Web UI, REST API and CLI** over the same engine, plus `/docs` (OpenAPI).
- **Configurable rule packs:** every judgement NED makes lives in JSON, not Python.
- **Bilingual:** Chinese and English inputs both work, with localized labels, verdicts
  and reality checks.
- **No network, ever.** A test asserts the CLI cannot even open a socket.

---

## Installation

Requires **Python 3.12+**. No API keys, no services, no accounts.

```bash
git clone https://github.com/REPLACE-WITH-GITHUB-OWNER/ned.git
cd ned

python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

pip install -e ".[dev]"
```

Runtime-only install:

```bash
pip install .
```

## Quick start

```bash
# 1. The terminal
ned analyze "我想你了"

# 2. The web UI and the API (defaults to 127.0.0.1:8000)
ned serve
#   UI:       http://127.0.0.1:8000/
#   API docs: http://127.0.0.1:8000/docs

# 3. The demo
ned demo
```

---

## CLI usage

```
ned analyze TEXT [--mode normal|scientific|extreme] [--history TEXT ...] [--top-k N] [--json]
ned asymmetry [--positive TEXT] [--negative TEXT] [--text TEXT] [--mode MODE] [--json]
ned fnbp [--expected NAME] [--actual NAME ...] [--count N] [--seed N] [--json]
ned demo [--mode MODE] [--json]
ned examples [--json]
ned version
ned serve [--host HOST] [--port PORT] [--reload]
```

Every command takes `--json` and then prints the API payload verbatim, so the CLI
can be scripted without parsing the pretty output.

```bash
# Escalation: NED keeps explaining, and eventually gives up
ned analyze "我们已经结婚了" --mode extreme \
  --history "我喜欢你" --history "我想和你谈恋爱" --history "做我男朋友吧"

#   NED Reaching Level  ████████████████████████████  100.0%
#                       人好。👍
#   Final Verdict (ned.capacity_exhausted)
#     兄弟，再解释就不礼貌了。😭

# The double standard detector
ned asymmetry --positive "她主动找我聊了两个小时" --negative "五分钟没回复"

#   positive  sustained interaction of about 2 hours   raw 82   weight 19%
#   negative  no reply for about 5 minutes             raw 90   weight 90%
#   Positive threshold  EXTREMELY HIGH
#   Negative threshold  EXTREMELY LOW
#   Asymmetry score     ████████████████████████░  81.8%   EXTREME

# The Lab easter egg
ned fnbp --expected Fuyuki --actual 张三 --actual 李四 --count 5
```

---

## API usage

`ned serve` exposes the OpenAPI docs at `/docs` and `/redoc`.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Liveness, version, uptime, engine name |
| GET | `/api/version` | Version and identity (single source: `ned/app/version.py`) |
| GET | `/api/modes` | Configured analysis modes |
| GET | `/api/examples` | Shipped synthetic example cases |
| GET | `/api/providers` | Registered explanation providers and the active one |
| GET | `/api/rules` | Rule-pack provenance (counts, directory, version) |
| GET | `/api/easter-eggs` | Cosmetic easter eggs |
| POST | `/api/analyze` | Full PED/NEA/Escape analysis |
| POST | `/api/asymmetry` | Evidence Asymmetry Detector |
| POST | `/api/fnbp` | FNBP lab simulation |

```bash
curl -s http://127.0.0.1:8000/api/health
# {"status":"ok","version":"0.1.0","uptime_seconds":12.3,"local_only":true,"engine":"ned-local-rules"}
```

```bash
curl -s -X POST http://127.0.0.1:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"text":"我想你了","mode":"extreme"}'
```

```json
{
  "input": "我想你了",
  "mode": "extreme",
  "language": "zh",
  "signal_type": "missing_you",
  "signal_label": "表达的想念（我想你了）",
  "signal_strength": 55.0,
  "raw_interpretation": "对方表达了想念。",
  "alternative_explanations": [
    {
      "hypothesis": "可能只是怀旧，而不是当下的情感。",
      "category": "nostalgia",
      "plausibility": 38.4,
      "source": "local-rule",
      "rule_id": "tier.situational",
      "note": "Alternative hypothesis, not a finding."
    }
  ],
  "positive_evidence_discount": 67.4,
  "negative_evidence_amplification": 0.0,
  "ned_reaching_level": 51.3,
  "reaching_label": "Advanced overthinking",
  "reality_check": "存在真实的正向互动：表达的想念（我想你了）。但样本量 N=1。…",
  "verdict": {
    "code": "ped.friendly_unexcluded",
    "text": "检测到积极信号，但无法排除友好行为。",
    "severity": "info",
    "emoji": "❔",
    "rule_id": "ped.friendly_unexcluded"
  },
  "breakdown": { "positive_mass": 55.0, "escape_pressure": 0.42, "escape_capacity": 0.33 },
  "engine": { "name": "ned-local-rules", "version": "0.1.0", "provider": "local-rule", "offline": true },
  "disclaimer": "NED cannot determine whether someone likes you. Humans are not APIs. …"
}
```

The full response model is in `ned/app/core/models.py`; the response is always
structured JSON, never a paragraph of prose.

---

## Modes

| Mode | Register | Positive discount baseline | Escapes | What it is for |
| --- | --- | --- | --- | --- |
| `normal` | dry | 35% | 3 | The default. Memes at a moderate density, plus an honest reality check. |
| `scientific` | peer review | 45% | 4 | The same conclusion in more syllables, with a sample size of N=1. |
| `extreme` | Nov1ce Mode | 60% | 5 | Every escape hatch at once, including the legal ones. |

Mode differences are configuration, not code: see `ned/app/rules/modes.json`.

### NED Reaching Level

| Range | Label |
| --- | --- |
| 0–19 | Reasonable skepticism |
| 20–39 | Routine doubt |
| 40–59 | Advanced overthinking |
| 60–79 | Industrial-grade denial |
| 80–99 | NED is currently reaching. |
| 100 | 人好。👍 |

---

## How the score works

Every number NED prints is computed from the formulas below, and every
intermediate value is exposed in the response's `breakdown` object.

```
positive_mass      = noisy_or(weights of positive signals)         # 1 - Π(1 - pᵢ)
negative_mass      = noisy_or(weights of negative signals)
information        = noisy_or(information_content of those signals)

negative_amplification = 100 · (1 − negative_information / negative_mass)

escape_pressure    = mean(1 − plausibility/100) over the escapes NED used
history_pressure   = min(1, history_mass / 100)
escape_capacity    = 0.60 · positive_mass/100 + 0.40 · history_pressure

reaching_level     = 0.62 · positive_mass + 28 · escape_pressure + 20 · history_pressure

positive_discount  = mode.discount_base
                   + 12 · escape_pressure
                   +  8 · negative_amplification/100
```

The last line is the joke expressed as arithmetic: the harder NED has to reach for an
explanation, the *more* of your evidence it discards. That is backwards as reasoning,
which is the point.

### Asymmetry Score

```
weight_gap      = (N_weight − P_weight) / (N_weight + P_weight)          # clamped to [0,1]
information_gap = (P_info   − N_info)   / (P_info   + N_info)            # clamped to [0,1]
categorical     = mean( N_weight > 75 , P_weight < 25 )

asymmetry_score = 100 · (0.45·weight_gap + 0.25·information_gap + 0.30·categorical)
```

Weight bands: `0–19 NEGLIGIBLE`, `20–39 MILD`, `40–59 MODERATE`,
`60–79 SEVERE`, `80–100 EXTREME`.

Unless the input states an interpretation of its own, the positive side is
discounted by a **declared prior** (a further ×0.35, configured in
`ned/app/rules/asymmetry.json`) because that is what the classic asymmetric reading
does. The prior is an explicit assumption, printed in the config, not a measurement
of anybody.

---

## Examples

Inputs and their classic outcomes (all available as `ned examples`):

| Input | Mode | Outcome |
| --- | --- | --- |
| `我想你了` | normal | `可能只是人好。👍` |
| `我想你了` | extreme | `检测到积极信号，但无法排除友好行为。` |
| `她说喜欢我` | extreme | reaching 76.7 (Industrial-grade denial) → `证据不足，建议扩大样本量。👍` |
| `我们已经结婚了` | extreme | `婚姻属于法律关系，不能单独证明爱情。👍` |
| `她主动找我聊了两个小时，但五分钟没回复` | normal | `检测到证据标准不对称。` (score ≈ 82/100) |
| `消息发出去五分钟没回复` | normal | `Reject. 5 分钟未回复不构成证据。👍` |
| `今天开会开了三个小时` | normal | `未检测到明显情感证据。NED 无事可做。👍` |
| `I love you` | scientific | `Current sample size is insufficient to reject the general-friendliness hypothesis (N=1).` |
| `我喜欢你` ×3 then `我们已经结婚了` | extreme + history | reaching 100 — `兄弟，再解释就不礼貌了。😭` |

The last row is NED's finale: once the evidence has been overwhelming for several
turns, its escape capacity is exhausted and the software admits the joke.

---

## Architecture

```
ned/                          Python package
├── app/
│   ├── main.py               FastAPI app factory, static/template wiring
│   ├── cli.py                Typer CLI (thin adapter over the analyzer)
│   ├── config.py             Typed configuration objects + NED_RULES_DIR
│   ├── version.py            Single source of truth for the version
│   ├── api/routes.py         REST routes
│   ├── core/
│   │   ├── models.py         Pydantic models (the API contract)
│   │   ├── parser.py         Language detection, duration parsing, rule matching
│   │   ├── scoring.py        The transparent scoring formulas
│   │   ├── theories.py       PED, NEA and the Semantic Escape Module
│   │   ├── asymmetry.py      Evidence Asymmetry Detector
│   │   ├── verdict.py        Declarative verdict engine
│   │   ├── fnbp.py           Fuyuki Notification Branch Predictor (easter egg)
│   │   ├── rules.py          Rule-pack loader and typed rule models
│   │   └── analyzer.py       NedAnalyzer: the framework-free facade
│   ├── providers/
│   │   ├── base.py           Provider protocol + registry
│   │   ├── local.py          The offline rule provider (the only one that runs)
│   │   └── llm.py            Declared stub that raises (never called in v0.1)
│   ├── rules/*.json          All judgement: signals, escapes, verdicts, modes…
│   ├── static/               style.css, app.js (no framework, no CDN)
│   └── templates/index.html  The single-page UI
├── examples/cases.json       Synthetic example cases
tests/                        pytest suite
```

Data flow:

```
text ──▶ parser.detect ──▶ scoring ──▶ theories.PED/NEA/Escape ──▶ verdict ──▶ models
              │                          ▲
              └──▶ asymmetry ────────────┘
```

The core engine never imports FastAPI, Typer, Rich or Jinja2. The API and the CLI
are adapters over `NedAnalyzer`, which is why the same behaviour is testable
without a server or a terminal.

---

## Configuration: rule packs

Every judgement NED makes is data. Override the whole directory with an
environment variable:

```bash
export NED_RULES_DIR=/path/to/my-rules     # PowerShell: $env:NED_RULES_DIR = "D:\my-rules"
ned analyze "我想你了"
```

| Pack | Contents |
| --- | --- |
| `signals.json` | Detection rules: regex patterns, weights, information content, NEA readings |
| `escaping.json` | Escape tiers by evidence strength, plus literal-wording escapes |
| `verdicts.json` | Ordered verdict rules with declarative `when` conditions, FNBP strings, disclaimer |
| `reality_checks.json` | The honest sentences, bilingual |
| `modes.json` | Mode tuning (discount baseline, escape count, plausibility scaling) |
| `asymmetry.json` | Asymmetry weights, bands, priors and scoring constants |
| `easter_eggs.json` | Cosmetic eggs, never able to influence a verdict |

A rule pack is validated at startup: a bad pack fails loudly with the offending
rule id, and `tests/test_rules.py` checks pack coherence in CI.

---

## Privacy

NED v0.1 is **local-first**:

- no uploads, no cloud, no third-party API calls;
- no database, no files written from your input, no accounts;
- no telemetry, no analytics, no trackers, no cookies;
- the web UI keeps your text in the browser and stores only the selected mode in
  `localStorage`;
- request bodies are not logged by NED itself (uvicorn's access log records the
  method and path, not the body — run with `--log-level warning` if you want even
  that gone).

The only place text leaves the process in v0.1 is… nowhere. The `llm` provider
exists as an interface and raises on use, so it cannot silently phone home.

## Philosophy

NED is satire with a specific target: **evidence asymmetry**.

People often require an enormous amount of proof before accepting a positive
interpretation, and almost none before accepting a negative one. Two hours of
someone actively seeking your company get discounted to "they are probably just
being nice", while five minutes without a reply is accepted as "they do not want to
talk to me". Same person, same week, two completely different standards of proof.

NED makes that asymmetry executable. It plays the role of the over-skeptical voice:
it finds your good news, explains it away with straight-faced methodology, assigns
arbitrary numbers to its own guesses — and then, because the joke only works if it is
honest, prints a Reality Check that says what the evidence can actually support,
plus an Asymmetry Score that measures the double standard it just performed.

The absurdity is the argument. "婚姻属于法律关系，不能单独证明爱情。👍" is funny
because it is a technically true sentence used to dismiss something that does not
need a proof in the first place. NED is a mirror for that move, not a manual for it.

The project therefore has two rules it will not break:

1. **It never claims to know what anyone feels.** No verdict reads "she likes you"
   or "she does not like you". The strongest available output is "the evidence is
   insufficient", which is the only conclusion text can actually support.
2. **Every generated explanation is labelled a hypothesis**, with the rule id that
   produced it, and paired with the reality check.

If NED ever helps anyone, it will be by making the asymmetry visible enough to be
funny, and therefore visible enough to stop doing.

## Disclaimer

> **NED cannot determine whether someone likes you.**
> Humans are not APIs.
> No amount of text analysis can replace direct communication and context.

NED is entertainment software and a satire on reasoning, not a psychological
instrument, a diagnostic tool, a dating coach or a mind reader. Its plausibility
numbers are arbitrary by construction. Do not use its output to make decisions about
real people, and do not use it to justify contacting or not contacting anyone —
ask them instead, in words, like a person.

Nothing in NED's output is professional advice of any kind. If you are struggling
with anxiety about a relationship, that is a real and common thing, and a
conversation with a human (or a qualified professional) will help far more than a
sarcastic CLI.

---

## Development

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"

ruff check .            # lint
ruff format --check .   # formatting
mypy                    # types (config lives in pyproject.toml)
pytest -q               # tests
pytest -q --cov=ned --cov-report=term-missing
```

Layout rules for contributors:

- rules and user-facing strings live in `ned/app/rules/*.json`, not in Python;
- the core engine must not import FastAPI, Typer, Rich or Jinja2;
- every public function is annotated, and every structured value is a Pydantic model;
- new behaviour needs a test; new satire needs a reality check.

## Testing

```bash
pytest -q
```

The suite covers the parser (both languages, durations, exclusions, overlap handling),
the scoring formulas against hand-computed values, the analyzer's behaviour on the
classic cases and all three modes, the asymmetry detector, the provider architecture
(including prompt-injection-shaped input), the REST API, the CLI, and the rule packs'
internal coherence. Two tests exist purely as guard rails:

- `test_cli_needs_no_network` forbids the CLI from opening a socket at all;
- `test_no_output_claims_to_know_anyones_feelings` fails if a report ever contains a
  sentence like "她喜欢你".

For a release check against a real server:

```bash
ned serve --port 8742               # terminal 1
python scripts/verify_http.py 8742  # terminal 2: every endpoint + the rendered UI
```

## Docker

```bash
docker build -t ned:0.1.0 .
docker run --rm -p 127.0.0.1:8000:8000 ned:0.1.0
# UI: http://127.0.0.1:8000/   docs: http://127.0.0.1:8000/docs
```

Or with Compose:

```bash
docker compose up --build
```

The image runs as a non-root user with a read-only root filesystem, mounts nothing
by default, and makes no network calls at run time. To use custom rule packs, mount
them read-only and set `NED_RULES_DIR` (see the comments in `docker-compose.yml`).

## Roadmap

- **v0.2** — an opt-in LLM provider behind a flag, with an explicit privacy warning and
  a hard rule that it can only *add* hypotheses, never change the verdict.
- **v0.2** — timeline analysis: several events with timestamps, so NED can weigh
  frequency instead of one message.
- **v0.3** — more languages (Japanese, Korean, Spanish) as rule packs.
- **v0.3** — report export (PNG/Markdown) and an i18n'd web UI.
- **v0.4** — a rule-pack validator CLI (`ned lint-rules`) and a gallery of
  community packs.

## Contributing

Issues and pull requests are welcome — especially rule packs, new escape tiers and
better reality checks. Please read [CONTRIBUTING.md](CONTRIBUTING.md) and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) first. Two ground rules:

1. NED must never claim to detect real feelings, and contributions that do will be
   rejected regardless of how funny they are.
2. Never submit anyone's real private messages as test data. Write synthetic examples
   (see `ned/examples/cases.json`).

## License

[MIT](LICENSE) © 2026 NED Contributors.

NED is a parody. Use it on yourself.
