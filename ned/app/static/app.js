/* NED - Nov1ce Evidence Denier
   Frontend controller. No dependencies, no build step, no third-party requests.
   Every value the API returns is untrusted text, so the renderers are defensive
   by design: a missing field becomes an em dash instead of a throw.

   The result page is a personality page first: title, fact, plain-language
   evidence quality, NED's line, a short reality check, and only then a folded
   Technical Details block. All of that copy comes from the personality
   catalogue that the server embeds; this file only looks values up. */
(function () {
  "use strict";

  var DASH = "\u2014";
  var NO_HYPOTHESES = "No alternative hypotheses were generated for this input. Leaving the evidence alone is itself suspicious.";
  var SEVERITIES = ["info", "warning", "reject", "chaos"];
  var MODE_KEY = "ned.mode";
  var TABS = [
    { tab: "tab-analyze", panel: "panel-analyze" },
    { tab: "tab-asymmetry", panel: "panel-asymmetry" },
    { tab: "tab-lab", panel: "panel-lab" }
  ];
  var state = { analyze: null, asymmetry: null, fnbp: null, health: null };

  /* ------------------------------------------------------------ primitives */

  function $(id) { return document.getElementById(id); }
  function obj(v) { return v && typeof v === "object" && !Array.isArray(v) ? v : {}; }
  function list(v) { return Array.isArray(v) ? v : []; }
  function keys(v) { return Object.keys(obj(v)); }
  function clear(node) { while (node && node.firstChild) { node.removeChild(node.firstChild); } }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) { n.className = cls; }
    if (text !== undefined && text !== null) { n.textContent = String(text); }
    return n;
  }
  // Safety net for any server string that would otherwise reach innerHTML. The
  // app builds DOM nodes with textContent instead, so raw HTML is never parsed.
  function escapeHtml(value) {
    if (value === null || value === undefined) { return DASH; }
    return String(value).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function txt(v) { return v === null || v === undefined || v === "" || typeof v === "object" ? DASH : String(v); }
  // The first argument with something in it. (Starting at 1 skipped the value
  // the caller actually wanted, which made the web page show signal labels where
  // the CLI showed the engine's own sentence.)
  function first() {
    for (var i = 0; i < arguments.length; i += 1) {
      var candidate = arguments[i];
      if (candidate !== null && candidate !== undefined && candidate !== "" && typeof candidate !== "object") {
        return String(candidate);
      }
    }
    return DASH;
  }
  // null, undefined and "" mean "no number at all", which is not the same as 0:
  // Number(null) is 0, and a declined comparison must not read as a perfect score.
  function num(v, digits) {
    if (v === null || v === undefined || v === "") { return DASH; }
    var n = Number(v);
    return isFinite(n) ? n.toFixed(digits === undefined ? 1 : digits) : DASH;
  }
  function int(v) { var n = Number(v); return isFinite(n) ? String(Math.round(n)) : DASH; }
  function clampPct(v) { var n = Number(v); return isFinite(n) ? Math.max(0, Math.min(100, n)) : 0; }
  function isNum(v) { return v !== null && v !== "" && isFinite(Number(v)); }
  function severityOf(v) { v = String(v || "").toLowerCase(); return SEVERITIES.indexOf(v) === -1 ? "info" : v; }
  function bandFor(level) { return level >= 85 ? "overloaded" : (level >= 80 ? "reaching" : "contained"); }

  /* --------------------------------------------------------------- setters */

  function setText(id, v) { var e = $(id); if (e) { e.textContent = txt(v); } }
  function setRaw(id, v) { var e = $(id); if (e) { e.textContent = typeof v === "string" ? v : ""; } }
  function setState(id, v) { var e = $(id); if (e) { e.setAttribute("data-state", v); } }
  function setHidden(id, hidden) { var e = $(id); if (e) { e.hidden = !!hidden; } }
  function setNum(id, v, digits, suffix) {
    var e = $(id); if (!e) { return; }
    var s = num(v, digits);
    e.textContent = (s !== DASH && suffix) ? s + suffix : s;
  }
  function setBar(id, v) {
    var e = $(id); if (!e) { return; }
    var p = clampPct(v);
    e.style.width = p + "%";
    if (e.parentElement) { e.parentElement.setAttribute("aria-valuenow", String(Math.round(p * 10) / 10)); }
  }
  function setStatus(id, message, kind) {
    var e = $(id); if (!e) { return; }
    e.textContent = message || "";
    e.classList.remove("is-error", "is-busy");
    if (kind) { e.classList.add(kind); }
  }
  // Table-driven assignment: [[id, value], ...] / [[id, value, digits, suffix], ...]
  function texts(pairs) { pairs.forEach(function (p) { setText(p[0], p[1]); }); }
  function nums(pairs) { pairs.forEach(function (p) { setNum(p[0], p[1], p[2], p[3]); }); }
  function bars(pairs) { pairs.forEach(function (p) { setBar(p[0], p[1]); }); }

  /* ----------------------------------------------------------- personality */

  function personalityCatalog() {
    var node = $("personality-catalog");
    if (!node) { return {}; }
    try { return obj(JSON.parse(node.textContent || "{}")); } catch (e) { return {}; }
  }
  var CATALOG = personalityCatalog();

  function catalogueList(key) { return list(CATALOG[key]); }
  function catalogueObj(key) { return obj(CATALOG[key]); }
  function languageOf(payload) { return txt(obj(payload).language) === "en" ? "en" : "zh"; }

  function personalityFor(module, score) {
    var levels = list(CATALOG[module]);
    var value = Number(score);
    if (!isFinite(value)) { return null; }
    for (var i = 0; i < levels.length; i += 1) {
      var feedback = obj(levels[i]);
      if (value >= Number(feedback.minimum)) { return feedback; }
    }
    return null;
  }

  function renderPersonality(id, module, score) {
    var feedback = personalityFor(module, score);
    setHidden(id, !feedback);
    if (!feedback) { return; }
    setText(id + "-technical", "Technical: " + txt(feedback.technical));
    setText(id + "-zh", feedback.zh);
    setText(id + "-en", feedback.en);
  }

  function renderFnbpPersonality(predictionMisses) {
    var messages = obj(CATALOG.fnbp);
    var feedback = obj(Number(predictionMisses) > 0 ? messages.miss : messages.hit);
    setText("fnbp-personality-title", feedback.title);
    setText("fnbp-personality-zh", feedback.zh);
    setText("fnbp-personality-en", feedback.en);
  }

  // Which screen are we on? The decision table lives in the personality
  // catalogue, so the web page and the CLI can never disagree about it.
  function situationFor(verdictCode, comparisonReason) {
    var code = String(verdictCode || "");
    var reason = String(comparisonReason || "");
    if (reason && catalogueList("comparison_reason_verdicts").indexOf(code) !== -1) {
      var mapped = catalogueObj("situation_by_comparison_reason")[reason];
      if (mapped !== undefined) { return String(mapped); }
    }
    var byVerdict = catalogueObj("situation_by_verdict")[code];
    return byVerdict === undefined ? "neutral" : String(byVerdict);
  }

  function firstScreenCopy(situation, mode, language) {
    var all = catalogueObj("first_screen");
    var neutral = obj(all.neutral);
    function pick(container, key) {
      var found = obj(container)[key];
      return found && keys(found).length > 0 ? found : null;
    }
    var perMode = pick(all, situation) || pick(all, "neutral") || obj(neutral.normal);
    var perLanguage = pick(perMode, mode) || pick(perMode, "normal") || obj(neutral.normal);
    return obj(perLanguage[language]) || obj(perLanguage.zh) || {};
  }

  // Plain-language evidence quality. The bands come from the personality
  // catalogue; the reading itself is an engine number that stays in the payload.
  function qualityFromValue(value, language) {
    if (!isNum(value)) { return ""; }
    var reading = Number(value);
    var bands = catalogueList("quality_bands");
    for (var i = 0; i < bands.length; i += 1) {
      var band = list(bands[i]);
      if (reading < Number(band[0])) { return String(language === "en" ? band[2] : band[1]); }
    }
    var top = catalogueObj("quality_top");
    return txt(language === "en" ? top.en : top.zh);
  }

  function explicitQuality(language) {
    var band = catalogueObj("explicit_quality");
    return txt(language === "en" ? band.en : band.zh);
  }

  function qualityForSituation(situation, payload, language) {
    var source = String(catalogueObj("quality_source")[situation] || "none");
    if (source === "explicit") { return explicitQuality(language); }
    if (source === "strength") { return qualityFromValue(obj(payload).signal_strength, language); }
    if (source === "negative_information") {
      var strongest = null;
      list(obj(payload).evidence).forEach(function (rawRow) {
        var row = obj(rawRow);
        if (String(row.polarity || "") !== "negative") { return; }
        var info = Number(row.information_content);
        if (!isFinite(info)) { return; }
        if (strongest === null || info > strongest) { strongest = info; }
      });
      return strongest === null ? "" : qualityFromValue(strongest, language);
    }
    return "";
  }

  function sideQuality(side, klass, polarity, language) {
    if (String(klass || "") === "boundary") { return explicitQuality(language); }
    var raw = obj(side);
    return qualityFromValue(polarity === "negative" ? raw.information_content : raw.raw_strength, language);
  }

  // The reader's own wording is the only licence for a second-person line.
  function basisFromSignals(evidence) {
    var allowed = catalogueList("reading_signal_types");
    var found = false;
    list(evidence).forEach(function (rawRow) {
      if (allowed.indexOf(String(obj(rawRow).signal_type || "")) !== -1) { found = true; }
    });
    return found;
  }

  function applyEmojiDiscipline(situation, text) {
    var forbidden = list(catalogueObj("forbidden_emoji")[situation]);
    var cleaned = String(text === null || text === undefined ? "" : text);
    forbidden.forEach(function (emoji) { cleaned = cleaned.split(String(emoji)).join(""); });
    return cleaned.replace(/\s+/g, " ").trim();
  }

  // Display-only: an engine verdict that names a reader who never spoke falls
  // back to an NED-self-referential sentence. The verdict itself is untouched.
  // The emoji slot never repeats a mark the sentence already ends with, and a
  // forbidden emoji is dropped there too, so a boundary screen cannot show 🤠
  // next to a sentence that had it removed.
  function displayVerdictEmoji(emoji, situation, text) {
    var value = typeof emoji === "string" ? emoji : "";
    if (!value) { return ""; }
    if (String(text === null || text === undefined ? "" : text).indexOf(value) !== -1) { return ""; }
    var forbidden = list(catalogueObj("forbidden_emoji")[situation]);
    return forbidden.indexOf(value) === -1 ? value : "";
  }

  function displayVerdictText(code, text, situation, basis, language) {
    var cleaned = String(text === null || text === undefined ? "" : text);
    var override = obj(catalogueObj("verdict_overrides")[String(code || "")]);
    var withoutBasis = obj(override.without_basis);
    if (!basis && keys(withoutBasis).length > 0) {
      var replacement = language === "en" ? withoutBasis.en : withoutBasis.zh;
      if (replacement) { cleaned = String(replacement); }
    }
    return applyEmojiDiscipline(situation, cleaned);
  }

  function renderScreenLines(hostId, lines) {
    var host = $(hostId);
    if (!host) { return; }
    clear(host);
    list(lines).forEach(function (line) {
      if (line === null || line === undefined || line === "") { return; }
      host.appendChild(el("blockquote", "screen-line", String(line)));
    });
  }

  function renderQuotes(hostId, quotes) {
    var host = $(hostId);
    if (!host) { return; }
    clear(host);
    var rows = list(quotes).filter(function (q) { return q !== null && q !== undefined && q !== ""; });
    host.hidden = rows.length === 0;
    rows.forEach(function (quote) { host.appendChild(el("p", "screen-quote", String(quote))); });
  }

  /* --------------------------------------------------------------- network */

  function postJson(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (res) {
      return res.text().then(function (raw) {
        var data = null;
        try { data = raw ? JSON.parse(raw) : null; } catch (e) { data = null; }
        if (!res.ok) {
          var detail = data && data.detail !== undefined ? data.detail : null;
          if (detail && typeof detail !== "string") {
            try { detail = JSON.stringify(detail); } catch (e2) { detail = String(detail); }
          }
          throw new Error(detail || ("Request failed with status " + res.status + "."));
        }
        if (!data || typeof data !== "object") { throw new Error("The engine returned an unexpected response."); }
        return data;
      });
    }).catch(function (err) {
      if (err && err.name === "TypeError") { throw new Error("Could not reach the NED engine. Is the local server still running?"); }
      throw err;
    });
  }

  /* ------------------------------------------------------------------ tabs */

  function selectTab(tabId, focus) {
    TABS.forEach(function (entry) {
      var tab = $(entry.tab);
      var panel = $(entry.panel);
      var active = entry.tab === tabId;
      if (tab) {
        tab.setAttribute("aria-selected", active ? "true" : "false");
        tab.tabIndex = active ? 0 : -1;
        tab.classList.toggle("is-active", active);
        if (active && focus) { tab.focus(); }
      }
      if (panel) { panel.hidden = !active; }
    });
  }

  function initTabs() {
    var bar = document.querySelector(".tabs");
    if (!bar) { return; }
    bar.addEventListener("click", function (event) {
      var btn = event.target.closest("[role='tab']");
      if (btn && btn.id) { selectTab(btn.id, false); }
    });
    bar.addEventListener("keydown", function (event) {
      if (["ArrowRight", "ArrowLeft", "Home", "End"].indexOf(event.key) === -1) { return; }
      event.preventDefault();
      var ids = TABS.map(function (t) { return t.tab; });
      var from = ids.indexOf(document.activeElement && document.activeElement.id);
      if (from === -1) { from = 0; }
      var to = event.key === "ArrowRight" ? (from + 1) % ids.length
        : event.key === "ArrowLeft" ? (from - 1 + ids.length) % ids.length
        : event.key === "Home" ? 0 : ids.length - 1;
      selectTab(ids[to], true);
    });
  }

  /* ------------------------------------------------------------ mode select */

  function currentMode() { var sel = $("mode-select"); return sel && sel.value ? sel.value : "normal"; }

  function updateModeBlurb() {
    var sel = $("mode-select");
    if (!sel) { return; }
    var opt = sel.options[sel.selectedIndex];
    var target = $("mode-blurb");
    if (target) { target.textContent = (opt && opt.getAttribute("data-blurb")) || DASH; }
  }

  function setMode(mode) {
    var sel = $("mode-select");
    if (!sel || !mode) { return false; }
    for (var i = 0; i < sel.options.length; i += 1) {
      if (sel.options[i].value !== mode) { continue; }
      sel.value = mode;
      try { localStorage.setItem(MODE_KEY, mode); } catch (e) { /* storage unavailable */ }
      updateModeBlurb();
      return true;
    }
    return false;
  }

  function initMode() {
    var sel = $("mode-select");
    if (!sel) { return; }
    var saved = null;
    try { saved = localStorage.getItem(MODE_KEY); } catch (e) { saved = null; }
    if (saved) { setMode(saved); }
    sel.addEventListener("change", function () { setMode(sel.value); });
    updateModeBlurb();
  }

  /* -------------------------------------------------------------- examples */

  function addChip(host, item) {
    var chip = el("button", "chip");
    chip.type = "button";
    chip.setAttribute("data-text", String(item.text));
    chip.setAttribute("data-mode", String(item.mode || "normal"));
    if (item.note) { chip.title = String(item.note); }
    chip.appendChild(el("span", "chip-text", item.text));
    var foot = el("span", "chip-foot");
    if (item.note) { foot.appendChild(el("span", "chip-note", item.note)); }
    foot.appendChild(el("span", "chip-mode mono", item.mode || "normal"));
    chip.appendChild(foot);
    host.appendChild(chip);
  }

  function initExamples() {
    var host = $("example-chips");
    if (!host) { return; }
    host.addEventListener("click", function (event) {
      var chip = event.target.closest(".chip");
      if (!chip) { return; }
      var input = $("analyze-input");
      if (input) { input.value = chip.getAttribute("data-text") || ""; }
      setMode(chip.getAttribute("data-mode"));
      selectTab("tab-analyze", false);
      if (input) { input.focus(); }
    });
    if (host.children.length > 0) { return; }
    // The template rendered no chips: ask the optional endpoint for them.
    fetch("/api/examples", { headers: { Accept: "application/json" } })
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (data) { list(data && data.cases).forEach(function (c) { if (c && c.text) { addChip(host, c); } }); })
      .catch(function () { /* examples are optional */ });
  }

  /* ---------------------------------------------------------------- health */

  function refreshHealth() {
    var pill = $("health-pill");
    return fetch("/api/health", { headers: { Accept: "application/json" } })
      .then(function (res) { if (!res.ok) { throw new Error("health " + res.status); } return res.json(); })
      .then(function (data) {
        state.health = data;
        if (pill) { pill.setAttribute("data-state", "online"); }
        setText("health-text", [txt(data.engine), data.local_only ? "local-only" : "remote"].join(" \u00b7 "));
      })
      .catch(function () {
        if (pill) { pill.setAttribute("data-state", "offline"); }
        setText("health-text", "engine unreachable");
      });
  }

  /* --------------------------------------------------------- analyze render */

  function renderHypotheses(raw) {
    var host = $("hypotheses-list");
    if (!host) { return; }
    clear(host);
    var items = list(raw);
    if (items.length === 0) { host.appendChild(el("li", "hypo hypo-empty", NO_HYPOTHESES)); return; }
    items.forEach(function (rawItem) {
      var h = obj(rawItem);
      var li = el("li", "hypo");
      var meta = el("div", "hypo-meta");
      var bar = el("div", "bar");
      var fill = el("span", "bar-fill sev-chaos");
      fill.style.width = clampPct(h.plausibility) + "%";
      li.appendChild(el("div", "hypo-head", txt(h.hypothesis)));
      meta.appendChild(el("span", "tag", txt(h.category)));
      meta.appendChild(el("span", "plausibility", "plausibility " + num(h.plausibility) + "%"));
      if (h.source) { meta.appendChild(el("span", "tag", txt(h.source))); }
      if (h.rule_id) { meta.appendChild(el("span", "rule-id", txt(h.rule_id))); }
      li.appendChild(meta);
      bar.appendChild(fill);
      li.appendChild(bar);
      if (h.note) { li.appendChild(el("div", "hypo-note", txt(h.note))); }
      host.appendChild(li);
    });
  }

  function renderEvidence(raw) {
    var body = $("evidence-rows");
    if (!body) { return; }
    clear(body);
    var items = list(raw);
    if (items.length === 0) {
      var empty = el("td", "muted", "No evidence rows were returned.");
      var row = el("tr");
      empty.colSpan = 7;
      row.appendChild(empty);
      body.appendChild(row);
      return;
    }
    items.forEach(function (rawRow) {
      var r = obj(rawRow);
      var tr = el("tr");
      var signal = el("td");
      signal.appendChild(el("div", "mono", txt(r.signal_type)));
      signal.appendChild(el("div", "muted", txt(r.label)));
      tr.appendChild(el("td", "mono", txt(r.rule_id)));
      tr.appendChild(el("td", "wrap", txt(r.text)));
      tr.appendChild(signal);
      tr.appendChild(el("td", "mono", txt(r.polarity)));
      tr.appendChild(el("td", "num", num(r.base_strength)));
      tr.appendChild(el("td", "num", num(r.information_content)));
      tr.appendChild(el("td", "wrap", list(r.matched_keywords).length ? r.matched_keywords.join(", ") : DASH));
      body.appendChild(tr);
    });
  }

  function renderBreakdown(raw) {
    var body = $("breakdown-rows");
    if (!body) { return; }
    clear(body);
    var data = obj(raw);
    var names = Object.keys(data);
    if (names.length === 0) { names = [DASH]; }
    names.forEach(function (key) {
      var tr = el("tr");
      var th = el("th", "mono", key);
      th.scope = "row";
      tr.appendChild(th);
      tr.appendChild(el("td", "mono", key === DASH ? DASH : num(data[key], 3)));
      body.appendChild(tr);
    });
  }

  function renderReaching(level, label) {
    var has = isNum(level);
    var value = has ? clampPct(level) : 0;
    setNum("reaching-value", has ? level : NaN, 1, "%");
    setText("reaching-label", label);
    setBar("reaching-bar", value);
    setState("reaching-track", bandFor(value));
    setHidden("reaching-alert", !(has && value >= 80));
    setHidden("reaching-personality", !(has && value >= 80));
    var legend = $("reaching-legend");
    if (!legend || !legend.querySelectorAll) { return; }
    Array.prototype.forEach.call(legend.querySelectorAll(".legend-item"), function (item) {
      var min = Number(item.getAttribute("data-min"));
      var max = Number(item.getAttribute("data-max"));
      item.classList.toggle("is-active", has && value >= min && value <= max);
    });
  }

  function renderNEA(d) {
    var block = $("nea-block");
    if (!block) { return; }
    var observed = txt(d.observed_evidence);
    var amplified = txt(d.irrational_amplification);
    var has = observed !== DASH && observed !== "";
    block.hidden = !has;
    if (!has) { return; }
    texts([
      ["nea-observed", observed],
      ["nea-amplified", amplified === "" ? DASH : amplified]
    ]);
    // The inflated reading is the interpretation under test, not a finding.
    var framing = obj(CATALOG.nea_framing);
    setText("nea-framing", languageOf(d) === "en" ? framing.en : framing.zh);
  }

  function renderNotes(notes, eggs) {
    var block = $("engine-notes-block");
    var host = $("mode-notes");
    var eggHost = $("egg-list");
    var rows = list(notes).filter(function (item) {
      return typeof item === "string" && item.trim() !== "";
    });
    if (host) {
      clear(host);
      rows.forEach(function (note) { host.appendChild(el("li", "note-row", note)); });
    }
    var eggRows = list(eggs);
    if (eggHost) {
      clear(eggHost);
      eggHost.hidden = eggRows.length === 0;
      eggRows.forEach(function (rawEgg) {
        var egg = obj(rawEgg);
        var parts = [];
        if (egg.emoji) { parts.push(txt(egg.emoji)); }
        parts.push(txt(egg.message));
        if (egg.id) { parts.push("[" + txt(egg.id) + "]"); }
        eggHost.appendChild(el("li", "note-row", parts.join(" ")));
      });
    }
    if (block) { block.hidden = rows.length === 0 && eggRows.length === 0; }
  }

  // The reader has supplied their own discount of real positive evidence: NED
  // should answer that instead of running a generic good-news joke.
  function displaySituation(baseSituation, evidence) {
    var allowed = catalogueList("self_discount_signal_types");
    var discount = false;
    var positive = false;
    list(evidence).forEach(function (rawRow) {
      var row = obj(rawRow);
      if (allowed.indexOf(String(row.signal_type || "")) !== -1) { discount = true; }
      if (String(row.polarity || "") === "positive") { positive = true; }
    });
    var promotes = catalogueList("self_discount_promotes");
    if (discount && positive && promotes.indexOf(baseSituation) !== -1) {
      return "self_discount_positive";
    }
    return baseSituation;
  }

  // The observed fact must describe the evidence that decided this screen. The
  // named types are data; when the primary signal is not one of them, the screen
  // shows the engine's own label for the evidence that actually decided it.
  // Repairs shipped engine copy on the way out: an unfilled duration slot, or a
  // sentence that claims more than the engine knows. Data lives in the catalogue.
  function escapeRegExp(value) {
    return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function repairDisplayText(text) {
    var repaired = String(text === null || text === undefined ? "" : text);
    catalogueList("display_repairs").forEach(function (pair) {
      var parts = list(pair);
      if (parts.length !== 2 || !parts[0]) { return; }
      // case-insensitive: shipped sentences start with a capital
      repaired = repaired.replace(
        new RegExp(escapeRegExp(parts[0]), "gi"),
        function () { return String(parts[1]); }
      );
    });
    return repaired;
  }

  function screenFact(d, situation) {
    if (catalogueList("fact_from_observed").indexOf(situation) !== -1) {
      return first(d.observed_evidence, d.signal_label, d.raw_interpretation);
    }
    var wanted = list(catalogueObj("fact_signal_types")[situation]);
    if (wanted.length > 0 && wanted.indexOf(String(d.signal_type || "")) === -1) {
      var found = null;
      list(d.evidence).forEach(function (rawRow) {
        var row = obj(rawRow);
        if (found === null && wanted.indexOf(String(row.signal_type || "")) !== -1) { found = row; }
      });
      if (found) { return first(found.label, found.text); }
    }
    return first(d.raw_interpretation, d.observed_evidence, d.signal_label);
  }

  function renderAnalyzeScreen(d, situation, basis) {
    var language = languageOf(d);
    var copy = firstScreenCopy(situation, String(d.mode || "normal"), language);
    var lines = list(copy.lines);
    if (basis && list(copy.lines_with_basis).length > 0) { lines = list(copy.lines_with_basis); }
    setState("analyze-results", severityOf(obj(d.verdict).severity));
    var panel = $("first-screen");
    if (panel) { panel.setAttribute("data-situation", situation); }
    setText("screen-title", copy.title);
    setText("screen-fact", screenFact(d, situation));
    setText("screen-reality", copy.reality);
    renderScreenLines("screen-lines", lines);
    var quality = qualityForSituation(situation, d, language);
    setHidden("screen-quality-row", !quality);
    setText("screen-quality", quality || DASH);
  }

  function renderAnalyze(data) {
    var report = $("analyze-results");
    if (!report) { return; }
    var d = obj(data);
    var v = obj(d.verdict);
    var engine = obj(d.engine);
    var asym = d.asymmetry && typeof d.asymmetry === "object" ? d.asymmetry : null;
    var language = languageOf(d);
    var reason = asym ? obj(obj(asym).evidence_profile).comparison_reason : "";
    var baseSituation = situationFor(v.code, reason);
    var attached = asym ? obj(obj(asym).user_interpretation) : null;
    var situation = displaySituation(baseSituation, d.evidence);
    var basis = basisFromSignals(d.evidence) || Boolean(attached && attached.reading_present);

    report.hidden = false;
    report.classList.remove("is-loading");
    report.setAttribute("data-severity", severityOf(v.severity));
    report.setAttribute("data-situation", situation);

    renderAnalyzeScreen(d, situation, basis);

    texts([
      ["result-mode", d.mode], ["result-language", d.language], ["result-signal-type", d.signal_type],
      ["sc-signal-type", d.signal_type], ["sc-signal-label", d.signal_label], ["sc-language", d.language],
      ["reality-check-text", repairDisplayText(d.reality_check)],
      ["raw-interpretation", repairDisplayText(d.raw_interpretation)],
      ["verdict-code", v.code], ["verdict-severity", v.severity],
      ["engine-name", engine.name], ["engine-provider", engine.provider],
      ["engine-escapes", engine.escapes_used === undefined ? DASH : int(engine.escapes_used)],
      ["result-disclaimer", d.disclaimer],
      ["result-generated-at", d.generated_at ? "generated_at " + txt(d.generated_at) : DASH]
    ]);
    var shownVerdict = repairDisplayText(
      displayVerdictText(v.code, v.text, situation, basis, language)
    );
    setText("verdict-text", shownVerdict);
    nums([
      ["evidence-strength-value", d.signal_strength, 1, " / 100"],
      ["discount-value", d.positive_evidence_discount, 1, "%"],
      ["amplification-value", d.negative_evidence_amplification, 1, "%"]
    ]);
    bars([
      ["evidence-strength-bar", d.signal_strength],
      ["discount-bar", d.positive_evidence_discount],
      ["amplification-bar", d.negative_evidence_amplification]
    ]);
    setRaw("verdict-emoji", displayVerdictEmoji(v.emoji, situation, shownVerdict));
    renderHypotheses(d.alternative_explanations);
    renderReaching(d.ned_reaching_level, d.reaching_label);
    renderPersonality("reaching-personality", "analysis", d.ned_reaching_level);
    renderEvidence(d.evidence);
    renderBreakdown(d.breakdown);
    renderNEA(d);
    renderNotes(d.mode_notes, d.easter_eggs);

    setHidden("analyze-asymmetry", !asym);
    if (asym) {
      var treatment = obj(asym.ned_treatment);
      var profile = obj(asym.evidence_profile);
      var reading = obj(asym.user_interpretation);
      var messages = obj(CATALOG.user_reading);
      var message = obj(messages[reading.status]);
      setText("analyze-asym-comparable", profile.comparable ? "yes" : "NO");
      setNum(
        "analyze-asym-score",
        treatment.treatment_gap === null || treatment.treatment_gap === undefined
          ? null
          : treatment.treatment_gap * 100,
        1,
        "%"
      );
      setText("analyze-asym-label", language === "en" ? message.en : message.zh);
      setBar("analyze-asym-bar", treatment.treatment_gap === null || treatment.treatment_gap === undefined
        ? null
        : treatment.treatment_gap * 100);
      setText("analyze-asym-reality", txt(asym.reality_check || d.asymmetry_reality_check));
    }
    return report;
  }

  function runAnalyze() {
    var input = $("analyze-input");
    var button = $("analyze-submit");
    if (!input || !button) { return; }
    var text = (input.value || "").trim();
    var report = $("analyze-results");
    setStatus("analyze-status", "", null);
    if (!text) {
      setStatus("analyze-status", "Enter a message or describe what happened first.", "is-error");
      input.focus();
      return;
    }
    button.disabled = true;
    setStatus("analyze-status", "Running NED...", "is-busy");
    if (report) { report.hidden = false; report.classList.add("is-loading"); }

    postJson("/api/analyze", { text: text, mode: currentMode() })
      .then(function (data) {
        state.analyze = data;
        renderAnalyze(data);
        setStatus("analyze-status", "Analysis complete \u00b7 " + txt(data.generated_at), null);
      })
      .catch(function (err) {
        if (report) {
          report.classList.remove("is-loading");
          if (!state.analyze) { report.hidden = true; }
        }
        setStatus("analyze-status", err && err.message ? err.message : "Analysis failed.", "is-error");
      })
      .then(function () { button.disabled = false; });
  }

  /* ------------------------------------------------------------- copy json */

  function legacyCopy(payload) {
    try {
      var area = document.createElement("textarea");
      area.value = payload;
      area.setAttribute("readonly", "readonly");
      area.style.position = "fixed";
      area.style.top = "-1000px";
      document.body.appendChild(area);
      area.select();
      var ok = document.execCommand && document.execCommand("copy");
      document.body.removeChild(area);
      return !!ok;
    } catch (e) {
      return false;
    }
  }

  function initCopy() {
    var button = $("copy-json");
    if (!button) { return; }
    var original = button.textContent;
    var timer = null;
    var flash = function (label) {
      button.textContent = label;
      if (timer) { clearTimeout(timer); }
      timer = setTimeout(function () { button.textContent = original; }, 1600);
    };
    button.addEventListener("click", function () {
      if (!state.analyze) { flash("Nothing yet"); return; }
      var payload = JSON.stringify(state.analyze, null, 2);
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(payload).then(
          function () { flash("Copied"); },
          function () { flash(legacyCopy(payload) ? "Copied" : "Copy unavailable"); }
        );
      } else {
        flash(legacyCopy(payload) ? "Copied" : "Copy unavailable");
      }
    });
  }

  /* ------------------------------------------------------ asymmetry render */

  /* the legacy score, label and sub-score readouts are no longer rendered */

  function renderAsymScreen(d, situation, basis, language) {
    var copy = firstScreenCopy(situation, String(d.mode || "normal"), language);
    var lines = list(copy.lines);
    if (basis && list(copy.lines_with_basis).length > 0) { lines = list(copy.lines_with_basis); }
    var panel = $("asym-first-screen");
    if (panel) { panel.setAttribute("data-situation", situation); }
    setText("asym-screen-title", copy.title);

    var profile = obj(d.evidence_profile);
    var positive = obj(d.positive);
    var negative = obj(d.negative);
    var prefix = language === "en" ? "positive: " : "正向：";
    var suffix = language === "en" ? "  negative: " : "  负向：";
    setText(
      "asym-screen-fact",
      prefix + first(positive.description, positive.text, profile.positive_class, DASH)
        + suffix + first(negative.description, negative.text, profile.negative_class, DASH)
    );

    var reading = obj(d.user_interpretation);
    var quotes = [];
    if (reading.positive_reading) { quotes.push("\u300c" + reading.positive_reading + "\u300d"); }
    if (reading.negative_reading) { quotes.push("\u300c" + reading.negative_reading + "\u300d"); }
    renderQuotes("asym-screen-quotes", quotes);

    var positiveQuality = sideQuality(positive, profile.positive_class, "positive", language);
    var negativeQuality = sideQuality(negative, profile.negative_class, "negative", language);
    var sideLabels = obj(catalogueObj("pair_quality_labels")[language]);
    setText("asym-quality-side-positive", sideLabels.positive);
    setText("asym-quality-side-negative", sideLabels.negative);
    setHidden("asym-screen-quality-row", !positiveQuality && !negativeQuality);
    setText("asym-screen-quality-positive", positiveQuality || DASH);
    setText("asym-screen-quality-negative", negativeQuality || DASH);

    setText("asym-screen-reality", copy.reality);
    renderScreenLines("asym-screen-lines", lines);
  }

  function renderAsymmetry(data) {
    var report = $("asym-results");
    if (!report) { return; }
    var d = obj(data);
    var v = obj(d.verdict);
    var profile = obj(d.evidence_profile);
    var treatment = obj(d.ned_treatment);
    var reading = obj(d.user_interpretation);
    var language = languageOf(d);
    var situation = situationFor(v.code, profile.comparison_reason);
    var basis = Boolean(reading.reading_present);

    report.hidden = false;
    report.classList.remove("is-loading");
    report.setAttribute("data-severity", severityOf(v.severity));
    report.setAttribute("data-situation", situation);

    renderAsymScreen(d, situation, basis, language);

    // 1. Evidence Profile: the clues, and the two pairwise readings.
    var gap = function (value) { return value === null || value === undefined ? DASH : num(value, 3); };
    texts([
      ["asym-profile-comparable", profile.comparable ? "yes" : "NO"],
      ["asym-profile-reason", profile.comparison_reason === "" ? DASH : profile.comparison_reason],
      ["asym-profile-raw-gap", gap(profile.raw_strength_gap)],
      ["asym-profile-information-gap", gap(profile.information_gap)]
    ]);
    renderProfileRows(d, profile);

    // 2. NED Treatment: policy only.
    var pct = function (value) { return value === null || value === undefined ? DASH : num(value, 1) + "%"; };
    texts([
      ["asym-treatment-mode", treatment.mode],
      ["asym-treatment-discount", pct(treatment.positive_discount)],
      ["asym-treatment-priors", "positive x" + num(treatment.prior_positive, 2) + "  negative x" + num(treatment.prior_negative, 2)],
      ["asym-treatment-positive", pct(treatment.positive_treated_weight)],
      ["asym-treatment-negative", pct(treatment.negative_treated_weight)],
      ["asym-treatment-amplification", pct(treatment.negative_amplification)],
      ["asym-treatment-gap", gap(treatment.treatment_gap)]
    ]);

    // 3. Your Reading: the only second-person layer.
    var messages = obj(CATALOG.user_reading);
    var message = obj(messages[reading.status]);
    setText("asym-reading-status", language === "en" ? message.en : message.zh);
    var basisHost = $("asym-reading-basis");
    if (basisHost) {
      clear(basisHost);
      list(reading.basis).forEach(function (code) {
        basisHost.appendChild(el("span", "chip mono", txt(code)));
      });
    }
    var detail = [];
    if (reading.positive_reading) { detail.push("positive: " + reading.positive_reading); }
    if (reading.negative_reading) { detail.push("negative: " + reading.negative_reading); }
    setText("asym-reading-detail", detail.length ? detail.join("  \u00b7  ") : DASH);
    setText("asym-reading-positive-basis", reading.positive_self_discount_present ? "yes" : "no");
    setText("asym-reading-negative-basis", reading.negative_self_conclusion_present ? "yes" : "no");

    texts([
      ["asym-reality-text", d.reality_check],
      ["asym-verdict-severity", v.severity], ["asym-disclaimer", d.disclaimer]
    ]);
    var shownAsymVerdict = displayVerdictText(v.code, v.text, situation, basis, language);
    setText("asym-verdict-text", shownAsymVerdict);
    setRaw("asym-verdict-emoji", displayVerdictEmoji(v.emoji, situation, shownAsymVerdict));
    return report;
  }

  function renderProfileRows(d, profile) {
    var host = $("asym-profile-rows");
    if (!host) { return; }
    clear(host);
    [["positive", obj(d.positive), profile.positive_class, profile.positive_raw_strength, profile.positive_information],
     ["negative", obj(d.negative), profile.negative_class, profile.negative_raw_strength, profile.negative_information]
    ].forEach(function (row) {
      var tr = el("tr");
      tr.appendChild(el("td", "", row[0]));
      tr.appendChild(el("td", "mono", txt(row[2] || DASH)));
      tr.appendChild(el("td", "num", row[3] === null || row[3] === undefined ? DASH : num(row[3], 0)));
      tr.appendChild(el("td", "num", row[4] === null || row[4] === undefined ? DASH : num(row[4], 0)));
      host.appendChild(tr);
    });
  }

  /* the legacy sub-score readout is no longer rendered */

  function runAsymmetry() {
    var button = $("asym-submit");
    if (!button) { return; }
    var posEl = $("asym-positive");
    var negEl = $("asym-negative");
    var report = $("asym-results");
    var positive = posEl ? (posEl.value || "").trim() : "";
    var negative = negEl ? (negEl.value || "").trim() : "";
    setStatus("asym-status", "", null);
    if (!positive && !negative) {
      setStatus("asym-status", "Provide at least one of the two evidence descriptions.", "is-error");
      return;
    }
    var body = { mode: currentMode() };
    if (positive) { body.positive_text = positive; }
    if (negative) { body.negative_text = negative; }

    button.disabled = true;
    setStatus("asym-status", "Comparing evidence...", "is-busy");
    if (report) { report.hidden = false; report.classList.add("is-loading"); }

    postJson("/api/asymmetry", body)
      .then(function (data) {
        state.asymmetry = data;
        renderAsymmetry(data);
        setStatus("asym-status", "Comparison complete.", null);
      })
      .catch(function (err) {
        if (report) {
          report.classList.remove("is-loading");
          if (!state.asymmetry) { report.hidden = true; }
        }
        setStatus("asym-status", err && err.message ? err.message : "Comparison failed.", "is-error");
      })
      .then(function () { button.disabled = false; });
  }

  /* ---------------------------------------------------------------- lab */

  function pad2(v) {
    if (!isNum(v)) { return "00"; }
    var s = String(Math.abs(Math.round(Number(v))));
    return s.length >= 2 ? s : "0" + s;
  }

  function prob(p) {
    var n = Number(p);
    return isFinite(n) ? "p=" + (n > 1 ? n / 100 : n).toFixed(2) : "p=n/a";
  }

  function fnbpTrace(d) {
    var rows = list(d.per_notification);
    var lines = rows.length === 0 ? ["no trace collected"] : [];
    rows.forEach(function (rawItem, index) {
      var r = obj(rawItem);
      lines.push("[" + pad2(r.index === undefined ? index + 1 : r.index) + "] predicted=" + txt(r.predicted_sender) +
        " " + prob(r.predicted_probability) + " actual=" + txt(r.actual_sender) + " -> " + (r.hit ? "HIT" : "MISPREDICT"));
      if (r.pipeline_flushed) { lines.push("PIPELINE FLUSHED"); }
    });
    lines.push("");
    lines.push("expected=" + txt(d.expected_sender) + " notifications=" + int(d.notifications) +
      " hits=" + int(d.prediction_hits) + " misses=" + int(d.prediction_misses));
    return lines.join("\n");
  }

  function renderFnbp(data) {
    var report = $("fnbp-results");
    if (!report) { return; }
    var d = obj(data);
    var v = obj(d.verdict);
    var log = $("fnbp-log");
    report.hidden = false;
    report.classList.remove("is-loading");
    report.setAttribute("data-severity", severityOf(v.severity));
    if (log) { log.textContent = fnbpTrace(d); }
    texts([
      ["fnbp-hits", d.prediction_hits === undefined ? DASH : int(d.prediction_hits)],
      ["fnbp-misses", d.prediction_misses === undefined ? DASH : int(d.prediction_misses)],
      ["fnbp-flushes", d.pipeline_flushes === undefined ? DASH : int(d.pipeline_flushes)],
      ["fnbp-wasted", d.wasted_cycles === undefined ? DASH : int(d.wasted_cycles)],
      ["fnbp-verdict-text", v.text], ["fnbp-verdict-severity", v.severity], ["fnbp-codename-note", d.codename_note]
    ]);
    setNum("fnbp-rate", d.mispredict_rate, 1, "%");
    setRaw("fnbp-verdict-emoji", typeof v.emoji === "string" ? v.emoji : "");
    renderFnbpPersonality(d.prediction_misses);
    return report;
  }

  function parseSenders(value) {
    return String(value || "").split(/[,，;；\n]+/).map(function (part) {
      return part.trim();
    }).filter(function (part) { return part.length > 0; });
  }

  function runFnbp() {
    var button = $("fnbp-submit");
    if (!button) { return; }
    var expectedField = $("fnbp-expected");
    var actualField = $("fnbp-actual");
    var countField = $("fnbp-count");
    var seedField = $("fnbp-seed");
    var report = $("fnbp-results");
    var expected = (expectedField && expectedField.value || "").trim();
    var senders = parseSenders(actualField && actualField.value);
    setStatus("fnbp-status", "", null);
    if (!expected) {
      setStatus("fnbp-status", "Enter the expected sender first.", "is-error");
      return;
    }
    if (senders.length === 0) {
      setStatus("fnbp-status", "Enter at least one actual sender (comma separated).", "is-error");
      return;
    }
    var count = parseInt((countField && countField.value) || "5", 10);
    if (!isFinite(count) || count < 1) { count = 5; }
    if (count > 64) { count = 64; }
    var seed = parseInt((seedField && seedField.value) || "0", 10);
    if (!isFinite(seed)) { seed = 0; }

    button.disabled = true;
    setStatus("fnbp-status", "Running branch predictor...", "is-busy");
    if (report) { report.hidden = false; report.classList.add("is-loading"); }

    postJson("/api/fnbp", {
      expected_sender: expected,
      actual_senders: senders,
      notifications: count,
      seed: seed
    })
      .then(function (data) {
        state.fnbp = data;
        renderFnbp(data);
        setStatus("fnbp-status", "Pipeline trace complete.", null);
      })
      .catch(function (err) {
        if (report) {
          report.classList.remove("is-loading");
          if (!state.fnbp) { report.hidden = true; }
        }
        setStatus("fnbp-status", err && err.message ? err.message : "Branch predictor failed.", "is-error");
      })
      .then(function () { button.disabled = false; });
  }

  /* ------------------------------------------------------------------ init */

  function onKeydown(event) {
    // Ctrl/Cmd+Enter runs the analyzer. Plain Enter is deliberately ignored in the
    // asymmetry fields: they are multi-line and no form element exists, so Enter
    // can never submit anything by accident.
    if (event.target && event.target.id === "analyze-input" && event.key === "Enter" &&
        (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      runAnalyze();
    }
  }

  function init() {
    initTabs();
    initMode();
    initExamples();
    initCopy();
    var analyzeBtn = $("analyze-submit");
    var asymBtn = $("asym-submit");
    var fnbpBtn = $("fnbp-submit");
    if (analyzeBtn) { analyzeBtn.addEventListener("click", runAnalyze); }
    if (asymBtn) { asymBtn.addEventListener("click", runAsymmetry); }
    if (fnbpBtn) { fnbpBtn.addEventListener("click", runFnbp); }
    document.addEventListener("keydown", onKeydown);
    refreshHealth();

    // Single debug hook; nothing else is attached to window.
    window.NED = {
      state: state,
      catalog: CATALOG,
      escapeHtml: escapeHtml,
      situationFor: situationFor,
      displaySituation: displaySituation,
      firstScreenCopy: firstScreenCopy,
      screenFact: screenFact,
      repairDisplayText: repairDisplayText,
      qualityFromValue: qualityFromValue,
      displayVerdictText: displayVerdictText,
      displayVerdictEmoji: displayVerdictEmoji,
      renderAnalyze: renderAnalyze,
      renderAsymmetry: renderAsymmetry,
      renderFnbp: renderFnbp,
      refreshHealth: refreshHealth
    };
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
}());
