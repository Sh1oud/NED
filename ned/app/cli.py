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
    AsymmetrySide,
    FnbpRequest,
    FnbpResult,
    Mode,
    Verdict,
)
from ned.app.ui.personality import (
    FORBIDDEN_EMOJI,
    GREETING_RULE,
    QUALITY_SOURCE,
    ROUTINE_CLAIM,
    SELF_DISCOUNT_SIGNAL_TYPES,
    SITUATION_EXPLANATION_AUDIT,
    PersonalityFeedback,
    analysis_feedback,
    audit_breakdown_rows,
    captured_reading,
    comedy_hypotheses,
    emoji_discipline,
    explicit_quality_label,
    fact_from_observed,
    fact_override,
    fact_signal_types,
    first_screen,
    fnbp_feedback,
    nea_framing,
    primary_positive_rule,
    quality_label,
    reading_basis_present,
    reading_message,
    repair_display_text,
    resolve_situation,
    screen_situation,
    verdict_display,
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


def bar(value: float | None, width: int = BAR_WIDTH, style: str = "") -> Text:
    """A block-character progress bar (no dependencies, no Unicode maths).

    ``None`` means no comparable number was produced, so the bar stays empty and
    the value reads as a dash instead of a misleading zero.
    """

    if value is None:
        text = Text()
        text.append("░" * width, style="dim")
        text.append("      —")
        return text

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


def personality_lines(feedback: PersonalityFeedback | None) -> tuple[Text, ...]:
    """Build display-only NED feedback for the human-readable CLI."""

    if feedback is None:
        return ()
    return (
        Text(f"Technical: {feedback.technical}", style="yellow"),
        Text(f"NED message: {feedback.zh}", style="bold yellow"),
        Text(feedback.en, style="dim"),
    )


def screen_context(result: AnalysisResult) -> tuple[str, bool, str]:
    """Which screen this result belongs to, whether the reader spoke, and the language."""

    base = resolve_situation(result.verdict.code)
    language = "en" if result.language == "en" else "zh"
    signal_types = [span.signal_type.value for span in result.evidence]
    basis = reading_basis_present(signal_types=signal_types)
    self_discount = any(item in SELF_DISCOUNT_SIGNAL_TYPES for item in signal_types)
    positive_evidence = any(span.polarity == "positive" for span in result.evidence)
    situation = screen_situation(
        base,
        self_discount=self_discount,
        positive_evidence=positive_evidence,
        audit=result.interpretation_audit is not None,
    )
    return situation, basis, language


def screen_fact(result: AnalysisResult, situation: str, language: str = "zh") -> str:
    """The observed fact, aligned with the screen the verdict produced.

    When the primary signal is the evidence that decided the screen, the engine's
    own reading is already about it. When it is not — a boundary inside an
    otherwise affectionate message, for instance — the screen shows the engine's
    label for the evidence that did decide it. Nothing is dropped: Technical
    Details still lists every span.
    """

    if fact_from_observed(situation):
        return (
            repair_display_text(result.observed_evidence)
            or result.signal_label
            or repair_display_text(result.raw_interpretation)
        )
    wanted = fact_signal_types(situation)
    if wanted and result.signal_type.value not in wanted:
        span = next(
            (item for item in result.evidence if item.signal_type.value in wanted),
            None,
        )
        if span is not None:
            return span.label or span.text
    shown = (
        repair_display_text(result.raw_interpretation)
        or result.observed_evidence
        or result.signal_label
    )
    # A single greeting is not a routine: display-only correction, input-driven.
    if ROUTINE_CLAIM in shown:
        corrected = fact_override(GREETING_RULE, result.input, language)
        if corrected:
            return corrected
    return shown


def screen_quality(situation: str, result: AnalysisResult, language: str) -> str:
    """Plain-language evidence quality, derived from engine readings only."""

    source = QUALITY_SOURCE.get(situation, "none")
    if source == "explicit":
        return explicit_quality_label(language)
    if source == "strength":
        return quality_label(result.signal_strength, language)
    if source == "negative_information":
        values = [
            span.information_content for span in result.evidence if span.polarity == "negative"
        ]
        return quality_label(max(values), language) if values else ""
    return ""


def panel_verdict(verdict: Verdict, situation: str, basis: bool, language: str) -> str:
    """Verdict sentence as this screen is allowed to show it.

    Boundary screens drop the boundary-forbidden emoji, both inside the sentence
    and in the separate emoji slot, without touching the verdict itself.
    """

    shown = emoji_discipline(
        situation,
        repair_display_text(
            verdict_display(verdict.code, verdict.text, basis=basis, language=language)
        ),
    )
    forbidden = FORBIDDEN_EMOJI.get(situation, ())
    if verdict.emoji and verdict.emoji in forbidden:
        return shown
    return verdict_text(verdict.emoji, shown)


def captured_reading_of(result: AnalysisResult) -> str:
    """The reader's own words, as the engine captured them.

    The discount span marks where the reading starts; the presentation layer
    extends it to the end of its clause so the quote is complete and still
    verbatim. Falls back to the pair layer's captured reading, then to nothing —
    and a screen with nothing to quote says so without quotation marks.
    """

    for span in result.evidence:
        if span.signal_type.value in SELF_DISCOUNT_SIGNAL_TYPES:
            found = captured_reading(result.input, span.start, span.end)
            if found:
                return found
    attached = result.asymmetry.user_interpretation if result.asymmetry is not None else None
    if attached is not None and attached.positive_reading:
        return attached.positive_reading
    return ""


def render_first_screen(
    result: AnalysisResult, situation: str, basis: bool, language: str, out: Console
) -> None:
    """NED's screen: title, observed fact, plain quality, one line, one reality check."""

    screen = first_screen(
        situation,
        result.mode,
        language,
        basis=basis,
        reading=captured_reading_of(result),
        rule=primary_positive_rule(result.evidence),
    )
    body = Table(show_header=False, box=None, padding=(0, 2))
    body.add_row("Observed evidence", Text(screen_fact(result, situation)))
    quality = screen_quality(situation, result, language)
    if quality:
        body.add_row("Evidence quality", Text(quality, style="bold white"))
    lines: list[Text] = [Text("")]
    lines.extend(Text(line, style="bold white") for line in screen.lines)
    lines.append(Text(""))
    lines.append(Text(screen.reality, style="dim italic"))
    out.print()
    out.print(
        Panel(
            Group(body, *lines),
            title=screen.title,
            border_style=SEVERITY_STYLE.get(result.verdict.severity, "white"),
        )
    )


def side_quality(side: AsymmetrySide | None, evidence_class: str, polarity: str) -> str:
    """Plain-language quality for one side of a comparison."""

    if side is None:
        return ""
    if evidence_class == "boundary":
        return explicit_quality_label("zh")
    reading = side.information_content if polarity == "negative" else side.raw_strength
    return quality_label(reading, "zh")


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


def render_epistemic_breakdown(result: AnalysisResult, situation: str, out: Console) -> None:
    """The expanded audit, and only under the screen that promised it.

    Stage 1 shows this card when the result actually reached the Alternative
    Explanation Audit. An audit recorded while a different screen decided the
    outcome — a boundary, a latency verdict, hostile input — stays out of the
    interface: relating those materials to the explanation is Stage 2's subject.
    """

    audit = result.interpretation_audit
    if audit is None or situation != SITUATION_EXPLANATION_AUDIT:
        return
    body = Table(show_header=False, box=None, padding=(0, 2))
    rows = audit_breakdown_rows(audit)
    for label, text in rows:
        body.add_row(label, Text(text))
    out.print(
        Panel(
            Group(
                body,
                Text(
                    "材料是输入报告的材料，不是本机构核实过的事实。",
                    style="dim italic",
                ),
            ),
            title="Epistemic Breakdown",
            border_style="cyan",
        )
    )


def render_analysis(result: AnalysisResult, out: Console) -> None:
    """Render an analysis result: NED's screen first, the evidence after it."""

    situation, basis, language = screen_context(result)
    render_first_screen(result, situation, basis, language, out)
    render_epistemic_breakdown(result, situation, out)
    out.print()
    out.print(Text("Technical Details " + "\u2500" * 44, style="dim"))
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
    for line in personality_lines(analysis_feedback(result.ned_reaching_level)):
        reaching.add_row("", line)
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
        comedy = comedy_hypotheses(primary_positive_rule(result.evidence))
        if comedy:
            for index, (text, category, plausibility) in enumerate(comedy, start=1):
                hypotheses.add_row(str(index), text, category, f"{plausibility:.0f}%")
        else:
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
        nea.add_row("Reality check", Text(repair_display_text(result.reality_check), style="green"))
        out.print(
            Panel(
                Group(
                    nea,
                    Text(nea_framing(result.language), style="dim italic"),
                ),
                title="Negative Evidence Amplifier",
                border_style="red",
            )
        )
    else:
        out.print(
            Panel(
                repair_display_text(result.reality_check),
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
                panel_verdict(result.verdict, situation, basis, language),
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
    """Render the three layers of an evidence comparison.

    Evidence Profile describes the clues, NED Treatment describes what the
    current mode does to them, and Your Reading is the only section allowed to
    say anything about the reader. The legacy composite is not printed.
    """

    profile = result.evidence_profile
    treatment = result.ned_treatment
    reading = result.user_interpretation

    def show(value: float | None, digits: int = 3) -> str:
        return "—" if value is None else f"{value:.{digits}f}"

    def _pct(value: float | None) -> str:
        return "—" if value is None else f"{value:.0f}%"

    profile_table = Table(box=None, show_header=True, header_style="bold", padding=(0, 2))
    profile_table.add_column("Side")
    profile_table.add_column("Evidence", overflow="fold")
    profile_table.add_column("Class")
    profile_table.add_column("Raw", justify="right")
    profile_table.add_column("Information", justify="right")
    for label, side in (("positive", result.positive), ("negative", result.negative)):
        if side is None:
            profile_table.add_row(label, "—", "—", "—", "—")
            continue
        profile_table.add_row(
            label,
            side.description or side.text,
            side.evidence_class or "—",
            f"{side.raw_strength:.0f}",
            f"{side.information_content:.0f}",
        )

    treatment_table = Table(show_header=False, box=None, padding=(0, 2))
    treatment_table.add_row("mode", Text(treatment.mode if treatment else "—"))
    treatment_table.add_row(
        "positive discount",
        Text(f"{treatment.positive_discount:.0f}%" if treatment else "—", style="bold yellow"),
    )
    treatment_table.add_row(
        "priors",
        Text(
            f"positive ×{treatment.prior_positive:g}  negative ×{treatment.prior_negative:g}"
            if treatment
            else "—"
        ),
    )
    treatment_table.add_row(
        "treated weights",
        Text(
            "positive "
            + _pct(treatment.positive_treated_weight if treatment else None)
            + "  negative "
            + _pct(treatment.negative_treated_weight if treatment else None),
        ),
    )
    treatment_table.add_row(
        "negative amplification",
        Text(
            _pct(treatment.negative_amplification if treatment else None),
            style="bold red",
        ),
    )
    treatment_table.add_row(
        "treatment gap",
        Text(
            show(treatment.treatment_gap) if treatment else "—",
            style="bold magenta",
        ),
    )

    reading_lines: list[Text] = [
        Text(f"status: {reading.status}", style="bold"),
    ]
    if reading.basis:
        reading_lines.append(Text(f"basis: {', '.join(reading.basis)}", style="dim"))
    if reading.positive_reading:
        reading_lines.append(Text(f"positive reading: {reading.positive_reading}", style="dim"))
    if reading.negative_reading:
        reading_lines.append(Text(f"negative reading: {reading.negative_reading}", style="dim"))
    reading_lines.append(
        Text(reading_message(reading.status, (result.mode and "zh") or "zh"), style="bold yellow")
    )

    situation = resolve_situation(result.verdict.code, profile.comparison_reason)
    basis = bool(reading.reading_present)
    screen = first_screen(situation, result.mode, "zh", basis=basis)

    screen_body = Table(show_header=False, box=None, padding=(0, 2))
    for label, side in (("positive", result.positive), ("negative", result.negative)):
        if side is None:
            screen_body.add_row(label, Text("\u2014"))
            continue
        screen_body.add_row(label, Text(side.description or side.text))
    screen_body.add_row(
        "evidence quality",
        Text(
            "positive "
            + (side_quality(result.positive, profile.positive_class, "positive") or "\u2014")
            + "  negative "
            + (side_quality(result.negative, profile.negative_class, "negative") or "\u2014"),
            style="bold white",
        ),
    )
    screen_lines: list[Text] = [Text(screen.title, style="bold white"), Text("")]
    screen_lines.extend(Text(line, style="bold white") for line in screen.lines)
    screen_lines.append(Text(""))
    screen_lines.append(Text(screen.reality, style="dim italic"))
    screen_lines.append(Text(""))
    screen_lines.append(Text("Technical Details", style="dim"))

    return Panel(
        Group(
            *screen_lines,
            screen_body,
            Text(""),
            Text("Evidence Profile", style="bold"),
            Text(
                f"comparable: {'yes' if profile.comparable else 'NO'}"
                f"   reason: {profile.comparison_reason or '—'}"
            ),
            profile_table,
            Text(
                f"raw strength gap: {show(profile.raw_strength_gap)}"
                f"   information gap: {show(profile.information_gap)}",
                style="dim",
            ),
            Text(""),
            Text("NED Treatment", style="bold"),
            treatment_table,
            Text(""),
            Text("Your Reading", style="bold"),
            *reading_lines,
            Text(""),
            Text(f"Reality check: {repair_display_text(result.reality_check)}", style="green"),
            Text(
                f"Verdict: {panel_verdict(result.verdict, situation, basis, 'zh')}",
                style="bold magenta",
            ),
        ),
        title="Evidence Comparison",
        border_style="magenta",
    )


def render_fnbp(result: FnbpResult, out: Console) -> None:
    """Render the branch-predictor easter egg as a pipeline log."""

    feedback = fnbp_feedback(result.prediction_misses)

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
                Text(feedback["title"], style="bold yellow"),
                Text(feedback["zh"], style="bold yellow"),
                Text(feedback["en"], style="dim"),
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
    """Compare two clues: the evidence first, your reasoning only if you stated it."""

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
