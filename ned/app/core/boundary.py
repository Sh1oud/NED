"""Who owns a stated relationship boundary.

``direct_rejection`` means, in the rule pack's own words, that *the other person*
directly and explicitly expressed a refusal or a boundary (``interpretations.zh``:
"对方直接、明确地表达了拒绝或边界"), and the screen says a stated boundary is an
*action, not an inference* (``说出口的边界是一个行为，不是推断``). The family's patterns,
however, match a lot of material that carries no author: bare stock lines
(``做朋友吧``, ``保持距离``, ``我们不合适``), imperatives (``让我滚``) and reported clauses.
Three other authors therefore reach the boundary screen and were never hers:

* the reader, speaking or concluding (``我跟她说…``, ``我觉得我们不合适``);
* a third party, relaying (``她妈妈跟我说…``, ``室友告诉我…``);
* somebody else entirely being the owner of the proposition
  (``她跟我说她姐姐只想当普通朋友``, ``她告诉我别人觉得我们不合适``).

This module answers one tiny question for a match: **is the other person the author
of this stance, and is the stance about her own relationship with the reader?** It
does not parse in general, does not judge truth, does not classify relationships,
and does not touch any other family. Like the reader-owned firewall in
``attribution.py`` it only ever *removes* spans, and it answers *no* when it cannot
tell.

How it decides, without a list of people or a list of reporting verbs:

* the prefix is the text in front of the match inside its own clause; the stance is
  the matched text itself;
* leading closed-class tokens are dropped: hedges/adverbs/particles, plus the
  ``X着`` adverbial form (``她哭着说``);
* the prefix is then read as a walk of *frames* and *roles*. A frame is a receiver
  frame (``跟/和/与/对/向/给`` + receiver, or ``告诉/通知/告知`` + receiver, optionally
  with a delivery noun), a speech verb, or a cognition verb. Everything the walk
  cannot place in a frame is a *content token*;
* the speaker slot in front of the first frame must be the described pronoun alone
  (``她``/``他``/``对方``). A content token there is a noun phrase
  (``她妈妈``, ``室友``, ``小王``, ``我妈``), and a noun phrase is somebody else;
* no content token may stand between frames (``她告诉我别人觉得…``);
* the stance's own subject, when it has one, must be followed by the family's
  predicate vocabulary rather than by a noun, so a possessive phrase
  (``她姐姐…``) is not her stance.

That is what makes the closure structural rather than sampled: the receiver slot is
the only place an open-class noun is allowed, because a preposition or a
receiver-object verb marks it there. ``老师``, ``小王``, ``群里有人``, ``表哥`` and any
other named person cannot be admitted as the *speaker* by construction, and no
reporting verb (``转述``, ``嘀咕``, ``断言``) needs to be known.
"""

from __future__ import annotations

import itertools

from ned.app.core import attribution

#: The other person, and the reader. Closed classes.
DESCRIBED_PRONOUNS = attribution.DESCRIBED_PRONOUNS
READER_PRONOUNS = attribution.READER_PRONOUNS

#: A clause ends here; the prefix never crosses one.
CLAUSE_BREAKS = attribution.CLAUSE_BREAKS

#: 我们/咱们/咱俩/你我 name both people: they are one subject, never 我 plus a stray
#: character, and they are neither the reader alone nor the other person alone.
INCLUSIVE_PRONOUNS = ("\u6211\u4eec", "\u54b1\u4eec", "\u54b1\u4fe9", "\u4f60\u6211")

#: The reader as the person being addressed. Inside her quote 你 is the reader.
ADDRESSEE_PRONOUNS = ("\u4f60\u4eec", "\u60a8", "\u4f60")

#: Every pronoun the walk recognises, longest first so 我们 is not read as 我.
ALL_PRONOUNS = tuple(
    sorted(
        [
            *INCLUSIVE_PRONOUNS,
            *ADDRESSEE_PRONOUNS,
            *attribution.DESCRIBED_PRONOUNS,
            *attribution.READER_PRONOUNS,
        ],
        key=len,
        reverse=True,
    )
)

#: Hedges, adverbs, particles, negation: they may stand anywhere between roles.
FILLERS = (
    *attribution.MARKERS,
    *(
        "\u660e\u786e",
        "\u76f4\u63a5",
        "\u4eb2\u53e3",
        "\u5f53\u9762",
        "\u521a\u521a",
        "\u521a\u624d",
        "\u540e\u6765",
        "\u6700\u540e",
        "\u7a81\u7136",
        "\u7ec8\u4e8e",
        "\u751a\u81f3",
        "\u8fd9\u4e0b",
        "\u5e72\u8106",
        "\u53ea",
        "\u4ec5",
        "\u4ec5\u4ec5",
        "\u53ea\u4e0d\u8fc7",
        "\u5c31",
        "\u624d",
        "\u5012",
        "\u5374",
        "\u53cd\u6b63",
        "\u6bd5\u7adf",
        "\u7136\u540e",
        "\u63a5\u7740",
        "\u4e4b\u540e",
        "\u800c\u540e",
        "\u968f\u540e",
        "\u63a5\u4e0b\u6765",
        "\u518d",
        "\u518d\u6b21",
        "\u91cd\u65b0",
        "\u9a6c\u4e0a",
        "\u7acb\u523b",
        "\u8d76\u7d27",
        "\u6ca1\u5173\u7cfb",
        "\u6ca1\u4e8b",
        "以后",
        "之前",
        "从此",
        "再也",
        "永远",
        "从前",
    ),
)
FILLERS = tuple(sorted(set(FILLERS), key=len, reverse=True))

#: The receiver slot: a preposition, or a verb that takes the receiver as object.
RECEIVER_PREPOSITIONS = ("\u8ddf", "\u548c", "\u4e0e", "\u5bf9", "\u5411", "\u7ed9", "\u66ff")

#: Those prepositions (and 把) are function words *inside* phrases, but they also
#: begin a receiver frame. The walk must never step over them as filler, or
#: "她给我发消息说" loses its frame and turns into a stray pronoun plus content.
FILLERS = tuple(token for token in FILLERS if token not in {*RECEIVER_PREPOSITIONS, "\u628a"})
RECEIVER_VERBS = ("\u544a\u8bc9", "\u901a\u77e5", "\u544a\u77e5", "\u63d0\u9192")

#: Speech, then cognition: both say the stance belongs to whoever is speaking.
SPEECH_VERBS = (
    "\u544a\u8bc9",
    "\u901a\u77e5",
    "\u544a\u77e5",
    "\u8868\u793a",
    "\u56de\u590d",
    "\u7b54\u5e94",
    "\u89e3\u91ca",
    "\u8bf4",
    "\u8bb2",
    "\u79f0",
    "\u9053",
    "\u7b54",
    "\u95ee",
)
COGNITION_VERBS = (
    "\u89c9\u5f97",
    "\u8ba4\u4e3a",
    "\u4ee5\u4e3a",
    "\u611f\u89c9",
    "\u6000\u7591",
    "\u76f8\u4fe1",
    "\u77e5\u9053",
    "\u660e\u767d",
    "\u731c",
    "\u60f3",
)

#: A delivery noun may sit inside the receiver frame: 给我发消息说, 给我打电话说.
DELIVERY = ("\u6d88\u606f", "\u4fe1\u606f", "\u5fae\u4fe1", "\u8bed\u97f3", "\u7535\u8bdd")

#: Aspect particles and quote marks: they carry no author.
ASPECT = ("\u8fc7", "\u4e86", "\u7740")
QUOTES = ("\u201c", "\u201d", '"', "'", "\u2018", "\u2019", "\uff1a", ":")
PARTICLES = (
    "\u7684",
    "\u4e86",
    "\u7740",
    "\u8fc7",
    "\u5427",
    "\u554a",
    "\u5462",
    "\u5417",
    "\u561b",
)

#: What may follow the stance's own subject: the family's predicate vocabulary.
#: A noun here means the subject is a possessive phrase, i.e. somebody else.
STANCE_HEADS: tuple[str, ...] = (
    "\u4e0d",
    "\u6ca1",
    "\u522b",
    "\u60f3",
    "\u8981",
    "\u613f",
    "\u80fd",
    "\u4f1a",
    "\u6562",
    "\u80af",
    "\u6253\u7b97",
    "\u51b3\u5b9a",
    "\u62d2\u7edd",
    "\u8ba9",
    "\u53eb",
    "\u547d\u4ee4",
    "\u8981\u6c42",
    "\u903c",
    "\u4fdd\u6301",
    "\u505a",
    "\u5f53",
    "\u53d1\u5c55",
    "\u8c08",
    "\u5f00\u59cb",
    "\u89c1",
    "\u8054\u7cfb",
    "\u8bf4\u8bdd",
    "\u804a\u5929",
    "\u6765\u5f80",
    "\u70e6",
    "\u6253\u6270",
    "\u627e",
    "\u7406",
    "\u7ba1",
    "\u51fa\u73b0",
    "\u79bb",
    "\u6eda",
    "\u8d70\u5f00",
    "\u63a5\u53d7",
    "\u540c\u610f",
    "\u62b1\u6b49",
    "\u5408\u9002",
    "\u5408\u5f97\u6765",
    "\u4e0d\u5408",
    "\u5bf9",
    "\u8ddf",
    "\u548c",
    "\u4e0e",
    "\u5411",
    "\u7ed9",
    "\u662f",
    "\u7684",
    "\u4e86",
    "\u7740",
    "\u8fc7",
    "\u5427",
    "\u554a",
    "\u5462",
    "\u5417",
)
STANCE_HEADS = tuple(
    sorted({*SPEECH_VERBS, *COGNITION_VERBS, *STANCE_HEADS}, key=len, reverse=True)
)

#: Mental state, not expression: a wish or a belief is not a stated boundary.
MENTAL_VERBS: tuple[str, ...] = (
    *COGNITION_VERBS,
    "\u5e0c\u671b",
    "\u60f3\u8981",
    "\u6253\u7b97",
    "\u51b3\u5b9a",
)
MENTAL_VERBS = tuple(sorted(set(MENTAL_VERBS), key=len, reverse=True))

#: Directives: the causative verbs take the reader as their object.
CAUSATIVE_VERBS = ("\u547d\u4ee4", "\u8981\u6c42", "\u8ba9", "\u53eb", "\u903c")

#: Action classes with opposite polarity. A distancing action is a boundary only when
#: it is a directive; a contact action is a boundary only when it is prohibited.
DISTANCING_ACTIONS = ("\u6eda", "\u8d70\u5f00", "\u79bb\u5f00")
CONTACT_ACTIONS = ("\u8054\u7cfb", "\u627e", "\u7406", "\u70e6", "\u6253\u6270")
PROHIBITIVE_MARKERS = ("\u4e0d\u8981", "\u4e0d\u7528", "\u4e0d\u51c6", "\u4e0d\u8bb8", "\u522b")

#: The quote marks that open her direct speech.
QUOTE_OPENERS = ("\u201c", "\u201d", '"', "'", "\u2018", "\u2019", "\uff1a", ":")

#: A sentence ends here; speaker inheritance never crosses one.
SENTENCE_BREAKS = "\u3002\uff01\uff1f!?\n\r"

#: Coordination markers that may carry a report scope across a clause break.
COORDINATION_MARKERS = ("但是", "不过", "可是", "但", "却")

#: The passive: in "我表白被拒了" the reader is the patient and the other person the
#: agent, so a first-person pronoun does not make the reader the author.
PASSIVE = ("\u88ab", "\u906d\u5230", "\u906d")


def _clause_prefix(text: str, start: int) -> str:
    """Everything in front of ``start`` inside its own clause."""

    for index in range(start - 1, -1, -1):
        if text[index] in CLAUSE_BREAKS:
            return text[index + 1 : start]
    return text[:start]


def _skip_fillers(text: str, index: int) -> int:
    """Advance past closed-class material, including the ``X着`` form."""

    while index < len(text):
        for token in FILLERS + QUOTES + ASPECT + PARTICLES:
            if text.startswith(token, index):
                index += len(token)
                break
        else:
            if index + 1 < len(text) and text[index + 1] == "\u7740":
                index += 2
                continue
            return index
    return index


def _starts_with(text: str, index: int, tokens: tuple[str, ...]) -> str | None:
    for token in sorted(tokens, key=len, reverse=True):
        if text.startswith(token, index):
            return token
    return None


def _receiver_token_length(text: str, index: int) -> int:
    """Length of the receiver phrase: a run that ends where the speech starts."""

    length = 0
    while length < 6 and index + length < len(text):
        if _starts_with(text, index + length, SPEECH_VERBS + ASPECT + STANCE_HEADS) is not None:
            break
        if text[index + length] in CLAUSE_BREAKS or text[index + length] in QUOTES:
            break
        length += 1
    return length


def _receiver_end(text: str, index: int) -> int | None:
    """End of a receiver slot at ``index``, or None."""

    token = _starts_with(text, index, RECEIVER_PREPOSITIONS + RECEIVER_VERBS)
    if token is None:
        return None
    return index + len(token) + _receiver_token_length(text, index + len(token))


def _frame_end(text: str, index: int) -> tuple[int, str] | None:
    """A frame at ``index``: (end, kind) with kind in receiver/speech/mental/causative."""

    if _starts_with(text, index, ALL_PRONOUNS) is not None:
        # A pronoun is never the head of a frame: 对方 is not 对 + a receiver.
        return None
    causative = _starts_with(text, index, CAUSATIVE_VERBS)
    if causative is not None:
        cursor = index + len(causative)
        length = _receiver_token_length(text, cursor)
        if length:
            return cursor + length, "causative"
    after_receiver = _receiver_end(text, index)
    if after_receiver is not None:
        cursor = _skip_fillers(text, after_receiver)
        while cursor < len(text):
            delivery = _starts_with(text, cursor, DELIVERY)
            if delivery is None:
                break
            cursor = _skip_fillers(text, cursor + len(delivery))
        speech = _starts_with(text, cursor, SPEECH_VERBS)
        if speech is not None:
            return cursor + len(speech), "receiver"
        return after_receiver, "receiver"
    speech = _starts_with(text, index, SPEECH_VERBS)
    if speech is not None:
        return index + len(speech), "speech"
    mental = _starts_with(text, index, MENTAL_VERBS)
    if mental is not None:
        return index + len(mental), "mental"
    return None


def _walk_spans(text: str) -> list[tuple[str, str, int]]:
    """Roles with their offsets, so adjacency can be read off the text.

    The walk stops at the first predicate: everything from there on is the
    proposition itself, which this module does not need to read.
    """

    tokens: list[tuple[str, str, int]] = []
    index = 0
    while index < len(text):
        frame = _frame_end(text, index)
        if frame is not None:
            end, kind = frame
            tokens.append((kind, text[index:end], index))
            index = end
            continue
        pronoun = _starts_with(text, index, ALL_PRONOUNS)
        if pronoun is not None:
            tokens.append(("pronoun", pronoun, index))
            index += len(pronoun)
            continue
        skipped = _skip_fillers(text, index)
        if skipped != index:
            index = skipped
            continue
        head = _starts_with(text, index, STANCE_HEADS)
        if head is not None:
            tokens.append(("predicate", head, index))
            break
        tokens.append(("content", text[index], index))
        index += 1
    return tokens


def _walk(text: str) -> list[tuple[str, str]]:
    return [(kind, token) for kind, token, _start in _walk_spans(text)]


def _adjacent_content(tokens: list[tuple[str, str, int]]) -> bool:
    """A content word glued to a subject or a frame is a noun phrase.

    她妈妈…, 我妈…, 告诉我别人…: the content follows with nothing (or only a negation)
    in between, and the chain starts at the pronoun or the frame. A content word
    behind a filler (他可能生气了…, 她可能不喜欢我…) belongs to the predicate instead.
    """

    glued = False
    for previous, current in itertools.pairwise(tokens):
        kind, _token, start = current
        gap = start - (previous[2] + len(previous[1]))
        if kind == "content":
            if gap == 0 or (gap == 1 and previous[0] != "content"):
                glued = previous[0] != "content" or glued
            else:
                glued = False
            if glued:
                return True
            continue
        glued = False
    return False


def _is_a_relay(tokens: list[tuple[str, str, int]]) -> bool:
    """A noun phrase in the speaker slot followed by a speech frame.

    她妈妈说…, 她朋友说…: the clause names somebody else as the speaker, so it cannot
    lend its speaker to the next clause.
    """

    adjacent = False
    for kind, _token, _start in tokens[1:]:
        if kind == "content":
            adjacent = True
            continue
        if kind in ("receiver", "speech") and adjacent:
            return True
        if kind in ("pronoun", "predicate", "causative", "mental"):
            adjacent = False
    return False


def _clause_end(text: str, start: int) -> int:
    for index in range(start, len(text)):
        if text[index] in CLAUSE_BREAKS:
            return index
    return len(text)


def _opens_a_quote(prefix: str) -> bool:
    """True when the closed prefix puts the match inside her own speech.

    A quotation mark does it, and so does reported speech without one: the first
    person of a reported imperative belongs to the speaker, not to the reader.
    """

    return any(kind in ("speech", "receiver") for kind, _ in _walk(prefix))


def _opens_with_coordination(prefix: str) -> bool:
    """True when the clause begins with a coordination marker.

    Only 但/但是/不过/可是/却 may carry a report scope across a clause break; an
    arbitrary preceding clause does not lend its speaker.
    """

    stripped = prefix.strip()
    return any(stripped.startswith(marker) for marker in COORDINATION_MARKERS)


def _previous_clause(text: str, start: int) -> str:
    """The clause before the one the match sits in, inside the same sentence."""

    sentence = 0
    for index in range(start - 1, -1, -1):
        if text[index] in SENTENCE_BREAKS:
            sentence = index + 1
            break
    head = text[sentence:start]
    last = -1
    for index in range(len(head) - 1, -1, -1):
        if head[index] in CLAUSE_BREAKS:
            last = index
            break
    if last < 0:
        return ""
    before = head[:last]
    cut = 0
    for index in range(len(before) - 1, -1, -1):
        if before[index] in CLAUSE_BREAKS:
            cut = index + 1
            break
    return before[cut:]


def _inherited_speaker(text: str, start: int) -> str:
    """The other person, when the clause in front of this one speaks for it.

    Only the previous clause of the same sentence is consulted, and only when its own
    speaker slot is hers alone: "他说我很好 但我们不合适" continues his report, while
    "她妈妈跟我说 她不想见我" must not become her own statement.
    """

    previous = _previous_clause(text, start)
    if not previous.strip():
        return ""
    tokens = _walk_spans(previous)
    if not tokens or tokens[0][0] != "pronoun" or tokens[0][1] not in DESCRIBED_PRONOUNS:
        return ""
    if _is_a_relay(tokens):
        return ""
    return tokens[0][1]


def _stance_subject_ok(stance: str) -> bool:
    """The stance's own subject, when it has one, must not be a possessive phrase."""

    tokens = _walk(stance)
    if not tokens or tokens[0][0] != "pronoun":
        return True
    pronoun = tokens[0][1]
    if pronoun in READER_PRONOUNS:
        # 我表白被拒了: the reader is the patient, the other person the agent.
        return any(marker in stance for marker in PASSIVE)
    if pronoun in INCLUSIVE_PRONOUNS:
        return True
    return not any(kind == "content" for kind, _ in tokens[1:])


def _stance_owns_itself(stance: str) -> bool:
    """POLICY A's only exceptions.

    A bare utterance belongs to the reader unless the stance itself makes the other
    person its subject, or the reader is the passive patient of somebody else's act.
    A bare causative is not an exception: its causer is unmarked.
    """

    tokens = _walk(stance)
    if not tokens or tokens[0][0] != "pronoun":
        return False
    pronoun = tokens[0][1]
    if pronoun in DESCRIBED_PRONOUNS:
        return True
    if pronoun in READER_PRONOUNS:
        return any(marker in stance for marker in PASSIVE)
    return False


def _stance_is_directive(stance: str) -> bool:
    """True when the stance orders or forbids somebody: 让我…, 别联系…."""

    if any(kind == "causative" for kind, _ in _walk(stance)):
        return True
    for action in CONTACT_ACTIONS + DISTANCING_ACTIONS:
        at = stance.find(action)
        if at <= 0:
            continue
        window = stance[max(0, at - 4) : at]
        if any(marker in window for marker in PROHIBITIVE_MARKERS):
            return True
    return False


def _volition_only(tokens: list[tuple[str, str]]) -> bool:
    """Her wish or belief, with no speech frame: not an expression."""

    kinds = [kind for kind, _ in tokens]
    return "mental" in kinds and not any(kind in ("speech", "receiver") for kind in kinds)


def _contact_target_ok(
    clause: str,
    stance: str,
    start: int,
    sender: str,
    in_quote: bool,
    her_speaking: bool,
) -> bool:
    """A directive CONTACT action must carry a target that denotes the sender.

    "她让我别联系她" keeps; "…别联系他", "…别人", "…我" and "…她朋友" do not, and an
    omitted target is hers only when she is the one speaking (she quotes herself).
    """

    causative = any(kind == "causative" for kind, _ in _walk(stance))
    offset = start  # the stance begins at the match offset inside the clause
    cursor_in_stance = 0
    while cursor_in_stance < len(stance):
        found = None
        for action in CONTACT_ACTIONS:
            at = stance.find(action, cursor_in_stance)
            if at != -1 and (found is None or at < found[0]):
                found = (at, action)
        if found is None:
            return True
        at, action = found
        cursor_in_stance = at + len(action)
        window = stance[max(0, at - 4) : at]
        if not any(marker in window for marker in PROHIBITIVE_MARKERS):
            continue
        cursor = offset + cursor_in_stance
        token = _starts_with(clause, cursor, ALL_PRONOUNS)
        if token is None:
            # "她说以后别联系了" elides the object, and there it is the speaker
            # herself; "她让我别联系" leaves it unknown.
            if causative:
                return False
            return her_speaking
        after = _walk(clause[cursor + len(token) :])
        if after and after[0][0] == "content":
            # 她朋友 / 他家人: the pronoun is a modifier, the target is a noun phrase.
            return False
        if in_quote:
            # inside her speech the first person is her, and reported speech
            # names her with the sender pronoun instead
            return token in READER_PRONOUNS or token == sender
        if token not in DESCRIBED_PRONOUNS:
            return False
        return token == sender
    return True


def _sender_of(*token_lists: list[tuple[str, str]]) -> str:
    for tokens in token_lists:
        if tokens and tokens[0][0] == "pronoun" and tokens[0][1] in DESCRIBED_PRONOUNS:
            return tokens[0][1]
    return ""


def _reader_is_the_speaker(tokens: list[tuple[str, str]]) -> bool:
    """The reader narrates their own speech, cognition or directive."""

    if not tokens:
        return False
    kind, token = tokens[0]
    if kind != "pronoun" or token not in READER_PRONOUNS + INCLUSIVE_PRONOUNS:
        return False
    return any(other in ("receiver", "speech", "mental", "causative") for other, _ in tokens)


def hers(text: str, start: int, end: int) -> bool:
    """Whether the other person is the author of the stance at ``[start:end]``."""

    stance = text[start:end]
    if not _stance_subject_ok(stance):
        return False

    prefix = _clause_prefix(text, start)
    spans = _walk_spans(prefix)
    tokens = _walk(prefix)
    in_quote = _opens_a_quote(prefix)
    sender = _sender_of(tokens, _walk(stance)) or _inherited_speaker(text, start)
    clause = text[start - len(prefix) : _clause_end(text, start)]
    her_speaking = in_quote or (
        bool(tokens)
        and tokens[0][0] == "pronoun"
        and tokens[0][1] in DESCRIBED_PRONOUNS
        and any(other in ("receiver", "speech") for other, _ in tokens[1:])
    )
    if not _contact_target_ok(clause, stance, len(prefix), sender, in_quote, her_speaking):
        return False

    if not tokens:
        # POLICY A: no speaker is named, so the utterance belongs to the reader,
        # unless the stance itself is hers or the clause in front names her.
        if _inherited_speaker(text, start):
            return True
        return _stance_owns_itself(stance)

    if _reader_is_the_speaker(tokens):
        return False

    kind, token = tokens[0]
    if kind == "content":
        # A noun phrase where the speaker must be: 她妈妈…, 室友…, 小王…, 我妈…
        return False
    if kind != "pronoun":
        # A frame with no speaker named in front of it: the subject may simply be
        # elided in the clause in front ("他约我周末看电影，后来又说我们保持距离吧"),
        # otherwise POLICY A asks the stance itself to name her ("让我滚" alone
        # names nobody).
        if _inherited_speaker(text, start):
            return True
        return _stance_owns_itself(stance)
    if token not in DESCRIBED_PRONOUNS:
        # A joint subject ("我们") can continue a report the clause in front opened, but
        # only across a restricted coordination boundary and only when that clause
        # really is her/his report: "他说他很喜欢我 但我们还是做朋友吧".
        # A joint subject continues a report only across a restricted coordination
        # boundary; otherwise it is the reader, or a joint subject the reader speaks for.
        return bool(
            token in INCLUSIVE_PRONOUNS
            and _opens_with_coordination(prefix)
            and _inherited_speaker(text, start)
        )

    if in_quote:
        # Inside her direct speech everything is hers, but a noun phrase there still
        # belongs to somebody else ("她说："我妈觉得我们不合适"").
        return not _adjacent_content(spans)

    if _volition_only(tokens) and _stance_is_directive(stance):
        # 她想让我离开: a wish about what the reader should do is not a statement.
        return False
    return not _adjacent_content(spans)


__all__ = ["ALL_PRONOUNS", "INCLUSIVE_PRONOUNS", "hers"]
