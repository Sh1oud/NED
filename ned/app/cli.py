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
from pathlib import Path
from typing import Annotated, Any, cast
from uuid import uuid4

import typer
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ned.app.api.review import build_review
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
from ned.app.review import (
    CasebookReview,
    RecordedCaseFile,
    RecordedEntry,
    RereadResult,
    reread_case_file,
)
from ned.app.store import (
    CasebookConfigError,
    CasebookDisabledError,
    CasebookError,
    CasebookNotFoundError,
    CasebookStore,
    CaseFileRecord,
    IdempotencyConflictError,
    OccurredPrecision,
    OccurredTime,
    build_case_file_snapshot,
    casebook_enabled,
    casebook_path,
    open_casebook,
    rules_fingerprint,
)
from ned.app.ui.personality import (
    ASPECT_CARD_SITUATIONS,
    AUDIT_COPY,
    BOUNDARY_SITUATIONS,
    FORBIDDEN_EMOJI,
    GREETING_RULE,
    QUALITY_SOURCE,
    READING_SIGNAL_TYPES,
    ROUTINE_CLAIM,
    SELF_DISCOUNT_SIGNAL_TYPES,
    SITUATION_EXPLANATION_AUDIT,
    SITUATION_MATERIAL_ONLY,
    PersonalityFeedback,
    analysis_feedback,
    aspect_breakdown_rows,
    aspect_copy,
    audit_breakdown_rows,
    captured_reading,
    comedy_hypotheses,
    emoji_discipline,
    explicit_quality_label,
    fact_fixed,
    fact_from_observed,
    fact_override,
    fact_signal_types,
    first_screen,
    fnbp_feedback,
    material_registry_copy,
    material_registry_rows,
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
        aspects=result.material_aspects is not None,
        reader_conclusion=any(item in READING_SIGNAL_TYPES for item in signal_types),
    )
    if result.recognition == "material_registered":
        # PR-2: material was filed but nothing could be adjudicated. That is its own screen,
        # not the empty one: the reader has to be told what was heard.
        situation = SITUATION_MATERIAL_ONLY
    return situation, basis, language


def registered_materials_of(result: AnalysisResult) -> tuple[str, ...]:
    """The verbatim material records this analysis filed, in input order."""

    return tuple(
        item.reported_content for item in (result.materials or []) if item.reported_content
    )


def material_pages_of(result: AnalysisResult) -> tuple[str, ...]:
    """The pages this result filed, in the order the input reported them."""

    aspects = result.material_aspects
    if aspects is None:
        return ()
    return tuple(item.text for item in aspects.materials)


def screen_fact(result: AnalysisResult, situation: str, language: str = "zh") -> str:
    """The observed fact, aligned with the screen the verdict produced.

    When the primary signal is the evidence that decided the screen, the engine's
    own reading is already about it. When it is not — a boundary inside an
    otherwise affectionate message, for instance — the screen shows the engine's
    label for the evidence that did decide it. Nothing is dropped: Technical
    Details still lists every span.
    """

    fixed = fact_fixed(situation, language)
    if fixed:
        return fixed
    if situation == SITUATION_MATERIAL_ONLY:
        # PR-2: the reader must be able to see what NED actually heard. The screen line below
        # quotes the filed material verbatim; this row only states how much was filed.
        count = len(registered_materials_of(result))
        if language == "en":
            return f"Material on file: {count}. None of it can be signed on its own."
        return f"已登记材料 {count} 条，均不足以单独签发结论。"
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
        materials=registered_materials_of(result)
        if situation == SITUATION_MATERIAL_ONLY
        else material_pages_of(result),
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
                # The restraint sentence is the audit card's own copy; reading it here
                # instead of repeating it keeps one source for the sentence.
                Text(AUDIT_COPY["disclaimer"], style="dim italic"),
            ),
            title="Epistemic Breakdown",
            border_style="cyan",
        )
    )


def render_aspect_breakdown(result: AnalysisResult, situation: str, out: Console) -> None:
    """The page-by-page filing card, and only where Stage 2 promised one.

    Shown under the multiple-aspects screen, and — in the serious register —
    under a stated boundary, where it records that the other material is still
    on file and does not weaken the boundary. Never under hostility: a hostile
    input gets no "two sides" framing at all.
    """

    aspects = result.material_aspects
    if aspects is None or situation not in ASPECT_CARD_SITUATIONS:
        return
    language = "en" if result.language == "en" else "zh"
    body = Table(show_header=False, box=None, padding=(0, 2))
    for label, text in aspect_breakdown_rows(
        aspects, result.evidence, situation=situation, language=language
    ):
        body.add_row(label, Text(text))
    out.print(
        Panel(
            Group(
                body,
                Text(aspect_copy(situation, language)["disclaimer"], style="dim italic"),
            ),
            title="Multiple Aspects Breakdown",
            border_style="cyan",
        )
    )


def render_material_registry(result: AnalysisResult, situation: str, out: Console) -> None:
    """The materials this input reported: registered, and nothing more.

    A material is what the input reports. It is not evidence, and registering it
    decides nothing: the card names the reported statements and their provenance,
    restates that this agency has verified nothing, and says out loud that none of
    it was converted into a conclusion.

    Under a stated boundary the card is not shown at all. An explicit boundary
    outranks any material presentation, and one input can carry both - a reported
    attitude and a plainly stated boundary - so this gate is load-bearing, not
    decorative. The JSON payload is untouched either way: only this screen is
    withheld.
    """

    if not result.materials or situation in BOUNDARY_SITUATIONS:
        return
    language = "en" if result.language == "en" else "zh"
    copy = material_registry_copy(language)
    body = Table(show_header=False, box=None, padding=(0, 2))
    for label, text in material_registry_rows(result.materials, language):
        body.add_row(label, Text(text))
    out.print(
        Panel(
            Group(
                Text(copy["registration_intro"]),
                body,
                Text(copy["disclaimer"], style="dim italic"),
                Text(copy["conclusion_isolation"], style="dim italic"),
            ),
            title=copy["card_title"],
            border_style="cyan",
        )
    )


def render_analysis(result: AnalysisResult, out: Console) -> None:
    """Render an analysis result: NED's screen first, the evidence after it."""

    situation, basis, language = screen_context(result)
    render_first_screen(result, situation, basis, language, out)
    render_epistemic_breakdown(result, situation, out)
    render_aspect_breakdown(result, situation, out)
    render_material_registry(result, situation, out)
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


RELATION_LABELS: dict[str, str] = {
    "supports": "supports",
    "conflicts": "conflicts",
    "superseded": "superseded by a later boundary",
    "unrelated": "unrelated",
    "not_comparable": "not comparable",
    "insufficient": "insufficient record",
}

SUMMARY_LINES: dict[str, str] = {
    "no_history": "the casebook holds nothing to compare with this input yet",
    "nothing_comparable": "nothing in the casebook could be compared with this input",
    "current_case_has_no_direction": "this input has no direction of its own to compare against",
    "boundary_governs": "an earlier record does not overturn a later explicit boundary",
    "order_unknown": "the casebook's order could not be established",
    "mixed_directions": "the casebook holds records that read both ways about this input",
    "only_supports": "the casebook reads the same way, which still proves nothing on its own",
    "only_conflicts": "the casebook reads against this input",
}


def examine_occurred(occurred: str | None, precision: str) -> OccurredTime:
    """The reader's own event time for the input being analysed, validated by the store's model."""

    allowed = ("year", "month", "day", "hour", "minute", "second", "unknown")
    if precision not in allowed:
        raise ValueError(
            "--precision must be one of {}, not {!r}".format(", ".join(allowed), precision)
        )
    return OccurredTime(
        occurred_at=occurred,
        occurred_precision=cast(OccurredPrecision, precision if occurred else "unknown"),
        occurred_source="user" if occurred else "unknown",
    )


REREAD_LABELS: dict[str, str] = {
    "same": "same",
    "changed": "changed",
    "missing": "missing today",
    "ambiguous": "ambiguous (not guessed)",
    "new": "new today",
}


def render_reread(result: RereadResult, out: Console) -> None:
    """Print the two readings side by side: what was recorded, and what today says."""

    out.print()
    out.print(
        Text(
            f"Reread - {result.casebook_label} / {result.case_file_id}",
            style="bold white",
        )
    )
    out.print(Text("This is a reread, not a rewrite: the archive below is unchanged.", style="dim"))
    out.print(Text(f"input      {result.input_text}", style="dim"))
    recorded = result.as_recorded
    reread = result.as_reread
    out.print(
        Text(
            f"recorded   {recorded.engine} {recorded.engine_version} · "
            f"rules {recorded.rules_version} ({recorded.rules_fingerprint})"
        )
    )
    out.print(
        Text(f"           {result.as_recorded.recognition} / {result.as_recorded.verdict_code}")
    )
    out.print(
        Text(
            f"today      {reread.engine} {reread.engine_version} · "
            f"rules {reread.rules_version} ({reread.rules_fingerprint})"
        )
    )
    out.print(Text(f"           {result.as_reread.recognition} / {result.as_reread.verdict_code}"))
    table = Table(box=None, show_header=True, header_style="bold", padding=(0, 1))
    table.add_column("class")
    table.add_column("recorded")
    table.add_column("today")
    table.add_column("fields")
    for row in result.alignment:
        table.add_row(
            REREAD_LABELS.get(str(row.difference), str(row.difference)),
            row.recorded_slice or row.recorded_kind or "-",
            row.reread_slice or row.reread_kind or "-",
            ", ".join(row.changed_fields) or ("rule id" if row.rule_id_changed else "-"),
        )
    out.print(table)
    counts = result.counts
    out.print(
        Text(
            "counts: "
            f"same {counts.same} · changed {counts.changed} · missing {counts.missing} · "
            f"ambiguous {counts.ambiguous} · new {counts.new} · rule-id only {counts.rule_id_only}",
            style="dim",
        )
    )
    if result.case_level_changed:
        out.print(Text("case level: " + ", ".join(result.case_level_changed), style="bold"))
    out.print(Text(f"note: {result.note_code}", style="dim"))
    out.print()


def render_casebook_review(review: CasebookReview, out: Console) -> None:
    """The casebook opinion, printed beside the report: relations and counts, never a score."""

    out.print()
    out.print(
        Text(
            f"Casebook review - {review.casebook_label} "
            f"({review.case_files_read} case file(s), {review.entries_read} entr(ies))",
            style="bold white",
        )
    )
    out.print(
        Text(
            "This is a parallel reading, not a new verdict: the report above is unchanged.",
            style="dim",
        )
    )
    table = Table(box=None, show_header=True, header_style="bold", padding=(0, 1))
    table.add_column("date")
    table.add_column("relation")
    table.add_column("record")
    for item in review.items:
        label = RELATION_LABELS.get(str(item.relation), str(item.relation))
        if item.governing:
            label = "governing boundary"
        when = item.occurred_at if item.occurred_precision != "unknown" else None
        table.add_row(when or "-", label, item.reported_content)
    out.print(table)
    counts = review.counts
    out.print(
        Text(
            "counts: "
            f"supports {counts.supports} · conflicts {counts.conflicts} · "
            f"superseded {counts.superseded} · not comparable {counts.not_comparable} · "
            f"unrelated {counts.unrelated} · insufficient {counts.insufficient}",
            style="dim",
        )
    )
    opinion = SUMMARY_LINES.get(str(review.summary_code), str(review.summary_code))
    out.print(Text(f"casebook opinion: {opinion}", style="bold"))
    if review.governing is not None:
        when = review.governing.occurred_at or "no declared date"
        out.print(Text(f"governing: {when} · {review.governing.reported_content}", style="dim"))
    out.print()


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
    with_casebook: Annotated[
        str | None,
        typer.Option(
            "--with-casebook",
            help="Review this input against one casebook (id or label). Off by default.",
        ),
    ] = None,
    occurred: Annotated[
        str | None,
        typer.Option("--occurred", help="When *this* input happened, for the review's ordering."),
    ] = None,
    precision: Annotated[
        str, typer.Option("--precision", help="year/month/day/hour/minute/second")
    ] = "day",
    as_json: Annotated[bool, typer.Option("--json", help="Emit the raw JSON report.")] = False,
) -> None:
    """Analyze one message or event description.

    The review is explicit: without ``--with-casebook`` nothing is read, and the report is exactly
    the report NED has always printed.
    """

    out = console()
    validated = _validate_mode(mode, out)
    if validated is None:
        raise typer.Exit(code=2)
    result = get_analyzer().analyze_text(text, mode=validated, history=history or [], top_k=top_k)
    if with_casebook is None:
        if occurred is not None or precision != "day":
            raise _casebook_error(
                CasebookConfigError(
                    "--occurred/--precision only mean something with --with-casebook"
                )
            )
        if emit(result, as_json):
            return
        render_analysis(result, out)
        return
    try:
        occurred_time = examine_occurred(occurred, precision)
    except ValueError as error:
        raise _casebook_error(CasebookConfigError(str(error))) from error
    store = _open_store()
    with store:
        casebook_id = _resolve_casebook(store, with_casebook)
        review = build_review(store, casebook_id=casebook_id, result=result, occurred=occurred_time)
    payload = result.model_dump(mode="json")
    payload["casebook_review"] = review.model_dump(mode="json")
    if emit(payload, as_json):
        return
    render_analysis(result, out)
    render_casebook_review(review, out)


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


casebook_app = typer.Typer(
    help="Manage the local casebook. It is off unless NED_CASEBOOK=on.",
    no_args_is_help=True,
)
app.add_typer(casebook_app, name="casebook")


def _casebook_error(error: Exception) -> typer.Exit:
    """Every casebook failure ends the same way: the reason, then a non-zero exit."""

    console().print(f"[red]{error}[/red]")
    return typer.Exit(code=1)


def _open_store() -> CasebookStore:
    """Open the casebook or stop, with the reason printed."""

    try:
        store = open_casebook()
    except (CasebookError, CasebookConfigError) as error:
        raise _casebook_error(error) from error
    if store is None:
        raise _casebook_error(
            CasebookDisabledError(
                "the casebook is switched off on this machine; set NED_CASEBOOK=on "
                "(and optionally NED_CASEBOOK_PATH) to use it"
            )
        )
    return store


def _resolve_casebook(store: CasebookStore, value: str) -> str:
    """Accept a casebook id or its label; a label must be unambiguous."""

    for record in store.list_casebooks():
        if record.casebook_id == value:
            return record.casebook_id
    matches = [record for record in store.list_casebooks() if record.label == value]
    if not matches:
        raise _casebook_error(CasebookNotFoundError(f"no casebook {value!r}"))
    if len(matches) > 1:
        ids = ", ".join(record.casebook_id for record in matches)
        raise _casebook_error(
            CasebookConfigError(f"the label {value!r} matches several casebooks: {ids}")
        )
    return matches[0].casebook_id


def _case_file_panel(store: CasebookStore, record: CaseFileRecord) -> Panel:
    """One case file as the reader should see it: what, when, what state, what material."""

    when = record.occurred_at or "time unknown"
    if record.occurred_at is None and record.occurred_source == "input_relative":
        when = "the input mentions a relative time; no date was ever recorded"
    lines = [
        Text(f"input      {record.input_text}", overflow="fold"),
        Text(f"occurred   {when}  ({record.occurred_precision}/{record.occurred_source})"),
        Text(f"saved      {record.saved_at}"),
        Text(f"generated  {record.generated_at}"),
        Text(
            f"state      {record.recognition} / {record.verdict_code} ({record.verdict_severity})"
        ),
        Text(f"reading    {record.verdict_text}", overflow="fold"),
        Text(
            f"engine     {record.engine_name} {record.engine_version}, "
            f"rules {record.rules_version} ({record.rules_fingerprint})"
        ),
    ]
    entries = store.list_entries(case_file_id=record.case_file_id)
    if not entries:
        lines.append(Text("material   none registered for this input"))
    for entry in entries:
        lines.append(
            Text(
                f"material   [{entry.entry_kind}/{entry.material_kind}] {entry.reported_content} "
                f"(offsets {entry.start_offset}-{entry.end_offset}, "
                f"{entry.source_kind}/{entry.reporter_role}, {entry.origin_rule_id})"
            )
        )
    return Panel(
        Text.assemble(*[Text("\n").join(lines)]),
        title=f"{record.case_file_id} · {record.mode} · {record.language}",
        border_style="dim",
        expand=False,
    )


@casebook_app.command("status")
def casebook_status() -> None:
    """Whether the casebook is available on this machine, and what is on file."""

    out = console()
    try:
        enabled = casebook_enabled()
        path = casebook_path() if enabled else None
    except CasebookConfigError as error:
        raise _casebook_error(error) from error
    out.print()
    out.print(f"casebook   {'on' if enabled else 'off'}")
    if path is not None:
        out.print(f"file       {path}")
        if path.exists():
            store = CasebookStore.open_read_only(path)
            with store:
                stats = store.stats()
            out.print(
                f"on file    {stats['casebooks']} casebook(s), {stats['case_files']} case file(s), "
                f"{stats['entries']} entr(ies)"
            )
        else:
            out.print("on file    nothing yet; the file is created by the first archive")
    out.print()


@casebook_app.command("list")
def casebook_list() -> None:
    """List the casebooks on this machine."""

    out = console()
    store = _open_store()
    with store:
        records = store.list_casebooks()
        table = Table(box=None, show_header=True, header_style="bold", padding=(0, 1))
        table.add_column("casebook")
        table.add_column("label")
        table.add_column("case files", justify="right")
        table.add_column("entries", justify="right")
        table.add_column("created", style="dim")
        for record in records:
            table.add_row(
                record.casebook_id,
                record.label,
                str(len(store.list_case_files(record.casebook_id))),
                str(len(store.list_entries(casebook_id=record.casebook_id))),
                record.created_at,
            )
    out.print()
    if not records:
        out.print("no casebooks yet")
    else:
        out.print(table)
    out.print()


@casebook_app.command("create")
def casebook_create(
    label: Annotated[str, typer.Option("--label", help="What to call this casebook.")],
    note: Annotated[str, typer.Option("--note", help="Optional subject note.")] = "",
) -> None:
    """Create a casebook (a subject scope the reader names)."""

    out = console()
    store = _open_store()
    with store:
        record = store.create_casebook(label, note)
    out.print()
    out.print(f"created casebook {record.casebook_id} ({record.label})")
    out.print()


@casebook_app.command("rename")
def casebook_rename(
    casebook: Annotated[str, typer.Option("--casebook", help="Casebook id or label.")],
    label: Annotated[str, typer.Option("--label", help="The new display name.")],
) -> None:
    """Change a casebook's display name. History is untouched."""

    out = console()
    store = _open_store()
    with store:
        casebook_id = _resolve_casebook(store, casebook)
        record = store.update_casebook(casebook_id, label=label)
    out.print()
    out.print(f"renamed {record.casebook_id} to {record.label}")
    out.print()


@casebook_app.command("show")
def casebook_show(
    casebook: Annotated[str, typer.Option("--casebook", help="Casebook id or label.")],
) -> None:
    """Show one casebook: its case files, their state and their material."""

    out = console()
    store = _open_store()
    with store:
        casebook_id = _resolve_casebook(store, casebook)
        record = store.get_casebook(casebook_id)
        case_files = store.list_case_files(casebook_id)
        out.print()
        out.print(f"{record.label}  ({record.casebook_id})")
        if record.subject_note:
            out.print(f"note: {record.subject_note}")
        if not case_files:
            out.print("nothing filed in this casebook yet")
        for case_file in case_files:
            out.print(_case_file_panel(store, case_file))
    out.print()


@casebook_app.command("archive")
def casebook_archive(
    casebook: Annotated[str, typer.Option("--casebook", help="Casebook id or label.")],
    text: Annotated[str, typer.Option("--text", help="The input to file.")] = "",
    file: Annotated[str | None, typer.Option("--file", help="Read the input from a file.")] = None,
    mode: Annotated[str, typer.Option("--mode")] = "normal",
    occurred: Annotated[
        str | None, typer.Option("--occurred", help="Event date/time the reader declares.")
    ] = None,
    precision: Annotated[
        str, typer.Option("--precision", help="year/month/day/hour/minute/second")
    ] = "day",
    action_id: Annotated[
        str | None,
        typer.Option("--action-id", help="Reuse to make a retry idempotent; default is a new one."),
    ] = None,
) -> None:
    """Analyse the input with NED and file that analysis into the casebook."""

    out = console()
    if bool(text) == bool(file):
        raise _casebook_error(CasebookConfigError("supply exactly one of --text or --file"))
    payload_text = text if text else Path(str(file)).read_text(encoding="utf-8")
    parsed_mode = _validate_mode(mode, out)
    if parsed_mode is None:
        raise typer.Exit(code=1)
    allowed = ("year", "month", "day", "hour", "minute", "second", "unknown")
    if precision not in allowed:
        raise _casebook_error(
            CasebookConfigError(
                "--precision must be one of {}, not {!r}".format(", ".join(allowed), precision)
            )
        )
    try:
        occurred_time = OccurredTime(
            occurred_at=occurred,
            occurred_precision=cast(OccurredPrecision, precision if occurred else "unknown"),
            occurred_source="user" if occurred else "unknown",
        )
    except ValueError as error:
        raise _casebook_error(CasebookConfigError(str(error))) from error
    key = action_id or uuid4().hex
    analyzer = get_analyzer()
    store = _open_store()
    with store:
        casebook_id = _resolve_casebook(store, casebook)
        result = analyzer.analyze_text(payload_text, mode=parsed_mode)
        snapshot = build_case_file_snapshot(result, occurred=occurred_time, book=analyzer.book)
        try:
            outcome = store.archive(casebook_id, snapshot, idempotency_key=key)
        except IdempotencyConflictError as error:
            raise _casebook_error(error) from error
    out.print()
    out.print(
        f"{'filed' if outcome.created else 'already filed'}: case file {outcome.case_file_id} "
        f"({outcome.entry_count} entr(ies)) · {result.recognition} / {result.verdict.code}"
    )
    out.print()


@casebook_app.command("reread")
def casebook_reread(
    casebook: Annotated[str, typer.Option("--casebook", help="Casebook id or label.")],
    case_file: Annotated[
        str, typer.Option("--case-file", help="The archived case file to re-read.")
    ],
    as_json: Annotated[bool, typer.Option("--json", help="Emit the raw JSON result.")] = False,
) -> None:
    """Re-read one archived case with the current rules. Read-only: nothing is stored."""

    out = console()
    analyzer = get_analyzer()
    store = _open_store()
    with store:
        casebook_id = _resolve_casebook(store, casebook)
        try:
            record = store.find_case_file(casebook_id, case_file)
            label = store.get_casebook(casebook_id).label
            entries = tuple(
                RecordedEntry(
                    entry_id=entry.entry_id,
                    entry_kind=entry.entry_kind,
                    material_index=entry.material_index,
                    material_kind=entry.material_kind,
                    reported_content=entry.reported_content,
                    start_offset=int(entry.start_offset if entry.start_offset is not None else -1),
                    end_offset=int(entry.end_offset if entry.end_offset is not None else -1),
                    polarity=entry.polarity,
                    epistemic_status=entry.epistemic_status,
                    proposition_owner=entry.proposition_owner,
                    reporter_role=entry.reporter_role,
                    target=entry.target,
                    origin_rule_id=entry.origin_rule_id,
                )
                for entry in store.list_entries(case_file_id=case_file)
            )
        except CasebookNotFoundError as error:
            raise _casebook_error(error) from error
        recorded = RecordedCaseFile(
            case_file_id=record.case_file_id,
            input_text=record.input_text,
            generated_at=record.generated_at,
            engine_name=record.engine_name,
            engine_version=record.engine_version,
            rules_version=record.rules_version,
            rules_fingerprint=record.rules_fingerprint,
            recognition=record.recognition,
            verdict_code=record.verdict_code,
            verdict_text=record.verdict_text,
            signal_type=record.signal_type,
        )
    result = reread_case_file(
        casebook_id=casebook_id,
        casebook_label=label,
        case_file=recorded,
        entries=entries,
        engine=analyzer,
        rules_version=str(getattr(analyzer.book, "version", "") or ""),
        rules_fingerprint=rules_fingerprint(getattr(analyzer.book, "source_dir", None)),
    )
    if emit(result, as_json):
        return
    render_reread(result, out)


@casebook_app.command("delete")
def casebook_delete(
    casebook: Annotated[str, typer.Option("--casebook", help="Casebook id or label.")],
    yes: Annotated[bool, typer.Option("--yes", help="Skip the confirmation prompt.")] = False,
) -> None:
    """Delete a casebook and everything filed under it. This is a real delete."""

    out = console()
    store = _open_store()
    with store:
        casebook_id = _resolve_casebook(store, casebook)
        record = store.get_casebook(casebook_id)
        case_files = len(store.list_case_files(casebook_id))
        entries = len(store.list_entries(casebook_id=casebook_id))
        if not yes:
            confirmed = typer.confirm(
                f"delete casebook {record.label!r} ({casebook_id}) and with it "
                f"{case_files} case file(s) / {entries} entr(ies)?"
            )
            if not confirmed:
                out.print("nothing was deleted")
                raise typer.Exit(code=0)
        outcome = store.delete_casebook(casebook_id)
    out.print()
    out.print(f"deleted {outcome.identifier}: {outcome.detail}")
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
