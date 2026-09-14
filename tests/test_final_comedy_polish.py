"""Final Comedy Polish v1: three correctness cleanups, and the joke packs.

Part A pins three facts that were wrong:

* "秒回别人" may not become "秒回我" (A1);
* "她说她只是把我当朋友" is her statement, not the reader's own discount (A2);
* one goodnight may not be reported as a routine (A3).

Part B pins the comedy packs: recognised positive evidence gets copy about that
family, the packs are presentation only, and nothing in them may certify what
the other person feels or turn a report into a fact.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from ned.app.cli import captured_reading_of, screen_context, screen_fact
from ned.app.core.analyzer import NedAnalyzer
from ned.app.ui import personality as p
from ned.app.ui.personality import first_screen, primary_positive_rule

RULES = Path(__file__).resolve().parent.parent / "ned" / "app" / "rules" / "signals.json"

#: A1 — someone else's reply speed is not the reader's.
OTHER_PEOPLE_SPEED = (
    "她总是秒回别人，却不回我",
    "他总是秒回其他人",
    "她对别人秒回，对我很慢",
    "他给别人回得很快",
)

#: A1 — genuine positives that must survive the guard.
OWN_SPEED = (
    "她总是秒回我",
    "跟我聊天的时候她总是秒回",
    "他今天回复很快",
    "她马上回我了",
)

#: A2 — the discount language belongs to the other person here.
REPORTED_DISCOUNT = (
    "她说她只是把我当朋友",
    "他说只是把我当朋友",
    "她告诉我也许只是把我当朋友",
)

#: A2 — the reader's own reading must survive.
READER_DISCOUNT = (
    "我觉得她可能只是把我当朋友",
    "可能她只是把我当朋友",
    "我是不是只是被她当朋友了",
    "我是不是想太多了",
)

#: A3 — frequency is a claim, and only the input may make it.
ONE_OFF_GREETING = ("她昨天跟我说晚安", "她昨天跟我说晚安了")
ROUTINE_GREETING = ("她每天跟我说晚安", "她最近天天说晚安", "她每晚都会说晚安")

#: B — the families that have a comedy pack, with one input each.
COMEDY_INPUTS: tuple[tuple[str, str], ...] = (
    ("他约我周末看电影", "meetup_invitation"),
    ("她问我周末有没有空", "meetup_invitation"),
    ("他第一次主动给我发消息", "initiation"),
    ("她主动来找我聊天", "initiation"),
    ("他给我点了一杯奶茶", "gift"),
    ("他记得我爱吃什么", "care"),
    ("她记得我不吃香菜", "care"),
    ("她每天陪我聊天到很晚", "sustained_interaction"),
    ("昨天聊到凌晨三点", "sustained_interaction"),
    ("我们聊了一整晚", "sustained_interaction"),
    ("她说喜欢我", "reported_affection"),
    ("他说爱我", "reported_affection"),
    ("她说想我了", "reported_affection"),
    ("他说了一百遍想我", "reported_affection"),
    ("她夸我可爱", "compliment"),
    ("他说我好看", "compliment"),
)

#: A family with no pack keeps the generic positive screen.
NO_PACK_INPUTS = ("她每天跟我说晚安", "他每天都聊")

#: Copy that would certify reality or invent a quote. Never allowed.
FORBIDDEN_COPY = ("证据是真的", "The evidence is real", "她真的爱你", "事实就是", "他其实喜欢你")


@pytest.fixture(scope="module")
def analyzer() -> NedAnalyzer:
    return NedAnalyzer()


@pytest.fixture(scope="module")
def rules() -> dict[str, dict[str, object]]:
    pack = json.loads(RULES.read_text(encoding="utf-8"))
    return {rule["id"]: rule for rule in pack["signals"]}


def first_screen_for(analyzer: NedAnalyzer, text: str) -> p.FirstScreen:
    result = analyzer.analyze_text(text, mode="normal")
    situation, basis, language = screen_context(result)
    return first_screen(
        situation,
        result.mode,
        language,
        basis=basis,
        reading=captured_reading_of(result),
        rule=primary_positive_rule(result.evidence),
    )


def fact_for(analyzer: NedAnalyzer, text: str) -> str:
    result = analyzer.analyze_text(text, mode="normal")
    situation, _basis, language = screen_context(result)
    return screen_fact(result, situation, language)


def families(result: object) -> set[str]:
    return {span.signal_type.value for span in result.evidence}  # type: ignore[attr-defined]


# --------------------------------------------------------------------------- #
# A1 — "秒回别人" is not "秒回我"
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text", OTHER_PEOPLE_SPEED)
def test_replying_fast_to_someone_else_is_not_evidence_about_the_reader(
    analyzer: NedAnalyzer, text: str
) -> None:
    assert fact_for(analyzer, text) != "对方回复速度很快。", text
    assert "responsiveness" not in families(analyzer.analyze_text(text, mode="normal")), text


def test_the_other_person_reading_is_still_shown_as_latency(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("她总是秒回别人，却不回我", mode="normal")
    assert "response_latency" in families(result)


@pytest.mark.parametrize("text", OWN_SPEED)
def test_replying_fast_to_the_reader_is_still_evidence(analyzer: NedAnalyzer, text: str) -> None:
    assert fact_for(analyzer, text) == "对方回复速度很快。", text


# --------------------------------------------------------------------------- #
# A2 — her statement is not the reader's discount
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text", REPORTED_DISCOUNT)
def test_a_reported_discount_is_not_the_readers_own_discount(
    analyzer: NedAnalyzer, text: str
) -> None:
    assert "self_discount" not in families(analyzer.analyze_text(text, mode="normal")), text


@pytest.mark.parametrize("text", READER_DISCOUNT)
def test_the_readers_own_discount_still_counts(analyzer: NedAnalyzer, text: str) -> None:
    assert "self_discount" in families(analyzer.analyze_text(text, mode="normal")), text


# --------------------------------------------------------------------------- #
# A3 — one greeting is not a routine
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text", ONE_OFF_GREETING)
def test_a_single_greeting_is_not_called_a_routine(analyzer: NedAnalyzer, text: str) -> None:
    fact = fact_for(analyzer, text)
    assert "规律性" not in fact, (text, fact)
    assert fact == p.ONE_OFF_GREETING_FACT["zh"], (text, fact)


@pytest.mark.parametrize("text", ROUTINE_GREETING)
def test_a_stated_frequency_may_be_called_a_routine(analyzer: NedAnalyzer, text: str) -> None:
    assert "规律性" in fact_for(analyzer, text), text


def test_the_one_off_correction_is_display_only(analyzer: NedAnalyzer) -> None:
    """The engine's own sentence is unchanged; only the screen says otherwise."""

    result = analyzer.analyze_text("她昨天跟我说晚安", mode="normal")
    assert "规律性" in result.raw_interpretation


def test_greeting_is_one_off_reads_the_input() -> None:
    assert p.greeting_is_one_off("她昨天跟我说晚安")
    assert not p.greeting_is_one_off("她每晚都会说晚安")
    assert not p.greeting_is_one_off("他每天都聊")


# --------------------------------------------------------------------------- #
# B — the packs themselves
# --------------------------------------------------------------------------- #


def test_every_pack_is_small_and_deterministic() -> None:
    # six priority groups, with gift and care written as two flavours
    assert len(p.COMEDY_PACKS) == 7
    for key, pack in p.COMEDY_PACKS.items():
        assert 1 <= len(pack.lines) <= 2, key
        assert 2 <= len(pack.hypotheses) <= 3, key
        for text, category, plausibility in pack.hypotheses:
            assert text and category, key
            assert 0 < plausibility <= 100, (key, text)


def test_every_linked_rule_exists(rules: dict[str, dict[str, object]]) -> None:
    for rule_id, key in p.COMEDY_PACK_BY_RULE.items():
        assert rule_id in rules, rule_id
        assert key in p.COMEDY_PACKS, key


@pytest.mark.parametrize(("text", "family"), COMEDY_INPUTS)
def test_recognised_positives_get_their_family_copy(
    analyzer: NedAnalyzer, text: str, family: str
) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    rule_id = primary_positive_rule(result.evidence)
    assert p.comedy_pack_key(rule_id) == family, (text, rule_id)
    screen = first_screen_for(analyzer, text)
    assert screen.lines == p.COMEDY_PACKS[family].lines, text
    assert len(p.comedy_hypotheses(rule_id)) >= 2, text


def test_the_sixteen_inputs_do_not_share_one_joke(analyzer: NedAnalyzer) -> None:
    """The point of the round: one line per family, not one line for everything."""

    signatures = {
        (first_screen_for(analyzer, text).title, first_screen_for(analyzer, text).lines)
        for text, _family in COMEDY_INPUTS
    }
    assert len(signatures) >= 5, signatures

    hypothesis_sets = {
        p.comedy_hypotheses(
            primary_positive_rule(analyzer.analyze_text(text, mode="normal").evidence)
        )
        for text, _family in COMEDY_INPUTS
    }
    assert len(hypothesis_sets) >= 5, hypothesis_sets


@pytest.mark.parametrize("text", NO_PACK_INPUTS)
def test_a_family_without_a_pack_keeps_the_generic_screen(analyzer: NedAnalyzer, text: str) -> None:
    assert first_screen_for(analyzer, text).lines == ("收到。现在开始寻找七种替代解释。👍",), text


def test_the_generic_line_is_not_deleted() -> None:
    generic = p.FIRST_SCREEN[p.SITUATION_POSITIVE]["normal"]["zh"]
    assert generic.lines == ("收到。现在开始寻找七种替代解释。👍",)


@pytest.mark.parametrize("mode", ["scientific", "extreme"])
def test_the_other_modes_keep_their_own_jokes(analyzer: NedAnalyzer, mode: str) -> None:
    """Family copy is for the default mode; the other modes already have a bit."""

    result = analyzer.analyze_text("他约我周末看电影", mode=mode)
    situation, basis, language = screen_context(result)
    screen = first_screen(
        situation, mode, language, basis=basis, rule=primary_positive_rule(result.evidence)
    )
    assert screen.lines != p.COMEDY_PACKS["meetup_invitation"].lines


def test_english_keeps_the_generic_screen(analyzer: NedAnalyzer) -> None:
    result = analyzer.analyze_text("he asked me out this weekend", mode="normal")
    situation, basis, language = screen_context(result)
    screen = first_screen(
        situation, "normal", language, basis=basis, rule=primary_positive_rule(result.evidence)
    )
    assert all("是" not in line for line in screen.lines)


def test_the_sample_size_line_survives_the_polish(analyzer: NedAnalyzer) -> None:
    """B8: the best existing joke may not be broken by the new ones."""

    screen = first_screen_for(analyzer, "他说了一百遍想我")
    assert "样本量 N=1" in screen.reality
    result = analyzer.analyze_text("他说了一百遍想我", mode="normal")
    assert all(span.occurrences == 1 for span in result.evidence)
    assert (
        result.signal_strength == analyzer.analyze_text("他说想我了", mode="normal").signal_strength
    )


def test_no_pack_copy_certifies_reality() -> None:
    for key, pack in p.COMEDY_PACKS.items():
        blob = " ".join((pack.title, *pack.lines, *(text for text, _c, _v in pack.hypotheses)))
        for banned in FORBIDDEN_COPY:
            assert banned not in blob, (key, banned)


def test_every_pack_line_is_a_hypothesis_not_a_finding() -> None:
    """The packs may be funny; they may not become findings."""

    for key, pack in p.COMEDY_PACKS.items():
        for text, category, _value in pack.hypotheses:
            assert text.endswith(("。", "👍")), (key, text)
            assert category, (key, text)


def test_the_rendering_is_deterministic(analyzer: NedAnalyzer) -> None:
    first = first_screen_for(analyzer, "他约我周末看电影")
    second = first_screen_for(analyzer, "他约我周末看电影")
    assert first == second


# --------------------------------------------------------------------------- #
# B12 — a boundary never gets a joke
# --------------------------------------------------------------------------- #


BOUNDARY_AND_HOSTILE = (
    "她说我们还是做朋友吧",
    "他说我们还是保持距离吧",
    "他说我很好 但我们不合适",
    "她让我别再联系她了",
    "她说你他妈有病吧",
)


@pytest.mark.parametrize("text", BOUNDARY_AND_HOSTILE)
def test_boundary_and_hostile_screens_get_no_comedy(analyzer: NedAnalyzer, text: str) -> None:
    result = analyzer.analyze_text(text, mode="normal")
    situation, basis, language = screen_context(result)
    screen = first_screen(
        situation,
        result.mode,
        language,
        basis=basis,
        rule=primary_positive_rule(result.evidence),
    )
    pack_lines = {line for pack in p.COMEDY_PACKS.values() for line in pack.lines}
    assert not (set(screen.lines) & pack_lines), (text, screen.lines)
    assert situation in p.BOUNDARY_SITUATIONS or situation == p.SITUATION_HOSTILE, situation
