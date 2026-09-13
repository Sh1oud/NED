"""NED command line interface.

``ned`` is a thin, pretty adapter over :class:`ned.app.core.analyzer.NedAnalyzer`.
Every command also supports ``--json`` so the CLI can be scripted; the human
output is decoration, the JSON is the contract.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
from typing import Annotated, Any

import typer
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.models import (
    AnalysisResult,
    AsymmetryRequest,
    AsymmetryResult,
    FnbpRequest,
    FnbpResult,
    Mode,
)
from ned.app.version import FULL_NAME, MOTTO, NAME, SUBTITLE, TAGLINE, __version__

app = typer.Typer(
    name="ned",
    help=(
        "NED — Nov1ce Evidence Denier.\n\n"
        "When reality becomes suspiciously positive, NED restores uncertainty.\n"
        "Satire software. NED cannot determine whether someone likes you."
    ),
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)

SEVERITY_STYLE = {
    "info": "cyan",
    "warning": "yellow",
    "reject": "red",
    "chaos": "magenta",
}

BAR_WIDTH = 28

_analyzer: NedAnalyzer | None = None


def console() -> Console:
    """A console that survives non-UTF8 Windows terminals."""

    with contextlib.suppress(AttributeError, ValueError, OSError):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    return Console(highlight=False, soft_wrap=False)


def get_analyzer() -> NedAnalyzer:
    """Lazily build the analyzer so ``ned version`` stays instant."""

    global _analyzer
    if _analyzer is None:
        _analyzer = NedAnalyzer()
    return _analyzer


def bar(value: float, width: int = BAR_WIDTH, style: str = "") -> Text:
    """A block-character progress bar (no dependencies, no Unicode maths)."""

    filled = round(max(0.0, min(100.0, value)) / 100.0 * width)
    text = Text()
    text.append("█" * filled, style=f"bold {style}".strip())
    text.append("░" * (width - filled), style="dim")
    text.append(f"  {value:5.1f}%")
    return text


def reaching_style(level: float) -> str:
    if level >= 100:
        return "bold magenta"
    if level >= 80:
        return "bold yellow"
    if level >= 60:
        return "yellow"
    return "cyan"


def emit(payload: Any, as_json: bool) -> bool:
    """Print JSON when asked, otherwise return False so callers render richly."""

    if not as_json:
        return False
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    return True


def verdict_text(emoji: str, text: str) -> str:
    """Render a verdict without repeating an emoji the text already contains."""

    if not emoji or emoji in text:
        return text
    return f"{emoji} {text}"


def render_analysis(result: AnalysisResult, out: Console) -> None:
    """Render an analysis result as a lab report."""

    out.print()
    out.print(
        Panel(
            Group(
                Text(f"{NAME} — {FULL_NAME}", style="bold white"),
                Text(SUBTITLE, style="dim"),
                Text(""),
                Text(f"input      : {result.input}"),
                Text(f"mode       : {result.mode}"),
                Text(f"language   : {result.language}"),
                Text(f"signal     : {result.signal_type.value} — {result.signal_label}"),
                Text(f"raw reading: {result.raw_interpretation}", style="dim"),
            ),
            title="Analysis",
            border_style="cyan",
        )
    )

    strength = Table(show_header=False, box=None, padding=(0, 2))
    strength.add_row("Evidence strength", bar(result.signal_strength))
    strength.add_row("Positive discount", bar(result.positive_evidence_discount))
    strength.add_row("Negative amplification", bar(result.negative_evidence_amplification))
    out.print(Panel(strength, title="Scoring", border_style="cyan"))

    reaching = Table(show_header=False, box=None, padding=(0, 2))
    reaching.add_row(
        "NED Reaching Level",
        bar(result.ned_reaching_level, style=reaching_style(result.ned_reaching_level)),
    )
    reaching.add_row(
        "", Text(result.reaching_label, style=reaching_style(result.ned_reaching_level))
    )
    if result.ned_reaching_level >= 80:
        reaching.add_row("", Text("NED is currently reaching.", style="bold yellow"))
    out.print(
        Panel(
            reaching,
            title="NED Reaching Level",
            border_style=reaching_style(result.ned_reaching_level),
        )
    )

    if result.alternative_explanations:
        hypotheses = Table(box=None, show_header=True, header_style="bold", padding=(0, 1))
        hypotheses.add_column("#", width=3, justify="right")
        hypotheses.add_column("Alternative hypothesis", overflow="fold")
        hypotheses.add_column("Category", style="dim")
        hypotheses.add_column("Plausibility", justify="right")
        for index, explanation in enumerate(result.alternative_explanations, start=1):
            hypotheses.add_row(
                str(index),
                explanation.hypothesis,
                explanation.category,
                f"{explanation.plausibility:.0f}%",
            )
        out.print(
            Panel(
                Group(
                    hypotheses,
                    Text(
                        "These are generated alternative hypotheses, not findings.",
                        style="dim italic",
                    ),
                ),
                title="Alternative Hypotheses",
                border_style="cyan",
            )
        )

    if result.observed_evidence:
        nea = Table(show_header=False, box=None, padding=(0, 2))
        nea.add_row("Observed evidence", result.observed_evidence)
        nea.add_row(
            "Amplified reading",
            Text(result.irrational_amplification, style="red"),
        )
        nea.add_row("Reality check", Text(result.reality_check, style="green"))
        out.print(
            Panel(
                nea,
                title="Negative Evidence Amplifier",
                border_style="red",
            )
        )
    else:
        out.print(
            Panel(
                result.reality_check,
                title="Reality Check",
                border_style="green",
            )
        )

    if result.asymmetry is not None:
        out.print(render_asymmetry_panel(result.asymmetry))

    verdict_style = SEVERITY_STYLE.get(result.verdict.severity, "white")
    out.print(
        Panel(
            Text(
                verdict_text(result.verdict.emoji, result.verdict.text),
                style=f"bold {verdict_style}",
            ),
            title=f"Final Verdict ({result.verdict.code})",
            border_style=verdict_style,
        )
    )

    if result.mode_notes:
        notes = Table(show_header=False, box=None, padding=(0, 1))
        for note in result.mode_notes:
            notes.add_row(Text(f"· {note}", style="dim"))
        out.print(Panel(notes, title="Mode Notes", border_style="dim"))

    out.print(
        Text(
            f"{result.disclaimer}",
            style="dim",
        )
    )
    out.print(
        Text(
            f"engine {result.engine.name} v{result.engine.version} "
            f"(provider={result.engine.provider}, offline={result.engine.offline})",
            style="dim",
        )
    )
    out.print()


def render_asymmetry_panel(result: AsymmetryResult) -> Panel:
    """Render an asymmetry report."""

    table = Table(box=None, show_header=True, header_style="bold", padding=(0, 1))
    table.add_column("Side")
    table.add_column("Evidence", overflow="fold")
    table.add_column("Raw", justify="right")
    table.add_column("Weight", justify="right")
    table.add_column("Information", justify="right")

    for label, side in (("positive", result.positive), ("negative", result.negative)):
        if side is None:
            table.add_row(label, "—", "—", "—", "—")
            continue
        table.add_row(
            label,
            side.description or side.text,
            f"{side.raw_strength:.0f}",
            f"{side.weight:.0f}%",
            f"{side.information_content:.0f}",
        )

    scores = Table(show_header=False, box=None, padding=(0, 2))
    scores.add_row("Positive threshold", Text(result.positive_threshold, style="bold yellow"))
    scores.add_row("Negative threshold", Text(result.negative_threshold, style="bold red"))
    scores.add_row("Asymmetry score", bar(result.asymmetry_score, style="magenta"))
    scores.add_row("", Text(result.asymmetry_label, style="bold magenta"))

    return Panel(
        Group(
            table,
            Text(""),
            scores,
            Text(""),
            Text(f"Reality check: {result.reality_check}", style="green"),
            Text(
                f"Verdict: {verdict_text(result.verdict.emoji, result.verdict.text)}",
                style="bold magenta",
            ),
        ),
        title="Evidence Asymmetry Detector",
        border_style="magenta",
    )


def render_fnbp(result: FnbpResult, out: Console) -> None:
    """Render the branch-predictor easter egg as a pipeline log."""

    log = Table(show_header=False, box=None, padding=(0, 1))
    for item in result.per_notification:
        status = "HIT" if item.hit else "MISPREDICT"
        style = "green" if item.hit else "red"
        log.add_row(
            Text(
                f"[{item.index:02d}] predicted={item.predicted_sender} "
                f"p={item.predicted_probability / 100:.2f} actual={item.actual_sender} -> {status}",
                style=style,
            )
        )
        if item.pipeline_flushed:
            log.add_row(Text("     PIPELINE FLUSHED", style="dim red"))

    stats = Table(show_header=False, box=None, padding=(0, 2))
    stats.add_row("notifications", str(result.notifications))
    stats.add_row("hits / misses", f"{result.prediction_hits} / {result.prediction_misses}")
    stats.add_row("mispredict rate", f"{result.mispredict_rate:.1f}%")
    stats.add_row("pipeline flushes", str(result.pipeline_flushes))
    stats.add_row("wasted cycles", str(result.wasted_cycles))

    out.print(
        Panel(
            Group(
                log,
                Text(""),
                stats,
                Text(""),
                Text(
                    f"Verdict: {verdict_text(result.verdict.emoji, result.verdict.text)}",
                    style="bold magenta",
                ),
                Text(result.codename_note, style="dim"),
            ),
            title="FNBP — Fuyuki Notification Branch Predictor",
            border_style="magenta",
        )
    )


@app.command()
def analyze(
    text: Annotated[str, typer.Argument(help="A message, or a description of what happened.")],
    mode: Annotated[
        str, typer.Option("--mode", "-m", help="normal | scientific | extreme")
    ] = "normal",
    history: Annotated[
        list[str] | None,
        typer.Option("--history", "-H", help="Earlier turns, oldest first. Repeatable."),
    ] = None,
    top_k: Annotated[
        int | None, typer.Option("--top-k", help="Limit the number of alternative explanations.")
    ] = None,
    as_json: Annotated[bool, typer.Option("--json", help="Emit the raw JSON report.")] = False,
) -> None:
    """Analyze one message or event description."""

    out = console()
    validated = _validate_mode(mode, out)
    if validated is None:
        raise typer.Exit(code=2)
    result = get_analyzer().analyze_text(text, mode=validated, history=history or [], top_k=top_k)
    if emit(result, as_json):
        return
    render_analysis(result, out)


@app.command()
def asymmetry(
    positive: Annotated[str, typer.Option("--positive", "-p", help="The positive evidence.")] = "",
    negative: Annotated[str, typer.Option("--negative", "-n", help="The negative evidence.")] = "",
    text: Annotated[
        str,
        typer.Option("--text", "-t", help="Free text; NED splits it into clauses itself."),
    ] = "",
    mode: Annotated[str, typer.Option("--mode", "-m")] = "normal",
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Compare two evidence standards (the double standard detector)."""

    out = console()
    validated = _validate_mode(mode, out)
    if validated is None:
        raise typer.Exit(code=2)
    if not (positive or negative or text):
        out.print(
            "[red]Supply --positive/--negative, or --text.[/red] "
            "NED cannot compare evidence it has not been given."
        )
        raise typer.Exit(code=2)
    request = AsymmetryRequest(
        positive_text=positive or None,
        negative_text=negative or None,
        text=text or None,
        mode=validated,
    )
    result = get_analyzer().compare(request)
    if emit(result, as_json):
        return
    out.print()
    out.print(render_asymmetry_panel(result))
    out.print(Text(result.disclaimer, style="dim"))
    out.print()


@app.command()
def fnbp(
    expected: Annotated[
        str, typer.Option("--expected", help="Who you were waiting for.")
    ] = "Fuyuki",
    actual: Annotated[
        list[str] | None,
        typer.Option("--actual", help="Who actually messaged. Repeatable."),
    ] = None,
    count: Annotated[int, typer.Option("--count", "-c", help="How many notifications.")] = 5,
    seed: Annotated[int, typer.Option("--seed", help="Kept for reproducibility of reports.")] = 7,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Fuyuki Notification Branch Predictor (an easter egg, not an analysis)."""

    out = console()
    request = FnbpRequest(
        expected_sender=expected,
        actual_senders=actual or ["张三", "李四"],
        notifications=count,
        seed=seed,
    )
    result = get_analyzer().fnbp_analysis(request)
    if emit(result, as_json):
        return
    out.print()
    render_fnbp(result, out)
    out.print()


@app.command()
def demo(
    mode: Annotated[
        str,
        typer.Option("--mode", "-m", help="auto (each case's own mode) or a specific mode."),
    ] = "auto",
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Run the shipped example cases end to end."""

    out = console()
    validated: Mode | None = None
    if mode != "auto":
        validated = _validate_mode(mode, out)
        if validated is None:
            raise typer.Exit(code=2)
    analyzer = get_analyzer()
    cases = analyzer.examples()
    if not cases:
        out.print("[yellow]No example cases found.[/yellow]")
        raise typer.Exit(code=1)

    out.print()
    if not as_json:
        out.print(
            Panel(
                Group(
                    Text(f"{NAME} — {FULL_NAME}", style="bold"),
                    Text(TAGLINE),
                    Text(MOTTO, style="dim"),
                ),
                title="Demo",
                border_style="cyan",
            )
        )
    payload: list[dict[str, Any]] = []
    for case in cases:
        case_mode = validated or _as_mode(case.mode)
        result = analyzer.analyze_text(case.text, mode=case_mode)
        if as_json:
            payload.append(result.model_dump(mode="json"))
            continue
        out.print()
        out.print(Text(f"case {case.id} [mode={case_mode}] {case.text}", style="bold white"))
        if case.note:
            out.print(Text(f"  note: {case.note}", style="dim"))
        out.print(
            Text.assemble(
                "  reaching ",
                bar(result.ned_reaching_level),
                Text(f"  {result.reaching_label}"),
            )
        )
        out.print(
            Text(
                f"  verdict: {verdict_text(result.verdict.emoji, result.verdict.text)}",
                style=SEVERITY_STYLE.get(result.verdict.severity, "white"),
            )
        )
    if as_json:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    out.print()


@app.command()
def examples(
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """List the shipped example cases."""

    out = console()
    cases = get_analyzer().examples()
    if as_json:
        typer.echo(
            json.dumps(
                [case.model_dump(mode="json") for case in cases], ensure_ascii=False, indent=2
            )
        )
        return
    table = Table(box=None, show_header=True, header_style="bold", padding=(0, 1))
    table.add_column("id")
    table.add_column("mode")
    table.add_column("text", overflow="fold")
    table.add_column("note", style="dim", overflow="fold")
    for case in cases:
        table.add_row(case.id, case.mode, case.text, case.note)
    out.print()
    out.print(table)
    out.print()


@app.command()
def version() -> None:
    """Print version information."""

    out = console()
    out.print(f"{NAME} — {FULL_NAME} v{__version__}")
    out.print(TAGLINE)
    out.print(MOTTO)


@app.command()
def serve(
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port")] = 8000,
    reload: Annotated[bool, typer.Option("--reload", help="Auto-reload for development.")] = False,
) -> None:
    """Run the local web UI and REST API (never binds a public interface by default)."""

    out = console()
    try:
        import uvicorn
    except ImportError:  # pragma: no cover - uvicorn is a hard dependency
        out.print("[red]uvicorn is not installed. Run: pip install -e .[/red]")
        raise typer.Exit(code=1) from None

    out.print(f"NED v{__version__} — {TAGLINE}")
    out.print(f"UI      : http://{host}:{port}/")
    out.print(f"API docs: http://{host}:{port}/docs")
    out.print("Local-first: your messages stay on your machine.")
    if os.environ.get("NED_RULES_DIR"):
        out.print(f"Rule packs: {os.environ['NED_RULES_DIR']}")
    uvicorn.run("ned.app.main:app", host=host, port=port, reload=reload, log_level="info")


def _as_mode(value: str) -> Mode:
    if value in ("normal", "scientific", "extreme"):
        return value  # type: ignore[return-value]
    return "normal"


def _validate_mode(value: str, out: Console) -> Mode | None:
    if value in ("normal", "scientific", "extreme"):
        return value  # type: ignore[return-value]
    out.print(f"[red]Unknown mode:[/red] {value}. Use normal, scientific or extreme.")
    return None


def main() -> None:
    """Console-script entry point."""

    app()


if __name__ == "__main__":  # pragma: no cover
    main()
