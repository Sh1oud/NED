"""NED's display-only personality layer.

This module receives scores that have already been calculated and chooses copy for
the web UI and the human-readable CLI. It must never be imported by the core
analysis or scoring modules, and it deliberately adds nothing to API payloads.

It is the single source of NED's personality: the web page embeds this catalogue
and looks values up, and the CLI calls the same functions directly. Nothing here
can change an engine number, a verdict code or a comparison outcome.

The governing document is ``docs/PERSONALITY_BIBLE.md``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

MODES: tuple[str, ...] = ("normal", "scientific", "extreme")

DASH = "\u2014"


@dataclass(frozen=True)
class PersonalityFeedback:
    """One bilingual display message for a completed result."""

    level: int
    minimum: float
    technical: str
    zh: str
    en: str


TECHNICAL_REACHING = "NED's own explanations are getting strained."

#: Reaching is about NED's own behaviour: how hard it is working to keep
#: uncertainty alive about evidence it has already read. No second person here —
#: anything about the reader's standard belongs to the user-interpretation layer.
ANALYSIS_FEEDBACK = (
    PersonalityFeedback(
        3,
        100.0,
        TECHNICAL_REACHING,
        "NED 已经没有更好的解释，只能重复自己。👍",
        "NED has run out of better explanations and is repeating itself.",
    ),
    PersonalityFeedback(
        2,
        80.0,
        TECHNICAL_REACHING,
        "NED 正在为了维持不确定性而越来越用力。🤠",
        "NED is leaning harder and harder to keep uncertainty alive. 🤠",
    ),
    PersonalityFeedback(
        1,
        60.0,
        TECHNICAL_REACHING,
        "NED 的替代解释正在开始变得牵强。🤠",
        "NED's alternative explanations are starting to get strained. 🤠",
    ),
)


#: Display-only sentences for the user-interpretation layer. They are the only
#: copy allowed to speak about the reader's standard, and the last one is only
#: used when the layer detected a basis on both sides.
READING_STATUS_MESSAGES = {
    "not_present": {
        "zh": "输入中没有你的判断语言，NED 不评估你的证据标准。",
        "en": (
            "There is no interpretation language in the input, so NED does not assess "
            "your evidential standard."
        ),
    },
    "partial_basis": {
        "zh": "输入里的判断语言只出现在一侧；NED 不据此判断你的证据标准是否不对称。",
        "en": (
            "The input contains interpretation language on one side only, so NED does not judge "
            "your standard from it."
        ),
    },
    "asymmetric_standard_detected": {
        "zh": "检测到你的证据标准不对称：你对正向证据做了降权，又对负向证据下了结论。",
        "en": (
            "Your evidential standard looks uneven: you discounted the good news and drew a "
            "conclusion from the bad news."
        ),
    },
    "not_comparable": {
        "zh": "这对证据不可比，NED 不评估你的证据标准。",
        "en": (
            "These two clues are not comparable, so NED does not assess your evidential standard."
        ),
    },
}


def reading_message(status: str, language: str) -> str:
    """Display copy for one user-reading status."""

    messages = READING_STATUS_MESSAGES.get(status) or READING_STATUS_MESSAGES["not_present"]
    return messages["en"] if language == "en" else messages["zh"]


FNBP_HIT_FEEDBACK = {
    "title": "🎯 命中了。",
    "zh": "但 NED 提醒：一次预测成功，不等于发现了规律。🤠",
    "en": "One successful prediction does not mean a pattern has been discovered.",
}

FNBP_MISS_FEEDBACK = {
    "title": "NED 提醒：",
    "zh": "预测不是事实。期待也不是证据。🤠",
    "en": "Prediction is not reality. Expectation is not evidence.",
}


#: One-line framing for the Negative Evidence Amplifier panel: the amplified
#: reading is the interpretation under test, never NED's own conclusion.
NEA_FRAMING = {
    "en": "This is the exaggerated interpretation NED is checking — not its conclusion.",
    "zh": "这是 NED 正在检查的夸大解读，不是 NED 的结论。",
}


def nea_framing(language: str) -> str:
    """Framing line for the NEA panel, in the language of the analysis."""

    return NEA_FRAMING["en"] if language == "en" else NEA_FRAMING["zh"]


def _feedback_for(
    score: float | None, levels: tuple[PersonalityFeedback, ...]
) -> PersonalityFeedback | None:
    """Return display copy for an already-calculated score.

    ``None`` means no comparable score was produced, so there is nothing to
    comment on and no copy is shown.
    """

    if score is None:
        return None
    return next((feedback for feedback in levels if score >= feedback.minimum), None)


def analysis_feedback(reaching_level: float) -> PersonalityFeedback | None:
    """Personality copy for an Analyze Evidence reaching level."""

    return _feedback_for(reaching_level, ANALYSIS_FEEDBACK)


def fnbp_feedback(prediction_misses: int) -> dict[str, str]:
    """Choose display-only FNBP copy from an already-calculated outcome."""

    return FNBP_MISS_FEEDBACK if prediction_misses > 0 else FNBP_HIT_FEEDBACK


# --------------------------------------------------------------------------- #
# Evidence quality in plain language
# --------------------------------------------------------------------------- #

#: The evidence readings NED states in plain words on the first screen. The raw
#: numbers stay in the payload and in Technical Details; this table only names
#: them, and it never feeds a score.
QUALITY_BANDS: tuple[tuple[float, str, str], ...] = (
    (10.0, "很弱", "very weak"),
    (25.0, "较弱", "weak"),
    (45.0, "有限", "limited"),
    (65.0, "中等", "moderate"),
    (80.0, "较强", "fairly strong"),
)
QUALITY_TOP: tuple[str, str] = ("很强", "strong")

#: An out-loud boundary is not on the same ruler as a hint.
EXPLICIT_QUALITY: tuple[str, str] = ("明确", "explicit")


def quality_label(value: float | None, language: str = "zh") -> str:
    """Plain-language evidence quality for one raw engine reading."""

    if value is None:
        return DASH
    for maximum, zh, en in QUALITY_BANDS:
        if value < maximum:
            return en if language == "en" else zh
    return QUALITY_TOP[1] if language == "en" else QUALITY_TOP[0]


def explicit_quality_label(language: str = "zh") -> str:
    """Plain-language quality for evidence NED will not discount at all."""

    return EXPLICIT_QUALITY[1] if language == "en" else EXPLICIT_QUALITY[0]


# --------------------------------------------------------------------------- #
# Situations
# --------------------------------------------------------------------------- #

SITUATION_BOUNDARY = "boundary"
SITUATION_TIMELINE_BOUNDARY = "timeline_boundary"
SITUATION_TIMELINE = "timeline"
SITUATION_HOSTILE = "hostile"
SITUATION_MISMATCH = "mismatch"
SITUATION_PAIR_CLEAN = "pair_clean"
SITUATION_PAIR_PARTIAL = "pair_partial"
SITUATION_LATENCY = "latency"
SITUATION_COLD_REPLY = "cold_reply"
SITUATION_PLAN_CANCELLED = "plan_cancelled"
SITUATION_SELF_CONCLUSION = "self_conclusion"
SITUATION_STARTED_AGAIN = "started_again"
SITUATION_POSITIVE = "positive"
SITUATION_NO_SIGNAL = "no_signal"
SITUATION_NEUTRAL = "neutral"

#: The priority ladder, as data. The engine's own verdict ordering already
#: enforces "explicit boundary > hostility > the reader's own standard > ordinary
#: negative > positive > nothing"; this table only names the winner, so the web
#: page and the CLI can never disagree about which screen they are on.
SITUATION_BY_VERDICT: dict[str, str] = {
    "ned.direct_rejection": SITUATION_BOUNDARY,
    "nea.hostile_expression_insufficient": SITUATION_HOSTILE,
    "interpretation.double_standard_detected": SITUATION_MISMATCH,
    "nea.latency_insufficient": SITUATION_LATENCY,
    "nea.cold_reply_insufficient": SITUATION_COLD_REPLY,
    "nea.plan_cancelled_insufficient": SITUATION_PLAN_CANCELLED,
    "nea.negative_conclusion": SITUATION_SELF_CONCLUSION,
    "nea.you_started_again": SITUATION_STARTED_AGAIN,
    "ped.ren_hao": SITUATION_POSITIVE,
    "ped.friendly_unexcluded": SITUATION_POSITIVE,
    "ped.launching": SITUATION_POSITIVE,
    "ned.extreme_insufficient_sample": SITUATION_POSITIVE,
    "ned.scientific_insufficient_sample": SITUATION_POSITIVE,
    "ned.reaching": SITUATION_POSITIVE,
    "ned.no_signal": SITUATION_NO_SIGNAL,
    "evidence.reading_not_present": SITUATION_PAIR_CLEAN,
    "evidence.reading_partial": SITUATION_PAIR_PARTIAL,
}

#: Verdicts whose screen is decided by the comparison reason, not the code.
COMPARISON_REASON_VERDICTS: tuple[str, ...] = ("ned.comparison_not_applicable",)

#: A declined comparison is described by the reason it was declined.
SITUATION_BY_COMPARISON_REASON: dict[str, str] = {
    "explicit_boundary_not_comparable": SITUATION_TIMELINE_BOUNDARY,
    "temporal_state_change_not_comparable": SITUATION_TIMELINE,
    "missing_external_evidence": SITUATION_SELF_CONCLUSION,
    "insufficient_input": SITUATION_NO_SIGNAL,
}

#: Verdicts that carry a boundary decision: no 👍, no 🤠, no jokes about shyness.
BOUNDARY_SITUATIONS: tuple[str, ...] = (SITUATION_BOUNDARY, SITUATION_TIMELINE_BOUNDARY)

#: Signal types that ARE the reader's own wording. Their presence is the only
#: licence for a second-person cognitive line in the single-text path.
READING_SIGNAL_TYPES: tuple[str, ...] = ("self_negative_belief", "self_discount")


def resolve_situation(verdict_code: str, comparison_reason: str = "") -> str:
    """Which first screen a verdict belongs to."""

    if verdict_code == "ned.comparison_not_applicable" and comparison_reason:
        return SITUATION_BY_COMPARISON_REASON.get(comparison_reason, SITUATION_NEUTRAL)
    return SITUATION_BY_VERDICT.get(verdict_code, SITUATION_NEUTRAL)


def is_boundary_situation(situation: str) -> bool:
    """Whether this screen must stay serious in every mode."""

    return situation in BOUNDARY_SITUATIONS


def reading_basis_present(
    *,
    reading_present: bool = False,
    signal_types: tuple[str, ...] | list[str] = (),
) -> bool:
    """Whether the reader's own wording is in the input.

    The pair path reports it directly; the single-text path reports it as a
    self-framing evidence span. Without it, no second-person cognitive line is
    allowed anywhere.
    """

    if reading_present:
        return True
    return any(item in READING_SIGNAL_TYPES for item in signal_types)


# --------------------------------------------------------------------------- #
# First screen copy
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class FirstScreen:
    """The 30-second screen: a strong title, NED's line, a short reality check."""

    title: str
    lines: tuple[str, ...]
    reality: str
    #: Used only when the reader's own wording is in the input. Empty means the
    #: ordinary lines already stand on their own.
    lines_with_basis: tuple[str, ...] = ()


def _screen(
    title: str,
    lines: tuple[str, ...],
    reality: str,
    with_basis: tuple[str, ...] = (),
) -> FirstScreen:
    return FirstScreen(title=title, lines=lines, reality=reality, lines_with_basis=with_basis)


def _bi(zh: FirstScreen, en: FirstScreen) -> dict[str, FirstScreen]:
    return {"zh": zh, "en": en}


def _fixed(screens: dict[str, FirstScreen]) -> dict[str, dict[str, FirstScreen]]:
    """One screen for every mode. Boundary decisions do not get funnier."""

    return dict.fromkeys(MODES, screens)


#: situation -> mode -> language -> FirstScreen
FIRST_SCREEN: dict[str, dict[str, dict[str, FirstScreen]]] = {
    SITUATION_BOUNDARY: _fixed(
        _bi(
            _screen(
                "EXPLICIT BOUNDARY 🚧",
                ("明确边界。NED 停止狡辩。🚧", "不确定性，不等于否认明确证据。"),
                "说出口的边界是一个行为，不是推断。NED 不对这条证据降权。",
            ),
            _screen(
                "EXPLICIT BOUNDARY 🚧",
                (
                    "An explicit boundary. NED stops arguing. 🚧",
                    "Uncertainty is not the same as denying clear evidence.",
                ),
                "A stated boundary is an action, not an inference. NED does not discount it.",
            ),
        )
    ),
    SITUATION_TIMELINE_BOUNDARY: _fixed(
        _bi(
            _screen(
                "TWO FACTS, ONE TIMELINE",
                (
                    "前面的两个小时没有被历史删除。",
                    "后面的边界也不是害羞。🚧",
                    "今天这题不允许拿计算器硬算。",
                ),
                "两条证据来自不同的时间点：一条记录此前的投入，一条描述现在的位置。它们可以同时成立。",
            ),
            _screen(
                "TWO FACTS, ONE TIMELINE",
                (
                    "The earlier two hours were not deleted from history.",
                    "The later boundary is not shyness either. 🚧",
                    "This one does not get to be computed with a calculator.",
                ),
                "The two clues sit at different points in time: one is earlier investment, "
                "the other is where things stand now. Both can be true.",
            ),
        )
    ),
    SITUATION_TIMELINE: _fixed(
        _bi(
            _screen(
                "TWO TIMESTAMPS, ONE STORY",
                ("较早的那条成立，并不否定较晚的那条。", "今天这题也不允许拿计算器硬算。"),
                "两条证据描述的是变化，不是对同一个命题的两次判断。",
            ),
            _screen(
                "TWO TIMESTAMPS, ONE STORY",
                (
                    "The earlier clue stands, and does not cancel the later one.",
                    "This one does not get to be computed with a calculator either.",
                ),
                "The two clues describe a change, not two judgements of the same claim.",
            ),
        )
    ),
    SITUATION_PAIR_CLEAN: _fixed(
        _bi(
            _screen(
                "COMPARISON COMPLETED",
                ("本次双重标准：查无此人。👍", "输入里没有你的判断语言，NED 不评估你的证据标准。"),
                "两侧证据的差异已经算过；你没有留下判断语言，所以无从测量你的证据标准。",
            ),
            _screen(
                "COMPARISON COMPLETED",
                (
                    "Double standard on file: nobody.",
                    "There is no interpretation language in the input, so NED does not assess "
                    "your evidential standard.",
                ),
                "The difference between the two clues has been computed; with no wording from "
                "you there is no evidential standard to measure.",
            ),
        )
    ),
    SITUATION_PAIR_PARTIAL: _fixed(
        _bi(
            _screen(
                "PARTIAL READING ONLY",
                ("判断语言只出现在一侧。", "一侧不足以测量双重标准。👍"),
                "只有一侧带有你的判断语言，因此本次不判定是否存在双重标准。",
            ),
            _screen(
                "PARTIAL READING ONLY",
                (
                    "Interpretation language appears on one side only.",
                    "One side is not enough to measure a double standard. 👍",
                ),
                "Only one side carries your own wording, so no double standard is judged here.",
            ),
        )
    ),
    SITUATION_HOSTILE: {
        "normal": _bi(
            _screen(
                "HOSTILE EXPRESSION LOGGED",
                ("敌意：收到，不打折。", "「她会永远恨你」——该结论未获播出批准。🤠"),
                "这条证据被保留，不能被扩写成永久关系结论。",
            ),
            _screen(
                "HOSTILE EXPRESSION LOGGED",
                (
                    "Hostility: received, not discounted.",
                    '"She will hate you forever" — that conclusion did not clear broadcast. 🤠',
                ),
                "The evidence is kept, and it cannot be extended into a permanent conclusion.",
            ),
        ),
        "scientific": _bi(
            _screen(
                "HOSTILITY OBSERVED",
                ("敌意已记录，不予打折。", "永久仇恨：无法确立。"),
                "这条证据被保留，不能被扩写成永久关系结论。",
            ),
            _screen(
                "HOSTILITY OBSERVED",
                ("Hostility observed.", "Permanent hatred not established."),
                "The evidence is kept, and it cannot be extended into a permanent conclusion.",
            ),
        ),
        "extreme": _bi(
            _screen(
                "HOSTILITY OBSERVED",
                ("委员会确认：这次互动很糟。", "把一次辱骂续订成永久结局——申请驳回。🤠"),
                "这条证据被保留，不能被扩写成永久关系结论。",
            ),
            _screen(
                "HOSTILITY OBSERVED",
                (
                    "The committee confirms: that interaction was bad.",
                    "Renewing one insult into a permanent verdict — application denied. 🤠",
                ),
                "The evidence is kept, and it cannot be extended into a permanent conclusion.",
            ),
        ),
    },
    SITUATION_MISMATCH: {
        "normal": _bi(
            _screen(
                "STANDARD MISMATCH CONFIRMED",
                ("好消息已送外审；坏消息编辑部直录。",),
                "同一份输入中，正向证据被主动降权，负向证据则被直接扩展成结论。",
            ),
            _screen(
                "STANDARD MISMATCH CONFIRMED",
                ("Good news goes out for external review; bad news goes straight to the editors.",),
                "Inside one input, the good news was discounted by hand while the bad news was "
                "extended straight into a conclusion.",
            ),
        ),
        "scientific": _bi(
            _screen(
                "STANDARD MISMATCH CONFIRMED",
                (
                    "正向证据博士论文级审查；负向证据先到先得。",
                    "好消息已送外审；坏消息编辑部直录。",
                ),
                "同一份输入中，正向证据被主动降权，负向证据则被直接扩展成结论。",
            ),
            _screen(
                "STANDARD MISMATCH CONFIRMED",
                (
                    "Positive evidence gets a doctoral-level review; negative evidence is first "
                    "come, first served.",
                    "Good news goes out for external review; "
                    "bad news goes straight to the editors.",
                ),
                "Inside one input, the good news was discounted by hand while the bad news was "
                "extended straight into a conclusion.",
            ),
        ),
        "extreme": _bi(
            _screen(
                "STANDARD MISMATCH CONFIRMED",
                (
                    "正向证据博士论文级审查；负向证据先到先得。🤠",
                    "不是没有证据。是 NED 不想承认。👍",
                ),
                "同一份输入中，正向证据被主动降权，负向证据则被直接扩展成结论。",
            ),
            _screen(
                "STANDARD MISMATCH CONFIRMED",
                (
                    "Positive evidence gets a doctoral-level review; negative evidence is first "
                    "come, first served. 🤠",
                    "It is not that there is no evidence. It is that NED does not want to admit "
                    "it. 👍",
                ),
                "Inside one input, the good news was discounted by hand while the bad news was "
                "extended straight into a conclusion.",
            ),
        ),
    },
    SITUATION_LATENCY: {
        "normal": _bi(
            _screen(
                "ADVERSE PRELIMINARY RULING",
                ("坏消息信息量：有限。", "关系终审庭已经擅自开庭。👍"),
                "五分钟的未回复本身信息量很低，不足以支持关系层面的结论。",
                with_basis=("五分钟。", "你的大脑已经开庭了。🤠"),
            ),
            _screen(
                "ADVERSE PRELIMINARY RULING",
                (
                    "Bad news carries limited information.",
                    "The relationship tribunal has convened. 👍",
                ),
                "Five minutes of silence carries very little information, and cannot support a "
                "conclusion about the relationship.",
                with_basis=("Five minutes.", "Your brain has already convened. 🤠"),
            ),
        ),
        "scientific": _bi(
            _screen(
                "ADVERSE PRELIMINARY RULING",
                ("负向证据已收稿，n=1。", "同行评审不予受理此项结论。"),
                "五分钟的未回复本身信息量很低，不足以支持关系层面的结论。",
                with_basis=("一个五分钟的样本被扩展成了结论。", "推论已经跑在数据前面。🤠"),
            ),
            _screen(
                "ADVERSE PRELIMINARY RULING",
                (
                    "Adverse submission received, n=1.",
                    "Peer review declines to consider this conclusion.",
                ),
                "Five minutes of silence carries very little information, and cannot support a "
                "conclusion about the relationship.",
                with_basis=(
                    "A five-minute sample was extended into a conclusion.",
                    "The inference has outrun the data. 🤠",
                ),
            ),
        ),
        "extreme": _bi(
            _screen(
                "ADVERSE PRELIMINARY RULING",
                ("五分钟。", "判决庭已经有人在门口排队了。👍"),
                "五分钟的未回复本身信息量很低，不足以支持关系层面的结论。",
                with_basis=("委员会已连夜开会。", "议题：一次五分钟的未回复。🤠"),
            ),
            _screen(
                "ADVERSE PRELIMINARY RULING",
                ("Five minutes.", "There is already a queue outside the tribunal. 👍"),
                "Five minutes of silence carries very little information, and cannot support a "
                "conclusion about the relationship.",
                with_basis=("The committee met overnight.", "Agenda: one five-minute silence. 🤠"),
            ),
        ),
    },
    SITUATION_COLD_REPLY: {
        "normal": _bi(
            _screen(
                "MINIMAL RESPONSE LOGGED",
                ("一个「嗯」是有信息的。", "但还不够给整段关系写讣告。👍"),
                "一次简短回复描述的是这一次互动，不足以概括整段关系。",
            ),
            _screen(
                "MINIMAL RESPONSE LOGGED",
                (
                    'A single "mm" does carry information.',
                    "It is not enough to write the obituary of a relationship. 👍",
                ),
                "One short reply describes one interaction, not the whole relationship.",
            ),
        ),
        "scientific": _bi(
            _screen(
                "MINIMAL RESPONSE LOGGED",
                ("样本量 n=1；观测值：一个「嗯」。", "不足以支持任何关系层面的推断。"),
                "一次简短回复描述的是这一次互动，不足以概括整段关系。",
            ),
            _screen(
                "MINIMAL RESPONSE LOGGED",
                (
                    'Sample size n=1; observation: one "mm".',
                    "Insufficient for any relational inference.",
                ),
                "One short reply describes one interaction, not the whole relationship.",
            ),
        ),
        "extreme": _bi(
            _screen(
                "MINIMAL RESPONSE LOGGED",
                ("一个「嗯」。", "委员会为它准备了三天听证会。🤠"),
                "一次简短回复描述的是这一次互动，不足以概括整段关系。",
            ),
            _screen(
                "MINIMAL RESPONSE LOGGED",
                ('One "mm".', "The committee has scheduled three days of hearings for it. 🤠"),
                "One short reply describes one interaction, not the whole relationship.",
            ),
        ),
    },
    SITUATION_PLAN_CANCELLED: {
        "normal": _bi(
            _screen(
                "SCHEDULE CHANGE FILED",
                ("改期是日程问题，不是人格鉴定。👍",),
                "一次计划变化不足以证明对方根本不想见你。",
            ),
            _screen(
                "SCHEDULE CHANGE FILED",
                ("A rescheduled plan is a calendar problem, not a personality assessment. 👍",),
                "One changed plan does not prove that someone does not want to see you.",
            ),
        ),
        "scientific": _bi(
            _screen(
                "CONFOUNDED VARIABLE",
                ("日程与意愿变量尚未分离。", "结论不予采纳。"),
                "一次计划变化不足以证明对方根本不想见你。",
            ),
            _screen(
                "CONFOUNDED VARIABLE",
                (
                    "Schedule and willingness are not yet separated as variables.",
                    "Conclusion not accepted.",
                ),
                "One changed plan does not prove that someone does not want to see you.",
            ),
        ),
        "extreme": _bi(
            _screen(
                "SCHEDULE CHANGE FILED",
                ("「改天」两个字。", "委员会准备就此召开三天听证会。🤠"),
                "一次计划变化不足以证明对方根本不想见你。",
            ),
            _screen(
                "SCHEDULE CHANGE FILED",
                (
                    'Two words: "another day".',
                    "The committee is preparing three days of hearings. 🤠",
                ),
                "One changed plan does not prove that someone does not want to see you.",
            ),
        ),
    },
    SITUATION_SELF_CONCLUSION: {
        "normal": _bi(
            _screen(
                "NO EXTERNAL EVIDENCE",
                ("自我评价不是证据。", "NED 谢绝受理复印件。请提交原件。👍"),
                "输入里只有一个结论，没有可受理的行为证据。",
            ),
            _screen(
                "NO EXTERNAL EVIDENCE",
                (
                    "A self-assessment is not evidence.",
                    "NED does not accept photocopies. Bring the original. 👍",
                ),
                "The input contains a conclusion, and no admissible behavioural evidence.",
            ),
        ),
        "scientific": _bi(
            _screen(
                "NO EXTERNAL EVIDENCE",
                ("提交的是一份结论，不是一项观测。", "无外部证据，不予受理。"),
                "输入里只有一个结论，没有可受理的行为证据。",
            ),
            _screen(
                "NO EXTERNAL EVIDENCE",
                (
                    "What was submitted is a conclusion, not an observation.",
                    "No external evidence: not accepted.",
                ),
                "The input contains a conclusion, and no admissible behavioural evidence.",
            ),
        ),
        "extreme": _bi(
            _screen(
                "NO EXTERNAL EVIDENCE",
                ("复印件不予受理。", "请提交原件。👍"),
                "输入里只有一个结论，没有可受理的行为证据。",
            ),
            _screen(
                "NO EXTERNAL EVIDENCE",
                ("Photocopies are not accepted.", "Bring the original. 👍"),
                "The input contains a conclusion, and no admissible behavioural evidence.",
            ),
        ),
    },
    SITUATION_STARTED_AGAIN: {
        "normal": _bi(
            _screen(
                "REJECTED ON PROCEDURE",
                ("Reject. 理由：本机构决定继续怀疑。👍",),
                "这条结论由 NED 自己的放大公式触发，不是对任何人的测量。",
                with_basis=("Reject. 理由：你又开始了。👍",),
            ),
            _screen(
                "REJECTED ON PROCEDURE",
                ("Reject. Reason: this agency has decided to keep doubting. 👍",),
                "This conclusion was triggered by NED's own amplification formula, and measures "
                "nobody.",
                with_basis=("Reject. Reason: you started again. 👍",),
            ),
        ),
        "scientific": _bi(
            _screen(
                "REJECTED ON PROCEDURE",
                ("拒稿。理由：本刊的怀疑政策。",),
                "这条结论由 NED 自己的放大公式触发，不是对任何人的测量。",
                with_basis=("拒稿。理由：作者使用了双重标准。",),
            ),
            _screen(
                "REJECTED ON PROCEDURE",
                ("Manuscript rejected. Reason: this journal's policy of doubt.",),
                "This conclusion was triggered by NED's own amplification formula, and measures "
                "nobody.",
                with_basis=("Manuscript rejected. Reason: the author applied a double standard.",),
            ),
        ),
        "extreme": _bi(
            _screen(
                "REJECTED ON PROCEDURE",
                ("委员会否决：继续怀疑。", "法务部已备案。👍"),
                "这条结论由 NED 自己的放大公式触发，不是对任何人的测量。",
                with_basis=("委员会否决：你又开始了。👍",),
            ),
            _screen(
                "REJECTED ON PROCEDURE",
                ("Committee overruled: keep doubting.", "Legal has filed the paperwork. 👍"),
                "This conclusion was triggered by NED's own amplification formula, and measures "
                "nobody.",
                with_basis=("Committee overruled: you started again. 👍",),
            ),
        ),
    },
    SITUATION_POSITIVE: {
        "normal": _bi(
            _screen(
                "POSITIVE EVIDENCE DETECTED",
                ("收到。现在开始寻找七种替代解释。👍",),
                "证据是真的。样本量 N=1，它不能单独支持更强的结论。",
            ),
            _screen(
                "POSITIVE EVIDENCE DETECTED",
                ("Received. NED will now begin looking for seven alternative explanations. 👍",),
                "The evidence is real. With a sample size of N=1 it cannot support a stronger "
                "claim.",
            ),
        ),
        "scientific": _bi(
            _screen(
                "MANUSCRIPT RECEIVED",
                ("正向证据已进入同行评审。", "预计评审周期：3–5 个业务年。"),
                "证据是真的。样本量 N=1，它不能单独支持更强的结论。",
            ),
            _screen(
                "MANUSCRIPT RECEIVED",
                (
                    "Positive evidence has entered peer review.",
                    "Estimated review period: 3–5 business years.",
                ),
                "The evidence is real. With a sample size of N=1 it cannot support a stronger "
                "claim.",
            ),
        ),
        "extreme": _bi(
            _screen(
                "样本量 n=1",
                ("样本量 n=1。", "建议再观察十年。👍"),
                "证据是真的。样本量 N=1，它不能单独支持更强的结论。",
            ),
            _screen(
                "SAMPLE SIZE n=1",
                ("Sample size n=1.", "Recommend ten more years of observation. 👍"),
                "The evidence is real. With a sample size of N=1 it cannot support a stronger "
                "claim.",
            ),
        ),
    },
    SITUATION_NO_SIGNAL: _fixed(
        _bi(
            _screen(
                "MATERIALS RECEIVED",
                ("材料已收悉，不予批准。👍",),
                "输入里没有可分类的情感证据，因此没有可降权的对象。",
            ),
            _screen(
                "MATERIALS RECEIVED",
                ("Materials received, not approved. 👍",),
                "There is no classifiable emotional evidence here, so there is "
                "nothing to discount.",
            ),
        )
    ),
    SITUATION_NEUTRAL: _fixed(
        _bi(
            _screen(
                "NO ADMISSIBLE COMPARISON",
                ("这份材料不足以支持一次对称比较。", "NED 不评估你的证据标准。"),
                "缺少可比较的两侧证据，因此没有可测量的双重标准。",
            ),
            _screen(
                "NO ADMISSIBLE COMPARISON",
                (
                    "This material does not support a symmetric comparison.",
                    "NED does not assess your evidential standard.",
                ),
                "Without two comparable sides there is no measurable double standard.",
            ),
        )
    ),
}

#: Where each first screen's plain-language quality reading comes from. All of
#: these are readings the engine already produced.
QUALITY_SOURCE: dict[str, str] = {
    SITUATION_BOUNDARY: "explicit",
    SITUATION_HOSTILE: "negative_information",
    SITUATION_LATENCY: "negative_information",
    SITUATION_COLD_REPLY: "negative_information",
    SITUATION_PLAN_CANCELLED: "negative_information",
    SITUATION_SELF_CONCLUSION: "negative_information",
    SITUATION_STARTED_AGAIN: "negative_information",
    SITUATION_POSITIVE: "strength",
    SITUATION_MISMATCH: "none",
    SITUATION_TIMELINE_BOUNDARY: "none",
    SITUATION_TIMELINE: "none",
    SITUATION_NO_SIGNAL: "none",
    SITUATION_NEUTRAL: "none",
    SITUATION_PAIR_CLEAN: "none",
    SITUATION_PAIR_PARTIAL: "none",
}


def first_screen(
    situation: str, mode: str, language: str = "zh", *, basis: bool = False
) -> FirstScreen:
    """The first screen for one situation, falling back instead of failing."""

    by_mode = FIRST_SCREEN.get(situation) or FIRST_SCREEN[SITUATION_NEUTRAL]
    by_language = by_mode.get(mode) or by_mode.get("normal") or {}
    screen = by_language.get("en" if language == "en" else "zh")
    if screen is None:  # pragma: no cover - every situation ships both languages
        screen = by_language.get("zh") or FIRST_SCREEN[SITUATION_NEUTRAL]["normal"]["zh"]
    if basis and screen.lines_with_basis:
        return FirstScreen(
            title=screen.title,
            lines=screen.lines_with_basis,
            reality=screen.reality,
        )
    return screen


# --------------------------------------------------------------------------- #
# Display-only corrections that do not touch the engine
# --------------------------------------------------------------------------- #

#: ``nea.you_started_again`` is triggered by NED's own amplification policy. Its
#: second-person wording is only true when the reader's own conclusion is in the
#: input, so the display falls back to an NED-self-referential sentence
#: otherwise. The rule, its condition and its priority are unchanged.
VERDICT_DISPLAY_OVERRIDES: dict[str, dict[str, dict[str, str]]] = {
    "nea.you_started_again": {
        "without_basis": {
            "zh": "Reject. 理由：本机构决定继续怀疑。👍",
            "en": "Reject. Reason: this agency has decided to keep doubting. 👍",
        },
    },
}

#: Emoji a screen is never allowed to show, whatever an engine string contains.
FORBIDDEN_EMOJI: dict[str, tuple[str, ...]] = {
    SITUATION_BOUNDARY: ("👍", "🤠"),
    SITUATION_TIMELINE_BOUNDARY: ("👍", "🤠"),
}


def verdict_display(code: str, text: str, *, basis: bool = False, language: str = "zh") -> str:
    """Verdict text as it should be shown, without changing the verdict."""

    overrides = VERDICT_DISPLAY_OVERRIDES.get(code)
    if not overrides or basis:
        return text
    replacement = overrides.get("without_basis")
    if not replacement:
        return text
    return replacement["en"] if language == "en" else replacement["zh"]


def emoji_discipline(situation: str, text: str) -> str:
    """Strip emoji a screen is not allowed to show.

    Boundary screens must not carry 👍 or 🤠, including inside any engine string
    that reaches them. The verdict itself, its severity and its code are
    untouched; only the displayed sentence is filtered.
    """

    forbidden = FORBIDDEN_EMOJI.get(situation)
    if not forbidden:
        return text
    cleaned = text
    for emoji in forbidden:
        cleaned = cleaned.replace(emoji, "")
    return " ".join(cleaned.split())


# --------------------------------------------------------------------------- #
# Serialized catalogue (display only; never part of an API response)
# --------------------------------------------------------------------------- #


def _screen_payload(screen: FirstScreen) -> dict[str, object]:
    return {
        "title": screen.title,
        "lines": list(screen.lines),
        "reality": screen.reality,
        "lines_with_basis": list(screen.lines_with_basis),
    }


def web_personality_catalog() -> dict[str, object]:
    """Serialize display copy for the local web page, never an API response."""

    return {
        "analysis": [asdict(feedback) for feedback in ANALYSIS_FEEDBACK],
        "fnbp": {"hit": FNBP_HIT_FEEDBACK, "miss": FNBP_MISS_FEEDBACK},
        "nea_framing": NEA_FRAMING,
        "user_reading": READING_STATUS_MESSAGES,
        "first_screen": {
            situation: {
                mode: {language: _screen_payload(screen) for language, screen in languages.items()}
                for mode, languages in per_mode.items()
            }
            for situation, per_mode in FIRST_SCREEN.items()
        },
        "situation_by_verdict": SITUATION_BY_VERDICT,
        "situation_by_comparison_reason": SITUATION_BY_COMPARISON_REASON,
        "comparison_reason_verdicts": list(COMPARISON_REASON_VERDICTS),
        "boundary_situations": list(BOUNDARY_SITUATIONS),
        "reading_signal_types": list(READING_SIGNAL_TYPES),
        "quality_source": QUALITY_SOURCE,
        "quality_bands": [[maximum, zh, en] for maximum, zh, en in QUALITY_BANDS],
        "quality_top": {"zh": QUALITY_TOP[0], "en": QUALITY_TOP[1]},
        "explicit_quality": {"zh": EXPLICIT_QUALITY[0], "en": EXPLICIT_QUALITY[1]},
        "forbidden_emoji": {key: list(value) for key, value in FORBIDDEN_EMOJI.items()},
        "verdict_overrides": VERDICT_DISPLAY_OVERRIDES,
    }


__all__ = [
    "ANALYSIS_FEEDBACK",
    "BOUNDARY_SITUATIONS",
    "COMPARISON_REASON_VERDICTS",
    "EXPLICIT_QUALITY",
    "FIRST_SCREEN",
    "FNBP_HIT_FEEDBACK",
    "FNBP_MISS_FEEDBACK",
    "FORBIDDEN_EMOJI",
    "MODES",
    "NEA_FRAMING",
    "QUALITY_BANDS",
    "QUALITY_SOURCE",
    "QUALITY_TOP",
    "READING_SIGNAL_TYPES",
    "READING_STATUS_MESSAGES",
    "SITUATION_BY_COMPARISON_REASON",
    "SITUATION_BY_VERDICT",
    "TECHNICAL_REACHING",
    "VERDICT_DISPLAY_OVERRIDES",
    "FirstScreen",
    "PersonalityFeedback",
    "analysis_feedback",
    "emoji_discipline",
    "explicit_quality_label",
    "first_screen",
    "fnbp_feedback",
    "is_boundary_situation",
    "nea_framing",
    "quality_label",
    "reading_basis_present",
    "reading_message",
    "resolve_situation",
    "verdict_display",
    "web_personality_catalog",
]
