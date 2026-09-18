# Screenshots

The README references four images captured from the real NED UI and CLI; each
image prints the engine version it was captured from. They are release evidence,
not mockups. Re-capture them whenever the UI changes and
check them against [`../../RELEASE_CHECKLIST.md`](../../RELEASE_CHECKLIST.md) section 2.

## What to capture

| File | Tab / command | State to capture |
| --- | --- | --- |
| `analysis.png` | Analyze | `她说喜欢我`, mode **Nov1ce Extreme**, after Analyse — the first screen, with signal, discount, reaching level and verdict inside the folded **Technical Details**. Capture it in the shipped default configuration: no casebook switched on, so no casebook file exists and no filing action is offered |
| `asymmetry.png` | Asymmetry Detector | defaults (`她主动找我聊了两个小时` vs `五分钟没回复`) — the comparison first screen; the treated weights (11.5% / 90.0%) are inside the folded **Technical Details** |
| `fnbp-lab.png` | Lab (FNBP) | defaults, after Run Branch Predictor — shows the pipeline log and `怎么又不是她效应` |
| `cli-extreme.png` | CLI | `ned analyze "她说喜欢我" --mode extreme`, the full report |

The script sets a **1440 × 1000** viewport at a 2× device scale factor and screenshots
the *full page*, so the three web images come out 1440 CSS px wide and about 2806 px tall
(2880 × 5612 device pixels), and the CLI page about 1180 × 1258 CSS px. Use a dark
background — the UI is dark by default.

Both web reports keep their rigorous blocks behind the folded **Technical Details**,
so a screenshot of a settled view shows the first screen plus the folded headers.
The Asymmetry page deliberately shows neither an asymmetry score nor admission
thresholds while the input carries no reader judgement; that absence is pinned by
`tests/test_comparability.py` and must not be captured around.

## How to capture

```bash
ned serve --port 8742
python scripts/capture_screenshots.py --base-url http://127.0.0.1:8742
```

The script drives the real UI over the Chrome DevTools Protocol (filling the inputs and
clicking the real buttons) and writes all four files into this directory. It needs a
working Chrome or Edge installation; see the script header for flags.

Manually is fine too: open the URL, click through the three tabs, screenshot the
viewport, and render `docs/cli-extreme.txt` in your terminal for the fourth.

## Regenerating the CLI capture

`cli-extreme.png` is rendered *from* `docs/cli-extreme.txt`, so a version bump makes
that image stale until the capture behind it is regenerated. Two steps:

```bash
# 1. regenerate the raw capture from the real CLI, at the width the box is drawn for
ned analyze "她说喜欢我" --mode extreme        # run in a 99-column terminal
# 2. re-render only the image, from the committed text
python scripts/capture_screenshots.py --cli-only --out-dir <absolute-path>
```

Step 1 is a terminal capture, so the committed file carries three *environment*
normalisations and nothing else: CRLF is written as LF, trailing whitespace on each
line is stripped (the renderer pads some lines), and the box is drawn for a 99-column
terminal (98-character rules, 63 lines). Nothing else about the capture is edited — the
report text itself is exactly what the CLI printed. Step 2 needs an absolute `--out-dir`;
a relative or out-of-repo path writes the image first and then raises.

The image is evidence of the version it was captured from, so after any version bump
both steps have to be repeated; the engine version printed inside the image is the
check. The render is deterministic: re-rendering the same committed text produces the
same PNG bytes, which is how a re-seal proves the image it ships is the image of the
capture it ships.

## Rules

1. Never commit a mockup, a redrawn UI, or a doctored image. The screenshots are
   evidence about the product.
2. Re-take them whenever the UI changes; a stale screenshot is a bug report.
3. Do not include real people's messages. Use only the shipped synthetic examples.
