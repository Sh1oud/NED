"""BATCH 5.1: five existing-family Chinese coverage gaps.

Each family pins its approved positives and its negative controls, so widening the
wording never widens the semantics: an ordinary explanation stays an explanation, a
latency wording stays latency, a private conclusion stays the reader's own conclusion,
and 不该/不应该 only counts when the reader is the one saying it.
"""

from __future__ import annotations

import pathlib

from ned.app.core.analyzer import NedAnalyzer
from ned.app.core.parser import detect
from ned.app.core.rules import RuleBook

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent

A1_POSITIVE = ("她只是善良", "她心善而已", "她对谁都这么好", "她不好意思拒绝", "她对我客气而已")
A1_NEGATIVE = ("她很善良", "她是个善良的人", "她很客气", "客气", "善良")

B5_POSITIVE = (
    "她隔了一天才回我",
    "她隔天才回我消息",
    "她隔两天才回我",
    "她过了一天才回复我",
    "她第二天才回我",
)
B5_NEGATIVE = (
    "她一天回我很多次",
    "她第二天见了我",
    "她隔天去上班",
    "她两天后告诉我答案",
)

C_POSITIVE = ("她就是不喜欢我", "她根本不喜欢我", "她就是不喜欢我吧")
C_NEGATIVE = ("她回复得很敷衍", "她说她不喜欢我")

D_POSITIVE = (
    "我肯定被讨厌了",
    "我大概被讨厌了",
    "我是不是被讨厌了",
    "我可能被讨厌了",
    "我好像被讨厌了",
)

G_POSITIVE = ("我不该想太多", "我不应该想太多", "我也不该想太多", "我是不是不该想太多")
G_NEGATIVE = tuple(
    f"{subject}{word}想太多" for subject in ("她", "他", "对方") for word in ("不该", "不应该")
)
G_REPORTED = (
    "他说我不该想太多",
    "她说我不该想太多",
    "朋友告诉我我不该想太多",
    "他说我不应该想太多",
    "她说我不应该想太多",
)
G_UNTOUCHED = ("我不想和你说话", "我不喜欢她", "我不认为她喜欢我")

BOOK = RuleBook.load()
ANALYZER = NedAnalyzer(book=BOOK)


def _rules(text: str) -> set[str]:
    return {span.rule_id for span in detect(text, BOOK)}


def _verdict(text: str) -> str:
    return ANALYZER.analyze_text(text, mode="normal").verdict.code


def test_a1_an_ordinary_explanation_is_recognised_only_when_offered() -> None:
    for text in A1_POSITIVE:
        assert _rules(text) == {"zh.self_discount"}, text
        assert _verdict(text) == "ned.self_discount_noted", text
    for text in A1_NEGATIVE:
        assert _rules(text) == set(), text


def test_b5_the_approved_latency_wordings_are_the_only_ones() -> None:
    for text in B5_POSITIVE:
        assert "zh.response_latency" in _rules(text), text
        assert _verdict(text) == "nea.latency_insufficient", text
    for text in B5_NEGATIVE:
        assert "zh.response_latency" not in _rules(text), text


def test_c_an_explicit_self_negative_belief_stays_the_readers_conclusion() -> None:
    for text in C_POSITIVE:
        assert "zh.self_negative_belief" in _rules(text), text
        assert _verdict(text) == "nea.negative_conclusion", text
    for text in C_NEGATIVE:
        assert "zh.self_negative_belief" not in _rules(text), text
    assert "zh.cold_reply" in _rules("她回复得很敷衍")


def test_d_a_passive_self_negative_belief_is_a_reader_conclusion() -> None:
    for text in D_POSITIVE:
        assert "zh.self_negative_belief" in _rules(text), text
        assert _verdict(text) == "nea.negative_conclusion", text


def test_g_the_reader_own_negated_discount_is_reader_owned() -> None:
    for text in G_POSITIVE:
        assert _rules(text) == {"zh.self_discount"}, text
        assert _verdict(text) == "ned.self_discount_noted", text


def test_gap2_a_described_subject_keeps_its_own_reading() -> None:
    """我不该想太多 is the reader's; 她不应该想太多 never is (mirror contract)."""

    assert _rules("我不该想太多") == {"zh.self_discount"}
    assert _rules("我不应该想太多") == {"zh.self_discount"}
    for text in G_NEGATIVE:
        assert "zh.self_discount" not in _rules(text), text


def test_g_a_reported_proposition_is_never_a_stance_transfer() -> None:
    for text in G_REPORTED:
        assert "zh.self_discount" not in _rules(text), text


def test_g_unrelated_reader_phrases_keep_their_own_behaviour() -> None:
    for text in G_UNTOUCHED:
        assert "zh.self_discount" not in _rules(text), text


E1_POSITIVE = (
    "我被她拒绝了",
    "我被她明确拒绝了",
    "我被她当面拒绝了",
    "我被对方拒绝了",
)
E1_DIRECTION = (
    "我拒绝了她",
    "她被我拒绝了",
    "我把她拒绝了",
    "我明确拒绝了她",
)
E1_NOT_UPGRADED = (
    "我没有被她拒绝",
    "我是不是被她拒绝了",
    "我可能被她拒绝了",
)


def test_e1_a_reader_patient_rejection_is_reported_as_a_boundary() -> None:
    for text in E1_POSITIVE:
        assert "zh.direct_rejection" in _rules(text), text
        assert _verdict(text) == "ned.direct_rejection", text


def test_e1_the_reader_actor_direction_is_never_inverted() -> None:
    for text in E1_DIRECTION:
        assert "zh.direct_rejection" not in _rules(text), text


def test_e1_negation_question_and_possibility_are_not_upgraded() -> None:
    for text in E1_NOT_UPGRADED:
        assert "zh.direct_rejection" not in _rules(text), text


#: E1-SUBJECT-PATIENT-1: a sentence that starts with 我 is not automatically the patient
#: of a rejection. A relative ("我朋友"), a perception or a report ("我看到/我听说/我
#: 知道/我发现/我记得") never makes the reader the person who was rejected.
E1_NOT_READER_PATIENT = (
    "我朋友被她拒绝了",
    "我室友被她拒绝了",
    "我妹妹被他拒绝了",
    "我看到她被他拒绝了",
    "我看见她被拒绝了",
    "我听说她被拒绝了",
    "我知道她被拒绝了",
    "我发现她被拒绝了",
    "我记得她被拒绝了",
    "我看到对方被她拒绝了",
    "我朋友昨天被她拒绝了",
)


def test_e1_subject_patient_1_never_reads_a_third_party_rejection_as_the_readers() -> None:
    for text in E1_NOT_READER_PATIENT:
        assert "zh.direct_rejection" not in _rules(text), text


#: E1-SUBJECT-PATIENT-0: only the reader's own rejection event is a boundary; a report
#: about somebody else's rejection never becomes the reader's own.
LEGACY_READER_EVENT = (
    "我表白被拒了",
    "我表白被拒绝了",
)
E1_REPORTED_REJECTION = (
    "我看见她被拒绝了",
    "我听说她被拒绝了",
    "我知道她被拒绝了",
    "我发现她被拒绝了",
    "我记得她被拒绝了",
)


def test_e1_subject_patient_0_the_readers_own_event_stays_a_boundary() -> None:
    """我表白被拒了 keeps the pre-E1 span, family and verdict."""

    expected = {"我表白被拒了": (0, 5), "我表白被拒绝了": (0, 6)}
    for text in LEGACY_READER_EVENT:
        spans = [span for span in detect(text, BOOK) if span.rule_id == "zh.direct_rejection"]
        assert spans, text
        assert (spans[0].start, spans[0].end) == expected[text], (text, spans[0])
        assert _verdict(text) == "ned.direct_rejection", text


def test_e1_subject_patient_0_a_reported_rejection_is_never_the_readers_event() -> None:
    for text in E1_REPORTED_REJECTION:
        assert "zh.direct_rejection" not in _rules(text), text


#: B1: the friend-line is a boundary only when she says it. The same words as a bare
#: utterance stay the reader's own text, and a belief, a relay or a conflicting owner
#: never become her explicit boundary.
B1_ATTRIBUTED = (
    "她说还是当朋友比较好",
    "她告诉我还是当朋友比较好",
    "她跟我说还是当朋友比较好",
    "她明确说还是做朋友比较好",
)
B1_BARE = (
    "还是当朋友比较好",
    "还是做朋友比较好",
    "当朋友比较好",
    "做朋友比较好",
)
B1_NOT_HERS = (
    "她觉得还是当朋友比较好",
    "她认为还是做朋友比较好",
    "她妈妈说她还是当朋友比较好",
    "朋友告诉我她还是做朋友比较好",
    "她说他觉得还是当朋友比较好",
)


def test_b1_an_attributed_friend_line_is_a_boundary() -> None:
    for text in B1_ATTRIBUTED:
        assert "zh.direct_rejection" in _rules(text), text
        assert _verdict(text) == "ned.direct_rejection", text


def test_b1_a_bare_friend_line_is_never_attributed_to_her() -> None:
    for text in B1_BARE:
        assert "zh.direct_rejection" not in _rules(text), text


def test_b1_belief_relay_and_owner_conflict_stay_precision_first() -> None:
    for text in B1_NOT_HERS:
        assert "zh.direct_rejection" not in _rules(text), text


#: E2: an explicit speech frame may carry a subjectless rejection proposition, because
#: "no local subject" is not a conflicting one. A named conflicting subject, a reader-actor
#: proposition and a third-party relay all stay out.
E2_SUBJECTLESS = (
    "她跟我说拒绝了我",
    "她跟我说已经拒绝我了",
    "她告诉我拒绝了我",
    "她说已经拒绝我了",
)
E2_ALIGNED = ("她跟我说她拒绝了我", "她告诉我她拒绝了我")
E2_CONFLICT = ("她跟我说他拒绝了我", "她告诉我他拒绝了我")
E2_DIRECTION = ("她跟我说我拒绝了她", "她说我拒绝了她")
E2_RELAY = ("朋友告诉我她拒绝了我",)


def test_e2_a_subjectless_rejection_under_her_speech_is_a_boundary() -> None:
    for text in E2_SUBJECTLESS:
        assert "zh.direct_rejection" in _rules(text), text
        assert _verdict(text) == "ned.direct_rejection", text
    for text in E2_ALIGNED:
        assert "zh.direct_rejection" in _rules(text), text


def test_e2_a_conflicting_subject_never_inherits_the_outer_sender() -> None:
    for text in E2_CONFLICT:
        assert "zh.direct_rejection" not in _rules(text), text


def test_e2_the_reader_actor_direction_stays_a_recognition_miss() -> None:
    for text in E2_DIRECTION:
        assert "zh.direct_rejection" not in _rules(text), text
    for text in E2_RELAY:
        assert "zh.direct_rejection" not in _rules(text), text
