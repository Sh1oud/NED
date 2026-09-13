#!/usr/bin/env python
"""Capture the four README screenshots from a running NED server.

The script drives the *real* UI through the Chrome DevTools Protocol: it navigates to
the app, fills the real inputs, clicks the real buttons, waits for the real API
responses, and screenshots the result. It also renders the committed CLI capture
(``docs/cli-extreme.txt``) into a terminal-styled page for the fourth image.

    ned serve --port 8742                    # terminal 1
    python scripts/capture_screenshots.py    # terminal 2

Requires ``websockets`` (already pulled in by ``uvicorn[standard]``) and a Chrome or
Edge installation. Nothing here is imported by the package itself.

Status: NOT executed in the environment where v0.1.0 was prepared — that sandbox
denies the named pipes Chromium needs for inter-process communication, so no browser
can start there. Run it on a normal desktop session and check the four images.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "docs" / "screenshots"

BROWSER_CANDIDATES = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
)


def find_browser(explicit: str | None) -> str:
    if explicit:
        return explicit
    for candidate in BROWSER_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    for name in ("google-chrome", "chromium", "chrome", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    raise SystemExit("No Chrome/Edge found. Pass --browser /path/to/chrome (see the header).")


class DevTools:
    """Minimal Chrome DevTools Protocol client over a single page target."""

    def __init__(self, ws_url: str) -> None:
        self.ws_url = ws_url
        self._ws = None
        self._next_id = 0

    async def __aenter__(self) -> DevTools:
        try:
            from websockets.asyncio.client import connect
        except ImportError as error:  # pragma: no cover - environment dependent
            raise SystemExit(
                "This script needs the 'websockets' package: pip install websockets"
            ) from error
        self._ws = await connect(self.ws_url, max_size=64 * 1024 * 1024)
        await self.send("Page.enable")
        await self.send("Runtime.enable")
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._ws is not None:
            await self._ws.close()

    async def send(self, method: str, params: dict | None = None) -> dict:
        assert self._ws is not None
        self._next_id += 1
        message_id = self._next_id
        await self._ws.send(
            json.dumps({"id": message_id, "method": method, "params": params or {}})
        )
        while True:
            raw = await asyncio.wait_for(self._ws.recv(), timeout=30)
            payload = json.loads(raw)
            if payload.get("id") == message_id:
                if "error" in payload:
                    raise RuntimeError(f"{method} failed: {payload['error']}")
                return payload.get("result", {})

    async def evaluate(self, expression: str):
        result = await self.send(
            "Runtime.evaluate",
            {"expression": expression, "awaitPromise": True, "returnByValue": True},
        )
        return result.get("result", {}).get("value")

    async def goto(self, url: str) -> None:
        await self.send("Page.navigate", {"url": url})
        await self.wait_for("document.readyState === 'complete'")

    async def wait_for(self, expression: str, timeout: float = 20.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if await self.evaluate(expression):
                return True
            await asyncio.sleep(0.25)
        return False

    async def screenshot(self, path: Path) -> None:
        metrics = await self.send("Page.getLayoutMetrics")
        size = metrics.get("cssContentSize") or metrics.get("contentSize") or {}
        width = int(size.get("width") or 1440)
        height = int(size.get("height") or 1000)
        await self.send(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": width,
                "height": height,
                "deviceScaleFactor": 2,
                "mobile": False,
            },
        )
        await asyncio.sleep(0.4)
        data = await self.send(
            "Page.captureScreenshot",
            {"format": "png", "captureBeyondViewport": True, "fromSurface": True},
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(data["data"]))
        size_kb = path.stat().st_size // 1024
        print(f"  wrote {path.relative_to(ROOT)}  ({size_kb} KB, {width}x{height})")


def wait_for_devtools(port: int, timeout: float = 25.0) -> dict:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=3) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError) as error:  # pragma: no cover
            last_error = error
            time.sleep(0.5)
    raise SystemExit(f"DevTools endpoint never came up on port {port}: {last_error}")


def page_target(port: int) -> str:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=5) as resp:
        targets = json.loads(resp.read().decode("utf-8"))
    for target in targets:
        if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
            return str(target["webSocketDebuggerUrl"])
    raise SystemExit("No page target available in the browser")


def start_browser(browser: str, port: int, profile: Path) -> subprocess.Popen:
    args = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--hide-scrollbars",
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}",
        "about:blank",
    ]
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def cli_harness_html() -> str:
    """A plain terminal-styled page displaying the *committed* CLI capture."""

    capture = ROOT / "docs" / "cli-extreme.txt"
    text = (
        capture.read_text(encoding="utf-8", errors="replace") if capture.is_file() else "(missing)"
    )
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>ned analyze --mode extreme</title>
<style>
  body {{ margin: 0; background: #0b0d10; padding: 28px 32px; }}
  h1 {{ color: #6d7d8c; font: 600 12px/1.6 ui-monospace, Consolas, monospace;
        letter-spacing: .18em; text-transform: uppercase; margin: 0 0 14px; }}
  pre {{ color: #d5dee6; font: 13px/1.45 ui-monospace, Consolas, "Cascadia Mono", monospace;
         white-space: pre; margin: 0; }}
</style></head>
<body><h1>ned analyze "&#22905;&#35828;&#21916;&#27426;&#25105;" --mode extreme</h1>
<pre>{escaped}</pre></body></html>"""


async def capture(base_url: str, out_dir: Path, port: int, browser: str, cli_only: bool) -> int:
    profile = Path(tempfile.mkdtemp(prefix="ned-shots-"))
    process = start_browser(browser, port, profile)
    try:
        wait_for_devtools(port)
        ws_url = page_target(port)
        async with DevTools(ws_url) as devtools:
            await devtools.send(
                "Emulation.setDeviceMetricsOverride",
                {"width": 1440, "height": 1000, "deviceScaleFactor": 2, "mobile": False},
            )

            if not cli_only:
                print("capturing web UI views...")
                await devtools.goto(base_url + "/")
                await devtools.wait_for("!!document.getElementById('analyze-input')")

                # 1. analysis view, extreme mode, populated
                await devtools.evaluate(
                    "(() => {"
                    "  const t = document.getElementById('analyze-input');"
                    "  t.value = '\u5979\u8bf4\u559c\u6b22\u6211';"
                    "  const m = document.getElementById('mode-select');"
                    "  if (m) { m.value = 'extreme';"
                    " m.dispatchEvent(new Event('change', {bubbles:true})); }"
                    "  document.getElementById('analyze-submit').click();"
                    "})()"
                )
                await devtools.wait_for(
                    "(() => { const r = document.getElementById('analyze-results');"
                    " return r && !r.hidden && !r.classList.contains('is-loading')"
                    " && (document.getElementById('verdict-text')||{}).textContent"
                    " && document.getElementById('verdict-text').textContent.trim()"
                    " !== '\u2014'; })()"
                )
                await devtools.screenshot(out_dir / "analysis.png")

                # 2. asymmetry detector
                await devtools.evaluate("document.getElementById('tab-asymmetry').click()")
                await devtools.evaluate("document.getElementById('asym-submit').click()")
                await devtools.wait_for(
                    "(() => { const r = document.getElementById('asym-results');"
                    " return r && !r.hidden && !r.classList.contains('is-loading')"
                    " && (document.getElementById('asym-score-value')||{}).textContent"
                    " && document.getElementById('asym-score-value').textContent.trim()"
                    " !== '\u2014'; })()"
                )
                await devtools.screenshot(out_dir / "asymmetry.png")

                # 3. FNBP lab
                await devtools.evaluate("document.getElementById('tab-lab').click()")
                await devtools.evaluate("document.getElementById('fnbp-submit').click()")
                await devtools.wait_for(
                    "(() => { const r = document.getElementById('fnbp-results');"
                    " return r && !r.hidden && document.querySelectorAll("
                    "  '#fnbp-log tr, #fnbp-log li, #fnbp-log div').length > 0; })()"
                )
                await devtools.screenshot(out_dir / "fnbp-lab.png")

            # 4. CLI capture, rendered from docs/cli-extreme.txt
            print("capturing CLI view...")
            await devtools.send(
                "Emulation.setDeviceMetricsOverride",
                {"width": 1180, "height": 900, "deviceScaleFactor": 2, "mobile": False},
            )
            await devtools.goto("about:blank")
            await devtools.evaluate(
                "document.open(); document.write("
                + json.dumps(cli_harness_html())
                + "); document.close();"
            )
            await asyncio.sleep(0.5)
            await devtools.screenshot(out_dir / "cli-extreme.png")
        return 0
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover
            process.kill()
        shutil.rmtree(profile, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture the NED README screenshots.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8742")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--port", type=int, default=9222, help="DevTools port")
    parser.add_argument("--browser", default=None, help="Path to chrome/msedge")
    parser.add_argument(
        "--cli-only",
        action="store_true",
        help="Only re-render the CLI image (no server needed)",
    )
    args = parser.parse_args()

    browser = find_browser(args.browser)
    print(f"browser : {browser}")
    print(f"out dir : {args.out_dir}")
    if not args.cli_only:
        print(f"server  : {args.base_url}")
        if os.name == "nt":
            pass
    return asyncio.run(
        capture(args.base_url, Path(args.out_dir), args.port, browser, args.cli_only)
    )


if __name__ == "__main__":
    sys.exit(main())
