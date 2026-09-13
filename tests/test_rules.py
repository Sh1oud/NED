"""Rule-pack integrity tests.

These do not test behaviour; they test that the configuration NED ships with is
internally coherent, so a bad rule pack fails in CI rather than in production.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import pytest
from ned.app.config import RULES_DIR_ENV, rules_dir
from ned.app.core.models import SignalType
from ned.app.core.rules import RuleBook, format_template, resolve_localized, resolve_verdict_text

PACK_FILES = (
    "signals.json",
    "modes.json",
    "escaping.json",
    "verdicts.json",
    "reality_checks.json",
    "asymmetry.json",
    "easter_eggs.json",
)

REQUIRED_MODES = {"normal", "scientific", "extreme"}


@pytest.mark.parametrize("name", PACK_FILES)
def test_pack_files_are_valid_json_objects(name: str) -> None:
    path = rules_dir() / name
    assert path.is_file(), f"missing rule pack: {name}"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    assert payload.get("version"), f"{name} must declare a version"


def test_rulebook_loads_and_covers_both_languages(book: RuleBook) -> None:
    assert book.signals, "no signal rules configured"
    chinese = [rule for rule in book.signals if rule.id.startswith("zh.")]
    english = [rule for rule in book.signals if rule.id.startswith("en.")]
    assert len(chinese) >= 8
    assert len(english) >= 5
    assert REQUIRED_MODES.issubset(set(book.mode_ids))


def test_every_rule_has_a_positive_weight_and_information_content(book: RuleBook) -> None:
    for rule in book.signals:
        assert 0 < rule.weight <= 100, rule.id
        assert 0 <= rule.information_content <= 100, rule.id
        assert rule.patterns, rule.id


def test_negative_latency_rule_is_the_designed_asymmetry(book: RuleBook) -> None:
    """The latency rule must carry a huge weight and almost no information."""

    rule = next(item for item in book.signals if item.id == "zh.response_latency")
    assert rule.weight >= 85
    assert rule.information_content <= 10
    assert rule.signal_type == SignalType.RESPONSE_LATENCY
    assert rule.amplified_interpretation, "NEA needs an amplified reading to display"


def test_escape_tiers_are_contiguous_and_escalate(book: RuleBook) -> None:
    tiers = book.escape_tiers
    assert tiers
    assert tiers[0].min_strength == 0
    assert tiers[-1].max_strength == 100
    for lower, upper in itertools.pairwise(tiers):
        assert lower.max_strength <= upper.min_strength + 0.001
        assert upper.plausibility < lower.plausibility, (
            "plausibility must fall as the evidence gets stronger"
        )


def test_verdict_rules_are_ordered_and_unique(book: RuleBook) -> None:
    priorities = [rule.priority for rule in book.verdicts]
    assert priorities == sorted(priorities)
    ids = [rule.id for rule in book.verdicts]
    assert len(ids) == len(set(ids))
    assert ids[-1] == "ned.no_signal", "the catch-all verdict must be last"


def test_verdict_texts_cover_english_and_chinese(book: RuleBook) -> None:
    for rule in book.verdicts:
        assert rule.texts, rule.id
        for language in ("zh", "en"):
            text = resolve_verdict_text(rule.texts, language, "normal", {})
            assert text.strip(), f"{rule.id} has no {language} text"


def test_reality_checks_are_bilingual(book: RuleBook) -> None:
    assert "no_signal" in book.reality_checks
    assert "asymmetry_pair" in book.reality_checks
    for check in book.reality_checks.values():
        assert check.zh.strip()
        assert check.en.strip()


def test_easter_eggs_never_influence_verdicts(book: RuleBook) -> None:
    """Eggs are decorative: they must not be referenced by any verdict rule."""

    egg_ids = {egg.id for egg in book.easter_eggs}
    verdict_ids = {rule.id for rule in book.verdicts}
    assert egg_ids.isdisjoint(verdict_ids)


def test_template_formatting_degrades_gracefully() -> None:
    assert format_template("{duration} 未回复", {"duration": "5 分钟"}) == "5 分钟 未回复"
    # An unknown placeholder must not raise; a malformed one must not either.
    assert format_template("{unknown} ok", {}) == "— ok"
    assert format_template("{broken ok", {}) == "{broken ok"


def test_localized_resolution_falls_back() -> None:
    assert resolve_localized({"zh": "中文", "en": "english"}, "zh") == "中文"
    assert resolve_localized({"en": "english"}, "zh") == "english"
    assert resolve_localized({}, "zh", "fallback") == "fallback"


def test_rules_dir_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    custom = Path("C:/custom-ned-rules")
    monkeypatch.setenv(RULES_DIR_ENV, str(custom))
    assert rules_dir() == custom
    monkeypatch.delenv(RULES_DIR_ENV)
    assert rules_dir().name == "rules"
