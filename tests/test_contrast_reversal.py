"""Contrast reversal: "used to, but not any more" is not current evidence.

NED may fail to understand a sentence. It may not report the opposite of what
was written. A past-tense positive clause that the same sentence then reverses
("他以前秒回，现在半天才回") is the clearest way to get that wrong: the engine
matched ``秒回`` and announced "对方回复速度很快。" about a complaint.

The fix is one forward-looking, span-local guard per family, in the same shape
Phase 2A used for ``zh.initiation``: the exclusion region starts at the matched
phrase itself and reaches into the clause that reverses it, so it can only kill
the span the reversal is about. The engine drops a match only when an exclusion
region **overlaps** it (``parser.py``), which is what keeps the guard from
vetoing a whole input — three tests below exist purely to pin that property.

This is a correctness round, not a recall round: no pattern, weight,
information_content or salience changed, and the negative half of these
sentences is deliberately left unowned (``no_signal``).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from ned.app.core.analyzer import NedAnalyzer

RULES = Path(__file__).resolve().parent.parent / "ned" / "app" / "rules" / "signals.json"

#: The five families a following clause could reverse, and the patterns they
#: shipped with. Pinned on purpose: this round may add guards, never coverage.
GUARDED: dict[str, list[str]] = {
    "zh.responsiveness": ["秒回", "马上(就)?回", "回复很快", "回得很快", "回消息很快"],
    "zh.daily_goodnight": ["每天(都)?(说)?晚安", "每天都聊", "晚安", "早安"],
    "zh.compliment": [
        "夸我",
        "说我(好看|帅|可爱|温柔|有趣|厉害)",
        "你真(好看|帅|可爱|温柔|有趣)",
        "你人真好",
    ],
    "zh.gift": [
        "给我(点|订|叫)(了)?[^。！？!?，,]{0,4}"
        "(外卖|奶茶|咖啡|饭|吃的|宵夜|水果|花|蛋糕|东西|零食)",
        "送我(礼物|东西|花)",
        "给我带(了)?",
        "给我买",
        "请我吃饭",
        "帮我",
    ],
    "zh.sustained_interaction": [
        "聊了[^。！？!?，,]{0,6}(小时|个小时)",
        "聊到(凌晨|半夜|很晚)",
        "聊了(一|1)?晚上",
        "聊了(很久|好久)",
        "打了?[^。！？!?，,]{0,6}小时(的)?电话",
        "电话打了",
        "聊(了)?(很久|好久|好一会儿)",
        "一聊就是[^。！？!?，,]{0,6}(小时|个?钟头)",
        "聊到([0-9一二三四五六七八九十两]{1,3}(点|点钟)|天亮|清晨|深夜)",
        "(每天|天天|每晚|经常|常常|时不时|总是|老是)[^。！？!?，,]{0,6}"
        "(找我聊|陪我聊|陪我聊天|聊天|来找我|聊到|聊很久)",
        "从[^。！？!?，,]{0,6}聊到[^。！？!?，,]{0,6}",
        "(聊|说|打电话)[^。！？!?，,]{0,3}(一整晚|一晚上|一整夜|一通宵|整晚|整夜)",
    ],
}

#: The reviewed tail of every guard: an open span-local window, a current-state
#: marker that is not about the reader, and a stop/decline word close behind it.
GUARD_TAIL = (
    "[^。！？!?]{0,12}(?<!我)(现在|如今|最近|后来)[^。！？!?]{0,6}(不|没|很少|几乎|才|没有|不再)"
)

#: A. The reported reversals. Each one used to announce positive evidence while
#: the sentence says the behaviour stopped or declined.
REVERSALS = (
    "他以前秒回，现在半天才回",
    "以前他每天都聊，现在很少联系",
    "以前他总夸我，现在不夸了",
    "以前他会送我礼物，现在什么都没有",
    "以前他每天跟我说晚安，现在不说了",
    "以前我们每天聊到很晚，现在几乎不聊",
)

#: B. The same families stated as a present behaviour. Nothing may shrink here.
POSITIVE_CONTROLS: tuple[tuple[str, str], ...] = (
    ("他现在还是秒回我", "responsiveness"),
    ("他最近每天都来找我聊天", "sustained_interaction"),
    ("他今天夸我了", "compliment"),
    ("他今天送我礼物", "care"),
    ("她每天跟我说晚安", "care"),
    ("我们昨天聊到凌晨", "sustained_interaction"),
)

#: C. Past bad, present good. The guard looks forward only, so a past negative
#: clause must never cost the sentence its present positive.
PAST_BAD_NOW_GOOD: tuple[tuple[str, str], ...] = (
    ("他以前从来不主动找我，但现在每天主动找我", "initiation"),
    ("她以前不怎么理我，现在每天陪我聊到很晚", "sustained_interaction"),
)

#: D. Clauses that look like a reversal but are not.
NOT_A_REVERSAL: tuple[tuple[str, str], ...] = (
    ("他以前秒回，现在也还是秒回", "responsiveness"),
    ("他今天秒回我，但我还是不确定他喜不喜欢我", "responsiveness"),
    ("以前他每天都说晚安，现在还在说", "care"),
    ("他以前总夸我，现在也是这样", "compliment"),
)


def families(result: Any) -> set[str]:
    return {span.signal_type.value for span in result.evidence}


def positive_families(result: Any) -> set[str]:
    return {span.signal_type.value for span in result.evidence if str(span.polarity) == "positive"}


@pytest.fixture(scope="module")
def analyzer() -> NedAnalyzer:
    return NedAnalyzer()


@pytest.fixture(scope="module")
def rules() -> dict[str, dict[str, Any]]:
    pack = json.loads(RULES.read_text(encoding="utf-8"))
    return {rule["id"]: rule for rule in pack["signals"]}


def reversal_guards(rule: dict[str, Any]) -> list[str]:
    return [guard for guard in (rule.get("exclude") or []) if "现在|如今|最近|后来" in guard]


def literal_chunks(pattern: str) -> list[str]:
    """The plain words of a pattern, with the regex machinery removed."""

    return [chunk for chunk in re.split(r"[\[\]()|?+*.^$\\]", pattern) if len(chunk) >= 2]


# --------------------------------------------------------------------------- #
# the patch is data, and it is only data
# --------------------------------------------------------------------------- #


def test_the_patch_adds_guards_and_no_coverage(rules: dict[str, dict[str, Any]]) -> None:
    """A correctness round may not smuggle in new patterns."""

    assert len(rules) == 38
    for rule_id, expected in GUARDED.items():
        assert rules[rule_id]["patterns"] == expected, rule_id


def test_every_guarded_rule_carries_exactly_one_reversal_guard(
    rules: dict[str, dict[str, Any]],
) -> None:
    for rule_id in GUARDED:
        guards = reversal_guards(rules[rule_id])
        assert len(guards) == 1, (rule_id, guards)


def test_the_reversal_guard_is_the_reviewed_span_local_shape(
    rules: dict[str, dict[str, Any]],
) -> None:
    for rule_id in GUARDED:
        guard = reversal_guards(rules[rule_id])[0]
        assert guard.startswith("("), rule_id
        assert guard.endswith(GUARD_TAIL), rule_id
        # the guard must speak the rule's own vocabulary, or no exclusion region
        # could ever overlap a real match
        words = {chunk for pattern in GUARDED[rule_id] for chunk in literal_chunks(pattern)}
        assert any(word in guard for word in words), rule_id


# --------------------------------------------------------------------------- #
# A. the six reversals are no longer positive evidence
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text", REVERSALS)
def test_a_reversed_past_behaviour_is_not_positive_evidence(
    analyzer: NedAnalyzer, text: str
) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    assert positive_families(result) == set(), (text, families(result))
    assert not result.verdict.code.startswith("ped."), (text, result.verdict.code)


# --------------------------------------------------------------------------- #
# B. the same families still fire when the behaviour is present
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(("text", "family"), POSITIVE_CONTROLS)
def test_a_present_behaviour_still_fires(analyzer: NedAnalyzer, text: str, family: str) -> None:
    assert family in families(analyzer.analyze_text(text, mode="normal")), text


# --------------------------------------------------------------------------- #
# C. past bad, present good
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(("text", "family"), PAST_BAD_NOW_GOOD)
def test_a_past_negative_clause_keeps_the_present_positive(
    analyzer: NedAnalyzer, text: str, family: str
) -> None:
    assert family in families(analyzer.analyze_text(text, mode="normal")), text


def test_the_canonical_past_bad_present_good_case(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("他以前从来不主动找我，但现在每天主动找我", mode="normal")
    assert "initiation" in families(result)
    assert "主动找我" in result.raw_interpretation or result.signal_label


# --------------------------------------------------------------------------- #
# D. the guard is clause-local, not input-global
# --------------------------------------------------------------------------- #


def test_a_reversal_does_not_swallow_the_next_sentence(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("他以前秒回，现在半天才回。但他今天夸我了。", mode="normal")
    assert "compliment" in families(result)
    assert "responsiveness" not in families(result)


def test_a_reversal_does_not_swallow_a_later_positive_clause(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text(
        "以前他每天都聊，现在很少联系，但我们昨天聊到凌晨两点", mode="normal"
    )
    assert "sustained_interaction" in families(result)
    assert "每天都聊" not in result.raw_interpretation


def test_the_readers_own_clause_is_not_a_reversal(analyzer: NedAnalyzer) -> None:
    """“我现在不想理她” is about the reader; it does not undo her behaviour."""

    assert "sustained_interaction" in families(
        analyzer.analyze_text("她最近老是找我聊天，我现在不想理她", mode="normal")
    )


# --------------------------------------------------------------------------- #
# E. clauses that look like a reversal but are not
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(("text", "family"), NOT_A_REVERSAL)
def test_a_non_reversing_current_clause_keeps_the_positive(
    analyzer: NedAnalyzer, text: str, family: str
) -> None:
    assert family in families(analyzer.analyze_text(text, mode="normal")), text
