# Screenshots

The README references four images captured from the real NED v0.1.0 UI and CLI.
They are release evidence, not mockups. Re-capture them whenever the UI changes and
check them against [`../../RELEASE_CHECKLIST.md`](../../RELEASE_CHECKLIST.md) section 2.

## What to capture

| File | Tab / command | State to capture |
| --- | --- | --- |
| `analysis.png` | Analyze | `她说喜欢我`, mode **Nov1ce Extreme**, after Analyse — shows signal, discount, reaching level and verdict |
| `asymmetry.png` | Asymmetry Detector | defaults (`她主动找我聊了两个小时` vs `五分钟没回复`) — shows the 19% vs 90% weights, the thresholds and the 81.8 score |
| `fnbp-lab.png` | Lab (FNBP) | defaults, after Run Branch Predictor — shows the pipeline log and `怎么又不是她效应` |
| `cli-extreme.png` | CLI | `ned analyze "她说喜欢我" --mode extreme`, the full report |

Suggested size: **1440 × 1000** (or a 2× device scale factor for crisp text). Use a
dark background — the UI is dark by default.

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

## Rules

1. Never commit a mockup, a redrawn UI, or a doctored image. The screenshots are
   evidence about the product.
2. Re-take them whenever the UI changes; a stale screenshot is a bug report.
3. Do not include real people's messages. Use only the shipped synthetic examples.
