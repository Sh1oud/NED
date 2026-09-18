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

import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass

from ned.app.core import aspects as aspect_pages
from ned.app.core.audit import CLAUSE_SEPARATORS

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


#: Side labels for the pair screen's quality row. Without them the two readings
#: sit next to each other and a reader cannot tell which side is which.
PAIR_QUALITY_LABELS: dict[str, dict[str, str]] = {
    "zh": {"positive": "正向：", "negative": "负向："},
    "en": {"positive": "POSITIVE ", "negative": "NEGATIVE "},
}


def pair_quality_label(language: str, side: str) -> str:
    """Side label for one half of a pair's evidence quality."""

    labels = PAIR_QUALITY_LABELS.get(language) or PAIR_QUALITY_LABELS["zh"]
    return labels.get(side, "")


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
SITUATION_SELF_DISCOUNT_POSITIVE = "self_discount_positive"
#: ``ned.self_discount_noted``: a discount with nothing to discount.
SITUATION_SELF_DISCOUNT_ONLY = "self_discount_only"
SITUATION_STARTED_AGAIN = "started_again"
SITUATION_POSITIVE = "positive"
SITUATION_NO_SIGNAL = "no_signal"
#: PR-2: the input was understood well enough to file material, and nothing in it can be
#: adjudicated by this release. It is a different state from "no material recognised", and
#: the distinction comes from the result's own recognition state, never from string matching.
SITUATION_MATERIAL_ONLY = "material_only"
#: The reader submitted their own explanation of material the input reports.
SITUATION_EXPLANATION_AUDIT = "explanation_audit"
#: Stage 2: the input reports several materials, each kept on its own page.
SITUATION_MULTIPLE_ASPECTS = "multiple_aspects"
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
    "ned.self_discount_noted": SITUATION_SELF_DISCOUNT_ONLY,
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


#: The reader's own discount, as the engine already reports it.
SELF_DISCOUNT_SIGNAL_TYPES: tuple[str, ...] = ("self_discount",)

#: Only these screens may be promoted to ``self_discount_positive``. A boundary,
#: a hostile expression, a real double standard or any negative verdict is never
#: promoted: the reader's discount does not outrank reality.
SELF_DISCOUNT_PROMOTES: tuple[str, ...] = (SITUATION_POSITIVE,)

#: Only these screens may be promoted to ``multiple_aspects``. A boundary, a
#: hostile expression or any other verdict keeps its own screen: keeping a second
#: page must never become an appeal against a stated boundary.
MULTIPLE_ASPECTS_PROMOTES: tuple[str, ...] = (SITUATION_STARTED_AGAIN,)


def screen_situation(
    base_situation: str,
    *,
    self_discount: bool = False,
    positive_evidence: bool = False,
    audit: bool = False,
    aspects: bool = False,
    reader_conclusion: bool = False,
) -> str:
    """The screen to show, given what the engine already found.

    When the reader has supplied their own discount of real positive evidence,
    NED should answer that discount instead of running a generic good-news joke.
    When the input itself reports several material pages, the amplification
    screen becomes the filing screen instead — but only there, and only when the
    reader supplied no conclusion of their own. Everything else is untouched, and
    nothing here can change a verdict.
    """

    if audit and base_situation in SELF_DISCOUNT_PROMOTES:
        # the reader supplied their own explanation: audit it instead of
        # answering it with the old self-service-denial screen
        return SITUATION_EXPLANATION_AUDIT

    # The input reports two pages and the reader supplied no conclusion of their
    # own. The amplification screen would answer with a subject the reader never
    # raised; the filing screen keeps both pages instead.
    if (
        aspects
        and base_situation in MULTIPLE_ASPECTS_PROMOTES
        and not audit
        and not reader_conclusion
    ):
        return SITUATION_MULTIPLE_ASPECTS

    if self_discount and positive_evidence:
        if base_situation in SELF_DISCOUNT_PROMOTES:
            return SITUATION_SELF_DISCOUNT_POSITIVE
        if base_situation == SITUATION_SELF_DISCOUNT_ONLY:
            # a discount with positive evidence is not a discount without one
            return SITUATION_SELF_DISCOUNT_POSITIVE
    return base_situation


#: The reader supplied a discount and there is no positive evidence to discount.
#: ``ned.self_discount_noted`` only fires when the discount is the sole signal.
SITUATION_SELF_DISCOUNT_ONLY = "self_discount_only"

#: On these screens the observed fact must describe the evidence that decided the
#: screen, not whichever signal happened to lead the classification. The list only
#: chooses which existing engine reading to show; it changes no verdict and drops
#: no evidence from Technical Details.
FACT_SIGNAL_TYPES: dict[str, tuple[str, ...]] = {
    SITUATION_BOUNDARY: ("direct_rejection",),
    SITUATION_HOSTILE: ("hostile_expression",),
}


def fact_signal_types(situation: str) -> tuple[str, ...]:
    """Evidence types the first screen's fact must describe, when any are present."""

    return FACT_SIGNAL_TYPES.get(situation, ())


#: What the engine renders when it fills a ``{duration}`` slot and cannot read
#: one. A dash there is an unfilled placeholder, not a fact: the display must never
#: show "—未回复", in either language.
DURATION_ARTIFACTS: tuple[str, ...] = (
    "—未回复",
    "— 未回复",
    "—未有回复",
    "— 未有回复",
    "— without a reply",
    "is — without",
)

#: Display-only repairs for engine sentences that break or overclaim on the way
#: to the screen. Keyed on the exact shipped strings, so nothing else is touched.
#: These are not detection, not parsing and not scoring: they change characters on
#: the way out, and the API payload keeps whatever the engine produced.
DISPLAY_REPAIRS: tuple[tuple[str, str], ...] = (
    # latency: an unfilled {duration} slot
    ("只有 —未有回复", "只有一次未回复"),
    ("The only datum is — without a reply", "The only datum is one unanswered message"),
    ("Reject. — without a reply", "Reject. one unanswered message"),
    ("只有 — 未有回复", "只有一次未回复"),
    ("the only datum is — without a reply", "the only datum is one unanswered message"),
    ("只有 —未回复", "只有一次未回复"),
    ("—未回复", "未回复"),
    ("— 未回复", "未回复"),
    ("—未有回复", "未有回复"),
    ("— 未有回复", "未有回复"),
    ("reject. — without a reply", "reject. one unanswered message"),
    ("— without a reply", "without a reply"),
    # latency: the engine reads any interval as "short", which it cannot know
    ("对方在短时间内没有回复。", "对方的回复延迟已被记录。"),
    (
        "The sender has not replied within a short interval.",
        "A reply delay has been recorded.",
    ),
    # no_signal: the engine claims the input has no meaning; NED only knows that it
    # did not recognise it
    ("这不是坏消息，只是没有消息。", "这不是坏消息，只是 NED 当前没有可解释的分类。"),
    (
        "That is not bad news; it is simply no news.",
        "That is not bad news; NED simply had no classification for it.",
    ),
)

#: Situations whose observed fact must come from the neutral evidence reading
#: rather than the engine's narrative sentence, which may claim more than the
#: engine knows (the latency reading always says "a short interval").
FACT_FROM_OBSERVED: tuple[str, ...] = (SITUATION_LATENCY,)

LATENCY_REALITY_ZH = (
    "未回复或回复延迟本身是一条观察；仅凭这一事件不足以推出关系层面的结论。"
    "时长与上下文会影响这条观察怎么读。"
)
LATENCY_REALITY_EN = (
    "A missing reply is one observation. On its own it cannot support a conclusion about the "
    "relationship; how it reads depends on the interval and the context."
)


def has_missing_duration(*texts: str) -> bool:
    """Whether the engine left a duration slot empty in any of these strings."""

    return any(artifact in text for artifact in DURATION_ARTIFACTS for text in texts)


def _literal(value: str) -> Callable[[re.Match[str]], str]:
    """A re.sub replacement that inserts ``value`` verbatim (no escapes)."""

    def _replace(_match: re.Match[str]) -> str:
        return value

    return _replace


def repair_display_text(text: str) -> str:
    """Repair shipped engine copy on the way to the screen, and nothing else.

    Matching is case-insensitive because shipped sentences start with a capital.
    Only engine strings pass through here: user input is never rewritten.
    """

    repaired = text
    for broken, fixed in DISPLAY_REPAIRS:
        if not broken:
            continue
        replacement: str = fixed
        repaired = re.sub(
            re.escape(broken),
            _literal(replacement),
            repaired,
            flags=re.IGNORECASE,
        )
    return repaired


def fact_from_observed(situation: str) -> bool:
    """Whether this screen must use the neutral evidence reading as its fact."""

    return situation in FACT_FROM_OBSERVED


#: The slot a screen uses where the reader's own words are quoted back.
# --------------------------------------------------------------------------- #
# Final Comedy Polish v1: family-aware copy for evidence NED already recognised
# --------------------------------------------------------------------------- #

#: The flavour count is deliberately small: six families, six packs. Families
#: without a pack keep the generic positive screen, which is a good line and is
#: not going anywhere.


@dataclass(frozen=True)
class ComedyPack:
    """One small joke pack for one recognised family. Presentation only.

    ``lines`` replaces the generic positive lines on the 30-second screen and
    ``hypotheses`` replaces the generic alternative explanations. Nothing here
    touches the engine, and nothing here may claim what the other person feels:
    an alternative explanation is still an alternative explanation.
    """

    title: str
    lines: tuple[str, ...]
    hypotheses: tuple[tuple[str, str, float], ...]


COMEDY_PACKS: dict[str, ComedyPack] = {
    "meetup_invitation": ComedyPack(
        title="OFFLINE INVITATION LOGGED",
        lines=(
            "线下邀约材料已进入卷宗。",
            "恋爱结论暂缓批准。毕竟电影院也卖票给普通朋友。👍",
        ),
        hypotheses=(
            ("电影院属于公共场所。", "venue", 73.5),
            ("两张电影票尚不足以建立排他性因果关系。", "causality", 66.0),
            ("普通厅证据等级有限；杜比影院也不能自动升级关系状态。", "certification", 58.5),
            ("本机构咨询过售票系统，它拒绝对双方感情负责。", "jurisdiction", 81.0),
            ("建议扩大样本量至 IMAX。👍", "sampling", 94.5),
        ),
    ),
    "initiation": ComedyPack(
        title="INITIATIVE LOGGED",
        lines=(
            "主动消息已进入档案。",
            "一次主动，尚不足以申请《长期主动许可证》。👍",
        ),
        hypotheses=(
            ("可能只是正好有话说。", "motive", 61.5),
            ("今天主动 ≠ 永久主动；本机构暂不接受一次性奇迹。", "longitudinal", 88.0),
            ("单次主动行为的可重复性未知，科研伦理委员会要求继续观察。", "ethics", 76.5),
            ("建议持续观察至太阳进入红巨星阶段。", "cosmology", 91.0),
        ),
    ),
    "gift": ComedyPack(
        title="MATERIAL TRANSFER LOGGED",
        lines=(
            # PR-2: no invented item. The screen names the category and keeps the joke, so a
            # reader who reported breakfast is never told about a milk tea.
            "卷宗中出现了一份具体付出。",
            "付出已进入证据链，爱情尚未进入。👍",
        ),
        hypotheses=(
            ("奶茶属于液体，暂不具备出庭证明爱情的法律资格。", "standing", 79.0),
            ("可能只是担心你低血糖，从而影响本机构后续审讯。", "metabolism", 62.5),
            ("建议等待第二杯，形成可重复实验。", "sampling", 90.5),
            ("珍珠数量不能直接换算成情感浓度。", "units", 71.5),
            ("本机构查阅了配料表，未发现“喜欢你”成分。👍", "assay", 93.0),
        ),
    ),
    "care": ComedyPack(
        title="MEMORY MODULE ONLINE",
        lines=(
            "记忆模块运行正常。",
            "感情模块是否在线，本机构尚未取得后台权限。👍",
        ),
        hypotheses=(
            ("记住你不吃香菜，至少说明海马体还在上班。", "neurology", 77.0),
            ("信息保存成功，恋爱许可证尚未自动生成。", "data", 86.5),
            ("数据库里有你的偏好；数据库管理员拒绝说明原因。", "access", 68.0),
            (
                "本机构承认：愿意记住细节通常不是完全不在乎。但本机构随后决定继续嘴硬。👍",
                "concession",
                41.0,
            ),
        ),
    ),
    "sustained_interaction": ComedyPack(
        title="LONG SESSION LOGGED",
        lines=(
            "长时间互动记录已入档。",
            # PR-2: no invented hour. Whatever the clock said, the log only proves that
            # nobody slept through it.
            "聊到几点，都只能证明当时双方都没有睡。👍",
        ),
        hypotheses=(
            ("凌晨三点不是爱情单位。", "units", 79.5),
            ("聊天时长可以用小时计算，感情目前尚无国家法定计量单位。", "metrology", 83.0),
            ("持续互动属于材料，因此本机构决定加班审查它。", "protocol", 88.5),
            ("双方共同牺牲睡眠，但民政部门尚未因此自动盖章。", "registry", 74.0),
            ("睡眠债可以量化，关系状态暂时不行。", "accounting", 69.5),
        ),
    ),
    "reported_affection": ComedyPack(
        title="STATEMENT LOGGED",
        lines=(
            "正向陈述已进入卷宗。",
            "语言属于可再生资源，本机构要求更多硬证据。👍",
        ),
        hypotheses=(
            ("输入报告了一句喜欢；审核部门决定假装没听清。", "transmission", 81.5),
            ("“想你”已登记；语言本身暂不具备强制执行力。", "enforcement", 77.0),
            ("人类可以重复一句话很多次；统计学仍然拒绝把复制粘贴算成独立样本。", "sampling", 90.0),
            ("一百遍来自同一个人。NED：样本量 n=1。👍", "sample_size", 96.0),
            ("建议寻找第二个宇宙进行交叉验证。", "cosmology", 88.0),
        ),
    ),
    "compliment": ComedyPack(
        title="APPRAISAL LOGGED",
        lines=(
            "形容词已进入卷宗。",
            "形容词不是结婚证。👍",
        ),
        hypotheses=(
            ("“可爱”属于形容词，目前未被任何国家认定为婚姻登记材料。", "registry", 89.0),
            ("审美意见属于意见；意见后面发生什么，本机构没有执法权。", "jurisdiction", 74.0),
            ("本机构已扣押“可爱”二字，等待进一步调查。", "seizure", 66.5),
            ("赞美可以构成好消息；至于结论，本机构拒绝这么早下班。", "overtime", 82.0),
        ),
    ),
}

#: rule id -> pack key. Rules that are not listed keep the generic screen.
COMEDY_PACK_BY_RULE: dict[str, str] = {
    "zh.meetup_invitation": "meetup_invitation",
    "zh.initiation": "initiation",
    "zh.gift": "gift",
    "zh.care": "care",
    "zh.sustained_interaction": "sustained_interaction",
    "zh.reported_affection": "reported_affection",
    "zh.miss_you": "reported_affection",
    "zh.explicit_affection": "reported_affection",
    "zh.explicit_love": "reported_affection",
    "zh.compliment": "compliment",
    "zh.affection_emoji": "compliment",
}


def comedy_pack_key(rule_id: str) -> str:
    """The pack key for one rule id, or an empty string."""

    return COMEDY_PACK_BY_RULE.get(rule_id, "")


def comedy_pack(rule_id: str) -> ComedyPack | None:
    """The pack for one rule id, if that family has one."""

    key = comedy_pack_key(rule_id)
    return COMEDY_PACKS.get(key) if key else None


def comedy_hypotheses(rule_id: str) -> tuple[tuple[str, str, float], ...]:
    """Family-aware hypotheses, or empty when the family has no pack."""

    pack = comedy_pack(rule_id)
    return pack.hypotheses if pack is not None else ()


def primary_positive_rule(evidence: Iterable[object]) -> str:
    """The rule whose observation the positive screen is actually about."""

    for span in evidence:
        if str(getattr(span, "polarity", "")) == "positive":
            return str(getattr(span, "rule_id", ""))
    return ""


#: One greeting is not a routine. Display only: the family still fires, and the
#: engine's own sentence is unchanged in the payload.
ROUTINE_MARKERS: tuple[str, ...] = (
    "每天",
    "天天",
    "每晚",
    "每夜",
    "都会",
    "总是",
    "老是",
    "经常",
    "常常",
    "一直",
    "时不时",
)
GREETING_RULE = "zh.daily_goodnight"
ROUTINE_CLAIM = "规律性"
ONE_OFF_GREETING_FACT: dict[str, str] = {
    "zh": "对方进行了一次问候互动。",
    "en": "The sender greeted you once.",
}


def greeting_is_one_off(text: str) -> bool:
    """Whether the input states a greeting without stating a frequency."""

    return not any(marker in text for marker in ROUTINE_MARKERS)


def fact_override(rule_id: str, text: str, language: str = "zh") -> str:
    """Display-only fact corrections that depend on the input, not the payload."""

    if rule_id == GREETING_RULE and greeting_is_one_off(text):
        return ONE_OFF_GREETING_FACT["en" if language == "en" else "zh"]
    return ""


READING_SLOT = "{reading}"

#: Where a displayed quote stops. The rule and the list live in the core audit
#: module, which applies them to the audit data itself; this layer re-exports the
#: name so screens and payloads cannot disagree about where a clause ends.


def captured_reading(text: str, start: int, end: int) -> str:
    """The reader's words, verbatim, extended to the end of their clause.

    The engine's span ends at the discount reason ("可能只是习惯"), so using the
    span alone would quote a truncated sentence. Extending to the clause boundary
    completes it without inventing anything: the result is still a substring of
    what the reader typed.
    """

    if start < 0 or end < 0 or start >= end or end > len(text):
        return ""
    stop = len(text)
    for index in range(end, len(text)):
        if text[index] in CLAUSE_SEPARATORS:
            stop = index
            break
    return text[start:stop].strip()


def fill_reading(lines: tuple[str, ...], reading: str) -> tuple[str, ...] | None:
    """Substitute the reading into a screen's quote slot.

    Returns ``None`` when the screen needs a quote and there is no reliable
    reading, so the caller can fall back to copy with no quotation.
    """

    if not any(READING_SLOT in line for line in lines):
        return lines
    if not reading:
        return None
    return tuple(line.replace(READING_SLOT, reading) for line in lines)


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


# --------------------------------------------------------------------------- #
# Alternative Explanation Audit (Stage 1)
# --------------------------------------------------------------------------- #

#: One flavour per reason the reader can submit. Deterministic lookup by
#: substring of the reader's own words; nothing is generated, nothing is random.
AUDIT_FLAVOURS: dict[str, tuple[str, str]] = {
    "礼貌": (
        "「礼貌」已受理，附件：0。",
        "能解释一切的解释，本机构先放进观察名单。👍",
    ),
    "人好": (
        "「人好」已入档。",
        "该理由本机构一天要用四十次，今天按规定回避，转第二科审查附件。👍",
    ),
    "无聊": (
        "「无聊」已入档，附件：0。",
        "补「可能」两个字，不算补材料。👍",
    ),
    "顺手": (
        "「顺手」已入档，附件：0。",
        "那件东西已经进卷；「顺手」是另一份说明。👍",
    ),
    "习惯": (
        "「习惯」已入档，附件：0。",
        "习惯是另一份结论，不是已经交上来的材料。👍",
    ),
    "可怜": (
        "「可怜」已入档，附件：0。",
        "悲观解释不享受免检通道。（该通道由本机构自行开设，现已关闭。）👍",
    ),
    "同情": (
        "「同情」已入档，附件：0。",
        "悲观解释不享受免检通道。（该通道由本机构自行开设，现已关闭。）👍",
    ),
}

AUDIT_DEFAULT_LINES: tuple[str, str] = (
    "你的解释已受理，附件：0。",
    "本机构不判断它对不对，只登记它有没有带材料。👍",
)

AUDIT_DEFAULT_LINES_EN: tuple[str, str] = (
    "Your explanation has been accepted for filing. Attachments: 0.",
    "This agency does not judge whether it is right; it records whether it came with material. 👍",
)

AUDIT_REALITY: dict[str, str] = {
    "zh": "输入报告的是材料，不是本机构核实过的事实。解释有没有带附件，与它对不对，是两件事。",
    "en": "The input reports material; this agency has verified nothing. Whether an "
    "explanation came with attachments is a separate question from whether it is right.",
}

#: The five parts of the expanded breakdown: labels first, then the sentences.
AUDIT_COPY: dict[str, str] = {
    "material_label": "输入报告的材料",
    "reading_label": "你提交的解释",
    "attachment_label": "解释提交的材料",
    "unknown_label": "仍然未知",
    "limit_label": "目前最多能说到这里",
    "attachment_none": "当前输入没有为该解释另外提交材料。",
    "attachment_some": "输入还有其他材料；这些材料与该解释之间的关系，当前 NED 不作判断。",
    "relation_note": "把材料与解释连起来，需要一份本机构没有做的判断：本机构只登记材料是否存在。",
    "unknown": "这条解释涉及的原因与动机，输入没有报告。",
    "limit": "输入报告了：{material}。再往上加，材料就接不住了。",
    "disclaimer": "材料是输入报告的材料，不是本机构核实过的事实。",
}


def audit_lines(reading: str) -> tuple[str, ...]:
    """The first-screen lines for one explanation, by deterministic lookup."""

    for key, lines in AUDIT_FLAVOURS.items():
        if key in reading:
            return lines
    return AUDIT_DEFAULT_LINES


def audit_breakdown_rows(audit: object) -> tuple[tuple[str, str], ...]:
    """The five-part Epistemic Breakdown for one audit. Display only.

    Every row reads the audit itself, the quote included. The reader's words are
    stored complete at the source, so no display layer completes, corrects or
    re-derives them: this card cannot disagree with the payload it came from.
    """

    shown = str(getattr(audit, "reading", ""))
    material = [str(item) for item in (getattr(audit, "material", None) or [])]
    other = [str(item) for item in (getattr(audit, "other_material", None) or [])]
    joined = "；".join(material) or "—"
    return (
        (AUDIT_COPY["material_label"], joined),
        (AUDIT_COPY["reading_label"], shown),
        (
            AUDIT_COPY["attachment_label"],
            AUDIT_COPY["attachment_some" if other else "attachment_none"]
            + AUDIT_COPY["relation_note"],
        ),
        (AUDIT_COPY["unknown_label"], AUDIT_COPY["unknown"]),
        (AUDIT_COPY["limit_label"], AUDIT_COPY["limit"].replace("{material}", joined)),
    )


# --------------------------------------------------------------------------- #
# Multiple Aspects (Stage 2)
# --------------------------------------------------------------------------- #

#: The slot a screen uses to name the pages it filed. Like the reading slot, it
#: is filled from data the engine already produced, never invented.
MATERIALS_SLOT = "{materials}"

#: What the slot says when the screen has no material names to show. It never
#: invents a material: it says how many pages there are, and no more.
MATERIALS_FALLBACK: dict[str, str] = {
    "zh": "两项材料",
    "en": "Two kinds of material",
}

MULTIPLE_ASPECTS_REALITY: dict[str, str] = {
    "zh": "两种材料不是一个单位，也不是同一把尺子上的格子。它们之间的关系、"
    "以及对方的总体态度，输入都没有报告。卷宗可以有两页，现实不必合成一章。",
    "en": "Two kinds of material are not one unit, and not two squares on the same ruler. "
    "The input reports neither the relation between them nor the other person's overall "
    "attitude. A file can have more than one page; reality does not have to be merged "
    "into one chapter.",
}

#: The observed-fact line for screens whose subject is the shape of the input
#: rather than one material inside it.
FACT_FIXED: dict[str, dict[str, str]] = {
    SITUATION_MULTIPLE_ASPECTS: {
        "zh": "输入报告了两个方向的材料，而不是一个结论。",
        "en": "The input reports material on two sides, not a conclusion.",
    },
}


def fact_fixed(situation: str, language: str = "zh") -> str:
    """A fixed observed-fact line, when the situation has one."""

    table = FACT_FIXED.get(situation)
    if not table:
        return ""
    return table.get("en" if language == "en" else "zh", "")


#: How a page is named in the filing card. Position is the input's order, never a
#: strength order: the card is a file, not a ranking.
ASPECT_PAGE_LABELS: dict[str, tuple[str, ...]] = {
    "zh": ("材料一", "材料二", "材料三", "材料四", "材料五"),
    "en": ("Material one", "Material two", "Material three", "Material four", "Material five"),
}

#: The ordinary register: two pages, kept, never added up.
ASPECT_COPY: dict[str, dict[str, str]] = {
    "zh": {
        "extra_label": "材料{n}",
        "material_row": "「{text}」（该材料自身的等级：{grade}）",
        "between_label": "两项之间",
        "between": "未比较。未合并。未排名。",
        "unknown_label": "仍然未知",
        "unknown": "这两项之间的关系；对方的总体态度。输入都没有报告。",
        "not_done_label": "本机构没有做",
        "not_done": "相加、平均、排名、总分、概率。",
        "disclaimer": "材料是输入报告的材料，不是本机构核实过的事实。",
    },
    "en": {
        "extra_label": "Material {n}",
        "material_row": "\u201c{text}\u201d (this material's own grade: {grade})",
        "between_label": "Between the two",
        "between": "Not compared. Not merged. Not ranked.",
        "unknown_label": "Still unknown",
        "unknown": "The relation between them, and the other person's overall attitude. "
        "The input reports neither.",
        "not_done_label": "This agency did not",
        "not_done": "add them up, average them, rank them, score them or put a "
        "probability on them.",
        "disclaimer": "Material is what the input reports; this agency has verified nothing.",
    },
}

#: The serious register, used under a stated boundary. No joke emoji, no也许, no
#: reopening: the other page is kept and the boundary is not re-read.
ASPECT_BOUNDARY_COPY: dict[str, dict[str, str]] = {
    "zh": {
        "extra_label": "材料{n}",
        "other_label": "已入档的另一份材料",
        "other_row": "「{text}」（该材料自身的等级：{grade}）",
        "boundary_label": "边界",
        "boundary_row": "「{text}」——明确表达的行为，等级：{grade}。",
        "relation_label": "它与边界的关系",
        "relation": "这份材料不会削弱边界。",
        "between_label": "两项之间",
        "between": "未比较。未合并。未排名。",
        "unknown_label": "仍然未知",
        "unknown": "两项材料为什么同时出现；对方未表达的其他心理动机。",
        "settled_label": "已经明确",
        "settled": "输入报告了明确边界；本机构不用另一份材料重新解释边界。",
        "not_done_label": "本机构没有做",
        "not_done": "用另一份材料重新解释边界；把边界算成模糊信号；替读者补一个结论。",
        "disclaimer": "材料是输入报告的材料，不是本机构核实过的事实。",
    },
    "en": {
        "extra_label": "Material {n}",
        "other_label": "The other material on file",
        "other_row": "\u201c{text}\u201d (this material's own grade: {grade})",
        "boundary_label": "The boundary",
        "boundary_row": "\u201c{text}\u201d — a plainly stated act; grade: {grade}.",
        "relation_label": "How it relates to the boundary",
        "relation": "This material does not weaken the boundary.",
        "between_label": "Between the two",
        "between": "Not compared. Not merged. Not ranked.",
        "unknown_label": "Still unknown",
        "unknown": "Why both materials appear together; any motive the other person did not state.",
        "settled_label": "Already settled",
        "settled": "The input states an explicit boundary; this agency does not re-read "
        "it through the other material.",
        "not_done_label": "This agency did not",
        "not_done": "re-read the boundary through the other material, treat the boundary "
        "as a fuzzy signal, or hand the reader a conclusion.",
        "disclaimer": "Material is what the input reports; this agency has verified nothing.",
    },
}


def aspect_copy(situation: str, language: str = "zh") -> dict[str, str]:
    """Which register the filing card speaks in, and in which language."""

    table = ASPECT_BOUNDARY_COPY if situation == SITUATION_BOUNDARY else ASPECT_COPY
    return table.get("en" if language == "en" else "zh") or table["zh"]


def page_grade(span: object, language: str = "zh") -> str:
    """The grade a page's own screen would print for it. Same ruler, same source.

    A positive page is graded by its strength, an observation page by its
    information content and a stated boundary by the explicit band — exactly the
    ``QUALITY_SOURCE`` rule each of those screens already uses.
    """

    if span is None:
        return DASH
    polarity = str(getattr(span, "polarity", ""))
    signal_type = str(getattr(getattr(span, "signal_type", None), "value", ""))
    if signal_type in aspect_pages.BOUNDARY_TYPES:
        return explicit_quality_label(language)
    if polarity == "positive":
        return quality_label(float(getattr(span, "base_strength", 0.0)), language)
    return quality_label(float(getattr(span, "information_content", 0.0)), language)


def page_label(copy: dict[str, str], position: int, language: str = "zh") -> str:
    """The name of the page at this position, in the input's own order."""

    labels = ASPECT_PAGE_LABELS.get("en" if language == "en" else "zh", ())
    if position < len(labels):
        return labels[position]
    return copy["extra_label"].replace("{n}", str(position + 1))


def fill_materials(
    lines: tuple[str, ...], materials: tuple[str, ...] = (), language: str = "zh"
) -> tuple[str, ...]:
    """Name the pages this screen filed, verbatim and in input order."""

    if not any(MATERIALS_SLOT in line for line in lines):
        return lines
    shown = "、".join(f"「{item}」" for item in materials if item)
    if not shown:
        shown = MATERIALS_FALLBACK.get("en" if language == "en" else "zh", "")
    return tuple(line.replace(MATERIALS_SLOT, shown) for line in lines)


def _is_boundary_page(span: object) -> bool:
    signal_type = str(getattr(getattr(span, "signal_type", None), "value", ""))
    return signal_type in aspect_pages.BOUNDARY_TYPES


def _row(template: str, text: str, grade: str) -> str:
    return template.replace("{text}", text).replace("{grade}", grade)


def aspect_breakdown_rows(
    aspects: object,
    evidence: Sequence[object],
    *,
    situation: str = "",
    language: str = "zh",
) -> tuple[tuple[str, str], ...]:
    """The page-by-page filing card for one set of aspects. Display only.

    Every row reads what the screens read: the pages point into the evidence, and
    each grade is the one that page's own screen would print. Nothing here
    compares, merges, ranks or scores the pages, and there is no aggregate number
    in the data to print.
    """

    copy = aspect_copy(situation, language)
    pages: list[tuple[object | None, str]] = []
    for item in list(getattr(aspects, "materials", None) or []):
        index = int(getattr(item, "evidence_index", -1))
        span = evidence[index] if 0 <= index < len(evidence) else None
        pages.append((span, str(getattr(item, "text", ""))))

    if situation == SITUATION_BOUNDARY:
        others = [(span, text) for span, text in pages if not _is_boundary_page(span)]
        boundary = [(span, text) for span, text in pages if _is_boundary_page(span)]
        rows: list[tuple[str, str]] = []
        for position, (span, text) in enumerate(others):
            label = (
                copy["other_label"] if len(others) == 1 else page_label(copy, position, language)
            )
            rows.append((label, _row(copy["other_row"], text, page_grade(span, language))))
        for span, text in boundary:
            rows.append(
                (
                    copy["boundary_label"],
                    _row(copy["boundary_row"], text, page_grade(span, language)),
                )
            )
        rows.append((copy["relation_label"], copy["relation"]))
        rows.append((copy["between_label"], copy["between"]))
        rows.append((copy["unknown_label"], copy["unknown"]))
        rows.append((copy["settled_label"], copy["settled"]))
        rows.append((copy["not_done_label"], copy["not_done"]))
        return tuple(rows)

    rows = []
    for position, (span, text) in enumerate(pages):
        label = page_label(copy, position, language)
        rows.append((label, _row(copy["material_row"], text, page_grade(span, language))))
    rows.append((copy["between_label"], copy["between"]))
    rows.append((copy["unknown_label"], copy["unknown"]))
    rows.append((copy["not_done_label"], copy["not_done"]))
    return tuple(rows)


#: Where the filing card is displayed: under its own screen, and — in the serious
#: register — under a stated boundary. Never under hostility.
ASPECT_CARD_SITUATIONS: tuple[str, ...] = (SITUATION_MULTIPLE_ASPECTS, SITUATION_BOUNDARY)


# --------------------------------------------------------------------------- #
# Observed material registry (the material layer's own record)
# --------------------------------------------------------------------------- #

#: The registry card's own copy. This is a different card from the filing card
#: above: the filing card files *evidence pages*, while this one registers the
#: reported statements the material layer actually recorded. The two never share a
#: row and never merge into one "combined material" view. Nor is it the no-signal
#: screen ("NO CLASSIFIABLE SIGNAL" / "来件已收悉，暂无可分类信号。"): that screen
#: reports the absence of a classifiable signal, while this card lists reports that
#: were found and registered. Different facts, so different wording.
MATERIAL_REGISTRY_COPY: dict[str, dict[str, str]] = {
    "zh": {
        "card_title": "材料登记",
        "registration_intro": "本次输入报告了以下说法，已登记：",
        "item_label": "附件 {n}",
        "item_text": "「{text}」",
        "source_label": "来源",
        "source_unknown": "来源未标注",
        "conclusion_isolation": "本机构没有把上述材料折算成关系结论。",
    },
    "en": {
        "card_title": "MATERIAL REGISTRY",
        "registration_intro": "The input reports the following; it is on file:",
        "item_label": "Attachment {n}",
        "item_text": "\u201c{text}\u201d",
        "source_label": "Source",
        "source_unknown": "Source not stated",
        "conclusion_isolation": "This agency has not converted the material above into a "
        "conclusion about the relationship.",
    },
}

#: How a report's provenance is said out loud. Provenance, never truth: a directly
#: stated report is still only what the input reports. ``direct_user_statement``
#: means the reader typed it, and nothing more.
MATERIAL_SOURCE_LABELS: dict[str, dict[str, str]] = {
    "zh": {
        "attributed_report": "转述材料",
        "direct_user_statement": "用户直接陈述",
    },
    "en": {
        "attributed_report": "Recorded as reported speech",
        "direct_user_statement": "Stated directly by the user",
    },
}


def material_registry_copy(language: str = "zh") -> dict[str, str]:
    """The registry card's copy, with the shared restraint sentence attached.

    The epistemic-restraint line is the existing filing-card disclaimer itself,
    not a second sentence saying the same thing: one sentence, one source, so the
    two cards cannot drift apart.
    """

    key = "en" if language == "en" else "zh"
    return {**MATERIAL_REGISTRY_COPY[key], "disclaimer": ASPECT_COPY[key]["disclaimer"]}


def material_registry_rows(
    materials: Sequence[object], language: str = "zh"
) -> tuple[tuple[str, str], ...]:
    """One label/text pair per registered material. Display only.

    Only the default-visible fields reach this card: the reported statement,
    verbatim, and where it came from. No id, no rule id, no offsets and no
    polarity. The rows are the registry in the registry's own order - nothing here
    sorts, merges, ranks, scores or de-duplicates - and it never reads
    ``material_aspects``, which is a different display object with a different
    source.
    """

    key = "en" if language == "en" else "zh"
    copy = MATERIAL_REGISTRY_COPY[key]
    labels = MATERIAL_SOURCE_LABELS[key]
    rows: list[tuple[str, str]] = []
    for position, item in enumerate(materials, start=1):
        content = str(getattr(item, "reported_content", "") or "")
        source = str(getattr(item, "source_kind", "") or "")
        label = copy["item_label"].replace("{n}", f"{position:02d}")
        rows.append((label, copy["item_text"].replace("{text}", content)))
        rows.append((copy["source_label"], labels.get(source, copy["source_unknown"])))
    return tuple(rows)


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
                LATENCY_REALITY_ZH,
                with_basis=("一次未回复。", "你的大脑已经开庭了。🤠"),
            ),
            _screen(
                "ADVERSE PRELIMINARY RULING",
                (
                    "Bad news carries limited information.",
                    "The relationship tribunal has convened. 👍",
                ),
                LATENCY_REALITY_EN,
                with_basis=("One unanswered message.", "Your brain has already convened. 🤠"),
            ),
        ),
        "scientific": _bi(
            _screen(
                "ADVERSE PRELIMINARY RULING",
                ("负向证据已收稿，n=1。", "同行评审不予受理此项结论。"),
                LATENCY_REALITY_ZH,
                with_basis=("一个未回复样本被扩展成了结论。", "推论已经跑在数据前面。🤠"),
            ),
            _screen(
                "ADVERSE PRELIMINARY RULING",
                (
                    "Adverse submission received, n=1.",
                    "Peer review declines to consider this conclusion.",
                ),
                LATENCY_REALITY_EN,
                with_basis=(
                    "A single unanswered message was extended into a conclusion.",
                    "The inference has outrun the data. 🤠",
                ),
            ),
        ),
        "extreme": _bi(
            _screen(
                "ADVERSE PRELIMINARY RULING",
                ("未回复已登记。", "判决庭已经有人在门口排队了。👍"),
                LATENCY_REALITY_ZH,
                with_basis=("委员会已连夜开会。", "议题：一次未回复。🤠"),
            ),
            _screen(
                "ADVERSE PRELIMINARY RULING",
                ("Delay logged.", "There is already a queue outside the tribunal. 👍"),
                LATENCY_REALITY_EN,
                with_basis=("The committee met overnight.", "Agenda: one unanswered message. 🤠"),
            ),
        ),
    },
    SITUATION_COLD_REPLY: {
        "normal": _bi(
            _screen(
                "MINIMAL RESPONSE LOGGED",
                # PR-2: the copy must not put a concrete detail in the reader's mouth. The
                # screen names the category, never an example the input may not contain.
                ("一次简短回复是有信息的。", "但还不够给整段关系写讣告。👍"),
                "一次简短回复描述的是这一次互动，不足以概括整段关系。",
            ),
            _screen(
                "MINIMAL RESPONSE LOGGED",
                (
                    "A single short reply does carry information.",
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
    SITUATION_SELF_DISCOUNT_POSITIVE: {
        "normal": _bi(
            _screen(
                "SELF-DISCOUNT RECEIVED",
                ("材料已收悉。", "驳回理由已由申请人自行填写。👍"),
                "输入里既有较强的正向证据，也有你自己给出的降权解释。NED 可以记录这种解释，"
                "但不能把它当作事实本身。",
            ),
            _screen(
                "SELF-DISCOUNT RECEIVED",
                ("Materials received.", "Rejection rationale supplied by the applicant. 👍"),
                "The input holds both reasonably strong positive evidence and a discount you "
                "wrote yourself. NED records the explanation; it does not treat it as a fact.",
            ),
        ),
        "scientific": _bi(
            _screen(
                "REVIEWER COMMENT RECEIVED",
                ("正向证据已送审。", "审稿意见已提前归档。"),
                "这份降权说明是一个解释，不是一条新的证据。",
                with_basis=("正向证据已送审。", "审稿意见：{reading}。"),
            ),
            _screen(
                "REVIEWER COMMENT RECEIVED",
                (
                    "Positive evidence submitted for review.",
                    "Reviewer comment already on file.",
                ),
                "That discount is an explanation, not additional evidence.",
                with_basis=(
                    "Positive evidence submitted for review.",
                    "Reviewer #1: {reading}.",
                ),
            ),
        ),
        "extreme": _bi(
            _screen(
                "SELF-SERVICE DENIAL",
                (
                    "这条正向证据很强。",
                    "降权理由也已经一并提交。",
                    "NED：很好，你已经会用了。👍",
                ),
                "驳回流程由申请人自行完成，NED 只负责盖章。",
                with_basis=(
                    "这条正向证据很强。",
                    "你：{reading}。",
                    "NED：很好，你已经会用了。👍",
                ),
            ),
            _screen(
                "SELF-SERVICE DENIAL",
                (
                    "This positive evidence is strong.",
                    "The discount was submitted along with it.",
                    "NED: excellent, you already know how to use this. 👍",
                ),
                "The rejection was completed by the applicant. NED only stamps it.",
                with_basis=(
                    "This positive evidence is strong.",
                    "You: {reading}.",
                    "NED: excellent, you already know how to use this. 👍",
                ),
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
                "输入里报告了正向证据。样本量 N=1，它不能单独支持更强的结论。",
            ),
            _screen(
                "POSITIVE EVIDENCE DETECTED",
                ("Received. NED will now begin looking for seven alternative explanations. 👍",),
                "The input reports positive evidence. With a sample size of N=1 it cannot "
                "support a stronger claim.",
            ),
        ),
        "scientific": _bi(
            _screen(
                "MANUSCRIPT RECEIVED",
                ("正向证据已进入同行评审。", "预计评审周期：3–5 个业务年。"),
                "输入里报告了正向证据。样本量 N=1，它不能单独支持更强的结论。",
            ),
            _screen(
                "MANUSCRIPT RECEIVED",
                (
                    "Positive evidence has entered peer review.",
                    "Estimated review period: 3–5 business years.",
                ),
                "The input reports positive evidence. With a sample size of N=1 it cannot "
                "support a stronger claim.",
            ),
        ),
        "extreme": _bi(
            _screen(
                "样本量 n=1",
                ("样本量 n=1。", "建议再观察十年。👍"),
                "输入里报告了正向证据。样本量 N=1，它不能单独支持更强的结论。",
            ),
            _screen(
                "SAMPLE SIZE n=1",
                ("Sample size n=1.", "Recommend ten more years of observation. 👍"),
                "The input reports positive evidence. With a sample size of N=1 it cannot "
                "support a stronger claim.",
            ),
        ),
    },
    SITUATION_MULTIPLE_ASPECTS: {
        "normal": _bi(
            _screen(
                "MULTIPLE ASPECTS DETECTED",
                (MATERIALS_SLOT + "已分别入档。", "两项各自成页。本机构拒绝把它们相加。👍"),
                MULTIPLE_ASPECTS_REALITY["zh"],
            ),
            _screen(
                "MULTIPLE ASPECTS DETECTED",
                (
                    MATERIALS_SLOT + " filed separately.",
                    "Each one stands as its own page. This agency refuses to add them up. 👍",
                ),
                MULTIPLE_ASPECTS_REALITY["en"],
            ),
        ),
        "scientific": _bi(
            _screen(
                "TWO DATASETS, ONE FILE",
                (
                    MATERIALS_SLOT + "：已分别登记。",
                    "两组材料量纲不同：本机构不加权、不合并、不排序。",
                ),
                MULTIPLE_ASPECTS_REALITY["zh"],
            ),
            _screen(
                "TWO DATASETS, ONE FILE",
                (
                    MATERIALS_SLOT + ": filed separately.",
                    "The two datasets are not commensurable: no weighting, no pooling, no ranking.",
                ),
                MULTIPLE_ASPECTS_REALITY["en"],
            ),
        ),
        "extreme": _bi(
            _screen(
                "BOTH PAGES KEPT",
                (MATERIALS_SLOT + "：两页都在卷里。", "销毁任意一页，本机构都不同意。👍"),
                MULTIPLE_ASPECTS_REALITY["zh"],
            ),
            _screen(
                "BOTH PAGES KEPT",
                (
                    MATERIALS_SLOT + ": both pages stay in the file.",
                    "This agency will not destroy either page. 👍",
                ),
                MULTIPLE_ASPECTS_REALITY["en"],
            ),
        ),
    },
    SITUATION_EXPLANATION_AUDIT: _fixed(
        _bi(
            _screen(
                "ALTERNATIVE EXPLANATION AUDIT",
                AUDIT_DEFAULT_LINES,
                AUDIT_REALITY["zh"],
            ),
            _screen(
                "ALTERNATIVE EXPLANATION AUDIT",
                AUDIT_DEFAULT_LINES_EN,
                AUDIT_REALITY["en"],
            ),
        )
    ),
    SITUATION_SELF_DISCOUNT_ONLY: {
        "normal": _bi(
            _screen(
                "SELF-DISCOUNT NOTED",
                ("正向证据尚未提交。", "驳回理由已经提前准备好了。👍"),
                "现在只有你自己给出的降权解释，没有一条可供降权的正向证据。"
                "降权说明是一个解释，不是现实证据。",
            ),
            _screen(
                "SELF-DISCOUNT NOTED",
                (
                    "No positive evidence submitted.",
                    "The rejection rationale is already prepared. 👍",
                ),
                "There is only a discount you supplied, and no positive evidence to discount. "
                "The discount is an interpretation, not evidence.",
            ),
        ),
        "scientific": _bi(
            _screen(
                "REVIEW COMMENT PRE-FILED",
                ("稿件尚未收到。", "折扣申请已经递到窗口了。"),
                "现在只有你自己给出的降权解释，没有一条可供降权的正向证据。"
                "降权说明是一个解释，不是现实证据。",
            ),
            _screen(
                "REVIEW COMMENT PRE-FILED",
                (
                    "Manuscript not received.",
                    "The discount request has already reached the counter.",
                ),
                "There is only a discount you supplied, and no positive evidence to discount. "
                "The discount is an interpretation, not evidence.",
            ),
        ),
        "extreme": _bi(
            _screen(
                "PREEMPTIVE DENIAL",
                ("你甚至还没提交正向证据。", "折扣申请已经递到窗口了。"),
                "现在只有你自己给出的降权解释，没有一条可供降权的正向证据。"
                "降权说明是一个解释，不是现实证据。",
            ),
            _screen(
                "PREEMPTIVE DENIAL",
                (
                    "You have not even submitted positive evidence.",
                    "The discount request has already reached the counter.",
                ),
                "There is only a discount you supplied, and no positive evidence to discount. "
                "The discount is an interpretation, not evidence.",
            ),
        ),
    },
    SITUATION_NO_SIGNAL: _fixed(
        _bi(
            _screen(
                "NO RECOGNIZED MATERIAL",
                ("来件已收悉，这一版没有识别到可登记的材料。", "本机构暂时不知道该送哪个窗口。👍"),
                "本次输入没有命中 NED 当前支持的信号类型，也没有登记到材料。这不代表输入本身"
                "没有意义，只表示当前规则没有给出可解释的分类。",
            ),
            _screen(
                "NO RECOGNIZED MATERIAL",
                (
                    "Submission received. This release recognised no material in it.",
                    "This agency currently has no window to route it to. 👍",
                ),
                "This input did not match any signal type NED currently supports, and no material "
                "was filed either. That does not mean the input itself is meaningless; it means "
                "the current rules produced no interpretable classification.",
            ),
        )
    ),
    SITUATION_MATERIAL_ONLY: _fixed(
        _bi(
            _screen(
                "MATERIAL ON FILE \u2014 NO VERDICT",
                (
                    "{materials} 已登记。",
                    "材料是「输入报告了什么」，不是本机构核实过的事实，也不是裁决。👍",
                ),
                "这件材料单独不足以支撑一个关系结论，所以本机构拒绝签发——不是因为没听见。"
                "登记内容逐字取自你的输入。",
            ),
            _screen(
                "MATERIAL ON FILE \u2014 NO VERDICT",
                (
                    "{materials} is on file.",
                    "A material record is what the input reports, not a verified fact and not a "
                    "verdict. 👍",
                ),
                "On its own this material cannot carry a relationship conclusion, so this agency "
                "declines to issue one - not because nothing was heard. The record quotes your "
                "input verbatim.",
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
    SITUATION_SELF_DISCOUNT_POSITIVE: "strength",
    SITUATION_MISMATCH: "none",
    SITUATION_TIMELINE_BOUNDARY: "none",
    SITUATION_TIMELINE: "none",
    SITUATION_EXPLANATION_AUDIT: "strength",
    #: This screen must not become a scoreboard: it prints no quality number at
    #: all, because each page's grade belongs to that page, not to a total.
    SITUATION_MULTIPLE_ASPECTS: "none",
    SITUATION_NO_SIGNAL: "none",
    SITUATION_SELF_DISCOUNT_ONLY: "none",
    SITUATION_NEUTRAL: "none",
    SITUATION_PAIR_CLEAN: "none",
    SITUATION_PAIR_PARTIAL: "none",
}


def first_screen(
    situation: str,
    mode: str,
    language: str = "zh",
    *,
    basis: bool = False,
    reading: str = "",
    rule: str = "",
    materials: tuple[str, ...] = (),
) -> FirstScreen:
    """The first screen for one situation, falling back instead of failing.

    ``rule`` is the rule the screen is about. When that family has a comedy
    pack, its lines replace the generic positive ones — in the default mode and
    in Chinese only, so the scientific and extreme modes keep their own jokes.
    """

    by_mode = FIRST_SCREEN.get(situation) or FIRST_SCREEN[SITUATION_NEUTRAL]
    by_language = by_mode.get(mode) or by_mode.get("normal") or {}
    screen = by_language.get("en" if language == "en" else "zh")
    if screen is None:  # pragma: no cover - every situation ships both languages
        screen = by_language.get("zh") or FIRST_SCREEN[SITUATION_NEUTRAL]["normal"]["zh"]

    if situation == SITUATION_EXPLANATION_AUDIT:
        # the flavour follows the reader's own words, in every mode
        return FirstScreen(
            title=screen.title,
            lines=audit_lines(reading),
            reality=screen.reality,
        )

    if situation in (SITUATION_MULTIPLE_ASPECTS, SITUATION_MATERIAL_ONLY):
        # Both screens name what was filed, verbatim and in input order: the pages of a
        # two-sided report, or the material records of an input that cannot be adjudicated.
        return FirstScreen(
            title=screen.title,
            lines=fill_materials(screen.lines, materials, language),
            reality=screen.reality,
        )

    if situation == SITUATION_POSITIVE and mode == "normal" and language != "en":
        pack = comedy_pack(rule)
        if pack is not None:
            return FirstScreen(title=pack.title, lines=pack.lines, reality=screen.reality)

    if basis and screen.lines_with_basis:
        lines = fill_reading(screen.lines_with_basis, reading)
        if lines is None:
            # the screen wants to quote the reader and has nothing reliable to
            # quote, so it says the same thing without quotation marks
            return screen
        return FirstScreen(title=screen.title, lines=lines, reality=screen.reality)
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


#: The service hall's own chrome: the bureau's name plate, the intake window's
#: heading and its submit label, the review record's heading, and the issuance
#: heading. These label the hall, not an input: they name no stage, promise no
#: progress, and state no approval, rejection or issuance outcome. The product has
#: no such status anywhere -- neither the payload nor the client derives one -- so
#: none is invented here. The page reads every one of these out of this catalogue at
#: runtime, which is why the template and the script carry no second copy of them.
FRONT_DESK_COPY: dict[str, dict[str, str]] = {
    "intake_heading": {
        "zh": "请提交待审查材料",
        "en": "Submit material for review",
    },
    # PR-6R2: one language per label. These were printed as "中文 · ENGLISH TITLE" in the
    # markup; they are looked up now, so the page shows one language at a time.
    "tab_intake": {"zh": "交材料", "en": "Review intake"},
    "tab_others": {"zh": "其它窗口", "en": "Other windows"},
    "tab_asymmetry": {"zh": "证据对比", "en": "Evidence comparison"},
    "tab_lab": {"zh": "通知分支实验室", "en": "Notification branch lab"},
    "intake_purpose": {
        "zh": "粘贴一句话，或描述发生了什么。",
        "en": "Paste a message, or describe what happened.",
    },
    "field_material": {"zh": "材料原文", "en": "Message or event"},
    "field_mode": {"zh": "审查模式", "en": "Analysis mode"},
    "field_material_placeholder": {
        "zh": "粘贴消息，或描述发生了什么…",
        "en": "Paste a message, or describe what happened…",
    },
    "examples_heading": {"zh": "办事指南", "en": "Example cases"},
    "section_reality": {"zh": "现实核对", "en": "Reality check"},
    "section_nea": {"zh": "负面证据放大器", "en": "Negative evidence amplifier"},
    "section_hypotheses": {"zh": "替代解释", "en": "Alternative hypotheses"},
    "section_audit": {"zh": "解释审计", "en": "Explanation audit"},
    "section_aspects": {"zh": "多面材料", "en": "Multiple aspects"},
    "verdict_heading": {"zh": "最终裁决", "en": "Final verdict"},
    "copy_json": {"zh": "复制 JSON", "en": "Copy JSON"},
    # PR-6R2: the review region's own labels and notes. Two of these were literals in the
    # template and two in the shipped script, which is how an English sentence ended up printed
    # on a Chinese desk. They are catalogue labels now, so both languages are served the same way.
    "screen_quality_label": {"zh": "证据强度", "en": "Evidence quality"},
    "nea_observed_label": {"zh": "观察到的证据", "en": "Observed evidence"},
    "nea_amplified_label": {"zh": "放大后的读法", "en": "Amplified reading"},
    "nea_note": {
        "zh": "这里没有建议，也没有任何关于某人的事实。",
        "en": "Nothing here is advice, and nothing here is a fact about anyone.",
    },
    "hypo_note": {
        "zh": "以下是替代解释，不是结论。它们只用来重新打开另一种可能：可能只是人好。👍",
        "en": "These are alternative hypotheses, not findings. Each one exists to re-open the "
        "possibility that 可能只是人好。👍",
    },
    "hypo_empty": {
        "zh": "本次没有生成替代解释。什么都不做，本身就值得怀疑。",
        "en": "No alternative hypotheses were generated for this input. Leaving the evidence "
        "alone is itself suspicious.",
    },
    "plausibility": {"zh": "可信度 {p}%", "en": "plausibility {p}%"},
    # PR-6M2: the casebook. Storage is opt-in and explicit, so the copy has to say what is kept,
    # where, and what is never kept at all.
    "casebook_tab": {"zh": "卷宗", "en": "Casebook"},
    "casebook_heading": {"zh": "卷宗", "en": "Casebook"},
    "casebook_intro": {
        "zh": "卷宗只保存在本机，而且只保存在你主动归入的内容。",
        "en": "The casebook lives on this machine and holds only what you file yourself.",
    },
    "casebook_disabled": {
        "zh": "本机未启用卷宗功能（NED_CASEBOOK=off）。分析照常可用，任何输入都不会被保存。",
        "en": "This machine has the casebook switched off (NED_CASEBOOK=off). Analysis still "
        "works and nothing you type is stored.",
    },
    "casebook_create_label": {"zh": "新建卷宗", "en": "New casebook"},
    "casebook_label_field": {"zh": "卷宗名", "en": "Casebook name"},
    "casebook_label_placeholder": {"zh": "例如：小 A", "en": "for example: A."},
    "casebook_create": {"zh": "新建", "en": "Create"},
    "casebook_created": {"zh": "已新建卷宗 {label}。", "en": "Created casebook {label}."},
    "casebook_empty": {"zh": "还没有卷宗。", "en": "No casebooks yet."},
    "casebook_expand": {"zh": "查看", "en": "Open"},
    "casebook_collapse": {"zh": "收起", "en": "Close"},
    "casebook_counts": {
        "zh": "{files} 个案卷 · {entries} 条材料",
        "en": "{files} case file(s) · {entries} entry(ies)",
    },
    "casebook_file_action": {"zh": "归入卷宗", "en": "File into casebook"},
    "casebook_file_choose": {"zh": "归入哪个卷宗", "en": "Which casebook"},
    "casebook_file_new": {"zh": "或新建一个卷宗名…", "en": "or name a new casebook…"},
    "casebook_file_occurred": {"zh": "发生时间（可选）", "en": "When it happened (optional)"},
    "casebook_file_confirm": {"zh": "确认归入", "en": "File it"},
    "casebook_file_cancel": {"zh": "取消", "en": "Cancel"},
    "casebook_file_pick": {
        "zh": "请选择一个卷宗，或填一个卷宗名。",
        "en": "Choose a casebook, or type a name for a new one.",
    },
    "casebook_filing": {"zh": "正在归入…", "en": "Filing…"},
    "casebook_filed": {"zh": "已归入「{label}」。", "en": "Filed into {label}."},
    "casebook_filed_again": {
        "zh": "这次动作已经归入过了，没有重复保存。",
        "en": "This action was already filed; nothing was stored twice.",
    },
    "casebook_file_failed": {"zh": "归入失败。", "en": "Filing failed."},
    "casebook_times": {
        "zh": "发生时间 {occurred} · 保存时间 {saved}",
        "en": "happened {occurred} · saved {saved}",
    },
    "casebook_occurred_unknown": {"zh": "未知", "en": "unknown"},
    "casebook_occurred_relative": {
        "zh": "原文含相对时间，未解析",
        "en": "the input mentions a relative time; it was not resolved",
    },
    "casebook_state": {"zh": "当时状态", "en": "state then"},
    "casebook_material": {"zh": "材料附件", "en": "material on file"},
    "casebook_no_material": {
        "zh": "本案没有登记材料。",
        "en": "Nothing was registered for this input.",
    },
    "casebook_entry_line": {
        "zh": "{kind} · 偏移 {start}-{end} · {source}",
        "en": "{kind} · offsets {start}-{end} · {source}",
    },
    "casebook_delete_entry": {"zh": "删除这条材料", "en": "Delete this entry"},
    "casebook_delete_case": {"zh": "删除这个案卷", "en": "Delete this case file"},
    "casebook_delete_casebook": {"zh": "删除整个卷宗", "en": "Delete this casebook"},
    "casebook_delete_ask": {
        "zh": "确认永久删除？此操作立即生效，不可撤销。",
        "en": "Delete for good? This takes effect immediately and cannot be undone.",
    },
    "casebook_delete_yes": {"zh": "确认删除", "en": "Delete"},
    "casebook_delete_cancel": {"zh": "取消", "en": "Cancel"},
    "casebook_deleted": {"zh": "已删除。", "en": "Deleted."},
    "casebook_delete_failed": {"zh": "删除失败。", "en": "Delete failed."},
    "casebook_archive_failed": {"zh": "卷宗请求失败。", "en": "The casebook request failed."},
    # PR-6M2: the footer has to describe what actually happens. The old sentence said input stays
    # "in this browser session", which was never quite true (the interface keeps its mode in
    # browser storage) and would now be wrong in a second way.
    "privacy_footer": {
        "zh": "本机运行：输入只在浏览器内存与本机服务器之间传递，分析不写入任何数据库。"
        "只有你主动「归入卷宗」的内容才会写入本机卷宗文件；分析模式偏好保存在浏览器本地存储，"
        "界面语言切换只在当前页面生效。无遥测、无分析、无 Cookie、无第三方请求。",
        "en": "Runs on this machine: your input passes between the browser's memory and the "
        "local server, and analysing writes to no database. Only what you explicitly file into "
        "the casebook is written to the local casebook file; your preferred analysis mode is "
        "kept in browser storage, and the language switch lasts for this page only. No "
        "telemetry, no analytics, no cookies, no third-party requests.",
    },
    # PR-6R2: the two status lines of the counter action. They are the only sentences left on the
    # main path that a reader could meet in English while the desk is speaking Chinese.
    "status_no_input": {
        "zh": "先输入一句话，或描述发生了什么。",
        "en": "Enter a message or describe what happened first.",
    },
    "status_analyze_failed": {"zh": "审查失败。", "en": "Analysis failed."},
    # PR-6R2: the hypotheses annotation is the one place the playful example survived into a
    # stated boundary. Under the serious register the same annotation is printed without it,
    # keyed on the client-derived situation that register already runs on.
    "hypo_note_boundary": {
        "zh": "以下是替代解释，不是结论。对方已经把边界说出口，本机构不对这句话开玩笑。",
        "en": "These are alternative hypotheses, not findings. The boundary was stated out "
        "loud, and this agency does not joke about it.",
    },
    # the same annotation for the other register where NED is not joking
    "hypo_note_hostile": {
        "zh": "以下是替代解释，不是结论。输入已经报告了敌意，本机构不把这句话读轻。",
        "en": "These are alternative hypotheses, not findings. The input reported hostility, "
        "and this agency does not read it lightly.",
    },
    "submit_label": {
        "zh": "提交审查",
        "en": "Submit for review",
    },
    "records_heading": {
        "zh": "技术档案",
        "en": "Technical archive",
    },
    "issuance_heading": {
        "zh": "签发状态",
        "en": "Issuance status",
    },
    # PR-3: the four-stage dossier. These name the stages of the counter and the state of
    # the reader's own submission; none of them invents a workflow, a progress figure or an
    # outcome the payload did not produce. Every value is filled at runtime from the
    # payload's own recognition state, evidence list and material list.
    "stage_material_count": {"zh": "已登记 {n} 项", "en": "{n} on file"},
    "stage_material_none": {"zh": "未识别到材料", "en": "no material recognised"},
    "stage_review_done": {"zh": "已出具意见", "en": "opinion issued"},
    "stage_review_unsignable": {"zh": "材料不足，未出具", "en": "material only, no opinion"},
    "stage_review_none": {"zh": "无材料可审", "en": "nothing to review"},
    "stage_issuance_signed": {"zh": "已签发", "en": "signed"},
    "stage_issuance_material": {"zh": "未签发 · 材料不足", "en": "not signed · material only"},
    "stage_issuance_none": {"zh": "未签发 · 未识别到材料", "en": "not signed · no material"},
    "issuance_signed": {"zh": "本局已签发结论", "en": "This agency signed a conclusion"},
    "issuance_boundary": {
        "zh": "本局确认：这是明确边界",
        "en": "This agency confirms: a stated boundary",
    },
    "issuance_boundary_sub": {
        "zh": "对方把边界说出口了。本局不对这条证据降权。",
        "en": "The boundary was stated out loud. This agency does not discount it.",
    },
    "issuance_material": {"zh": "本局未签发结论", "en": "This agency signed nothing"},
    "issuance_material_sub": {
        "zh": "材料已登记，但不足以单独签发结论。",
        "en": "Material is on file, but it cannot carry a conclusion on its own.",
    },
    "issuance_none": {"zh": "本局未签发结论", "en": "This agency signed nothing"},
    "issuance_none_sub": {
        "zh": "本版未识别到可登记材料。",
        "en": "This release recognised no material in the submission.",
    },
    "material_count": {"zh": "已登记材料 {n} 项", "en": "{n} material item(s) on file"},
    "material_count_none": {"zh": "无可登记材料", "en": "no material on file"},
    "review_relation_evidence_and_material": {
        "zh": "材料已登记，其中 {n} 项与本次命中的证据相关；证据本身仍不足以无限外推。",
        "en": "{n} material item(s) are on file; the matched evidence still cannot be "
        "extrapolated.",
    },
    "review_relation_evidence_only": {
        "zh": "本次未登记材料，审查意见直接来自输入命中的证据。",
        "en": "No material was filed; this opinion rests on the evidence the input matched.",
    },
    "review_relation_material_only": {
        "zh": "材料已入卷，但不足以单独签发该结论。",
        "en": "Material is on file, but it cannot sign that conclusion on its own.",
    },
    "review_relation_none": {
        "zh": "本版没有登记到材料，也没有可裁决的证据。",
        "en": "This release filed no material and found no adjudicable evidence.",
    },
    "language_toggle": {"zh": "EN", "en": "中文"},
    # PR-3: the four counters of the dossier. Names only - the state beside each one comes
    # from the payload (recognition, evidence, materials), never from these strings.
    "stage_name_submit": {"zh": "提交材料", "en": "Submitted material"},
    "stage_name_material": {"zh": "材料登记", "en": "Material registration"},
    "stage_name_review": {"zh": "审查意见", "en": "Review opinion"},
    "stage_name_issuance": {"zh": "签发状态", "en": "Issuance"},
    "issuance_kicker": {"zh": "签发状态", "en": "Issuance status"},
    "stage_kicker_submit": {"zh": "第一步 · 提交材料", "en": "Step one - submit material"},
    "stage_submit_state": {"zh": "已提交", "en": "submitted"},
    "submit_pending": {
        "zh": "正在提交，等待本机引擎响应…",
        "en": "Submitting; waiting for the local engine…",
    },
    "submit_done": {"zh": "已出具", "en": "Opinion issued"},
    "satire_line": {
        "zh": "本输出是讽刺作品，不测量任何人的感情。",
        "en": "This output is satire. It does not measure anyone's feelings.",
    },
    # PR-4R: the issuance stamp is a state word, so it follows the interface language like the
    # rest of the flow. Short labels only - the sentence beside them carries the meaning.
    "stamp_signed": {"zh": "已签", "en": "SIGNED"},
    "stamp_unsigned": {"zh": "未签", "en": "NOT SIGNED"},
    # a withheld conclusion with material on file says so on the stamp itself, so a
    # reader never has to guess why nothing was signed
    "stamp_material_pending": {
        "zh": "未签\n材料在卷",
        "en": "NOT SIGNED\nMATERIAL ON FILE",
    },
    "stamp_boundary": {"zh": "边界", "en": "BOUNDARY"},
    # PR-4R: the one-line leads of stages 02-04, so an English interface does not run the
    # four-stage flow in Chinese.
    "material_lead": {
        "zh": "本机构到底听到了什么。",
        "en": "What this agency actually heard.",
    },
    "review_lead": {
        "zh": "这些材料能不能支持你准备下的那个结论。",
        "en": "Whether this file can carry the conclusion you came for.",
    },
    "issuance_lead": {
        "zh": "本机构这次究竟签没签。",
        "en": "Whether this agency signed anything at all.",
    },
    # PR-4R: one obvious step back to the counter after reading the outcome. It returns the
    # reader to the intake and never clears what they submitted.
    "submit_another": {"zh": "继续交材料", "en": "Submit another"},
    # PR-4R: stage 02 when evidence was adjudicated without any separate material record. That
    # is not the same as "nothing was recognised", and it must never read as "NED did not
    # understand you"; the wording states the architecture instead.
    "stage_material_independent_none": {
        "zh": "本次无独立材料登记项",
        "en": "no separate material item",
    },
    # PR-4R: the fact row of the material-only screen, worded exactly as the CLI
    # screen words it, so the two surfaces cannot disagree.
    "fact_material_only": {
        "zh": "已登记材料 {n} 条，均不足以单独签发结论。",
        "en": "Material on file: {n}. None of it can be signed on its own.",
    },
    "material_empty_independent_none": {
        "zh": "本次没有独立材料登记项；审查意见直接来自输入中识别到的证据。",
        "en": "No separate material item was filed; this opinion rests on the evidence "
        "recognised in the input.",
    },
}


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
        "reading_slot": READING_SLOT,
        "clause_separators": list(CLAUSE_SEPARATORS),
        "self_discount_signal_types": list(SELF_DISCOUNT_SIGNAL_TYPES),
        "self_discount_promotes": list(SELF_DISCOUNT_PROMOTES),
        "fact_signal_types": {key: list(value) for key, value in FACT_SIGNAL_TYPES.items()},
        "fact_from_observed": list(FACT_FROM_OBSERVED),
        "duration_artifacts": list(DURATION_ARTIFACTS),
        "display_repairs": [list(pair) for pair in DISPLAY_REPAIRS],
        "quality_source": QUALITY_SOURCE,
        "quality_bands": [[maximum, zh, en] for maximum, zh, en in QUALITY_BANDS],
        "quality_top": {"zh": QUALITY_TOP[0], "en": QUALITY_TOP[1]},
        "explicit_quality": {"zh": EXPLICIT_QUALITY[0], "en": EXPLICIT_QUALITY[1]},
        "pair_quality_labels": PAIR_QUALITY_LABELS,
        "forbidden_emoji": {key: list(value) for key, value in FORBIDDEN_EMOJI.items()},
        "verdict_overrides": VERDICT_DISPLAY_OVERRIDES,
        "comedy_packs": {
            key: {
                "title": pack.title,
                "lines": list(pack.lines),
                "hypotheses": [
                    {"hypothesis": text, "category": category, "plausibility": value}
                    for text, category, value in pack.hypotheses
                ],
            }
            for key, pack in COMEDY_PACKS.items()
        },
        "comedy_by_rule": COMEDY_PACK_BY_RULE,
        "routine_markers": list(ROUTINE_MARKERS),
        "greeting_rule": GREETING_RULE,
        "routine_claim": ROUTINE_CLAIM,
        "greeting_one_off_fact": ONE_OFF_GREETING_FACT,
        "multiple_aspects_situation": SITUATION_MULTIPLE_ASPECTS,
        "multiple_aspects_promotes": list(MULTIPLE_ASPECTS_PROMOTES),
        "aspect_card_situations": list(ASPECT_CARD_SITUATIONS),
        "materials_slot": MATERIALS_SLOT,
        "material_registry_copy": {key: material_registry_copy(key) for key in ("zh", "en")},
        "material_source_labels": MATERIAL_SOURCE_LABELS,
        "boundary_page_types": list(aspect_pages.BOUNDARY_TYPES),
        "materials_fallback": MATERIALS_FALLBACK,
        "aspect_page_labels": {key: list(value) for key, value in ASPECT_PAGE_LABELS.items()},
        "aspect_copy": {key: dict(value) for key, value in ASPECT_COPY.items()},
        "aspect_boundary_copy": {key: dict(value) for key, value in ASPECT_BOUNDARY_COPY.items()},
        "fact_fixed": {key: dict(value) for key, value in FACT_FIXED.items()},
        "explanation_audit_situation": SITUATION_EXPLANATION_AUDIT,
        "audit_flavours": {key: list(lines) for key, lines in AUDIT_FLAVOURS.items()},
        "audit_default_lines": list(AUDIT_DEFAULT_LINES),
        "audit_copy": AUDIT_COPY,
        "front_desk": {key: dict(value) for key, value in FRONT_DESK_COPY.items()},
    }


__all__ = [
    "ANALYSIS_FEEDBACK",
    "ASPECT_BOUNDARY_COPY",
    "ASPECT_CARD_SITUATIONS",
    "ASPECT_COPY",
    "ASPECT_PAGE_LABELS",
    "AUDIT_COPY",
    "AUDIT_DEFAULT_LINES",
    "AUDIT_FLAVOURS",
    "AUDIT_REALITY",
    "BOUNDARY_SITUATIONS",
    "CLAUSE_SEPARATORS",
    "COMEDY_PACKS",
    "COMEDY_PACK_BY_RULE",
    "COMPARISON_REASON_VERDICTS",
    "DISPLAY_REPAIRS",
    "DURATION_ARTIFACTS",
    "EXPLICIT_QUALITY",
    "FACT_FIXED",
    "FACT_FROM_OBSERVED",
    "FACT_SIGNAL_TYPES",
    "FIRST_SCREEN",
    "FNBP_HIT_FEEDBACK",
    "FNBP_MISS_FEEDBACK",
    "FORBIDDEN_EMOJI",
    "FRONT_DESK_COPY",
    "GREETING_RULE",
    "MATERIALS_FALLBACK",
    "MATERIALS_SLOT",
    "MATERIAL_REGISTRY_COPY",
    "MATERIAL_SOURCE_LABELS",
    "MODES",
    "MULTIPLE_ASPECTS_PROMOTES",
    "MULTIPLE_ASPECTS_REALITY",
    "NEA_FRAMING",
    "ONE_OFF_GREETING_FACT",
    "PAIR_QUALITY_LABELS",
    "QUALITY_BANDS",
    "QUALITY_SOURCE",
    "QUALITY_TOP",
    "READING_SIGNAL_TYPES",
    "READING_SLOT",
    "READING_STATUS_MESSAGES",
    "ROUTINE_CLAIM",
    "ROUTINE_MARKERS",
    "SELF_DISCOUNT_PROMOTES",
    "SELF_DISCOUNT_SIGNAL_TYPES",
    "SITUATION_BY_COMPARISON_REASON",
    "SITUATION_BY_VERDICT",
    "SITUATION_EXPLANATION_AUDIT",
    "SITUATION_MULTIPLE_ASPECTS",
    "TECHNICAL_REACHING",
    "VERDICT_DISPLAY_OVERRIDES",
    "ComedyPack",
    "FirstScreen",
    "PersonalityFeedback",
    "analysis_feedback",
    "aspect_breakdown_rows",
    "aspect_copy",
    "audit_breakdown_rows",
    "audit_lines",
    "captured_reading",
    "comedy_hypotheses",
    "comedy_pack",
    "comedy_pack_key",
    "emoji_discipline",
    "explicit_quality_label",
    "fact_fixed",
    "fact_from_observed",
    "fact_override",
    "fact_signal_types",
    "fill_materials",
    "fill_reading",
    "first_screen",
    "fnbp_feedback",
    "greeting_is_one_off",
    "has_missing_duration",
    "is_boundary_situation",
    "material_registry_copy",
    "material_registry_rows",
    "nea_framing",
    "page_grade",
    "page_label",
    "pair_quality_label",
    "primary_positive_rule",
    "quality_label",
    "reading_basis_present",
    "reading_message",
    "repair_display_text",
    "resolve_situation",
    "screen_situation",
    "verdict_display",
    "web_personality_catalog",
]
