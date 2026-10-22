"use strict";

let currentVerseData = [];
let currentTikkunHtml = { plain: "", pointed: "" };
let tikkunError = ""; // why the scroll layout couldn't be fetched, if it couldn't
let currentClozeOutput = ""; // the full cloze markup, for Copy (the box only holds what's in view)
let currentDiagrams = []; // [{ref, diagram}], for saving the diagram view
let currentShorashim = null; // ankipasuk.shorashim.passage for the loaded pesuqim, once it's in
let currentPhrases = null; // ankipasuk.phrases.passage, likewise
let cachedBooks = null; // {"Tora": [...], "Nevi'im": [...], "Megillot": [...]}
let cachedBookLabels = null; // {"Genesis": "Bereshit · בראשית", ...}

function api() {
    return window.pywebview.api;
}

function showToast(message, isError) {
    const el = document.getElementById("toast");
    el.textContent = message;
    el.className = "toast" + (isError ? " error" : "");
    el.hidden = false;
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => { el.hidden = true; }, 4000);
}

// labels, if given, is shown instead of values (same order) -- e.g. a
// parasha's name as AnkiPasuk writes it, while its value stays Sefaria's.
function setOptions(select, values, keepSelection, labels) {
    const prev = select.value;
    select.innerHTML = "";
    for (const [i, v] of values.entries()) {
        const opt = document.createElement("option");
        opt.value = String(v);
        opt.textContent = String(labels ? labels[i] : v);
        select.appendChild(opt);
    }
    if (keepSelection && values.map(String).includes(prev)) {
        select.value = prev;
    }
}

function setBookOptions(select, booksByCategory, keepSelection, labels) {
    const prev = select.value;
    select.innerHTML = "";
    for (const [category, books] of Object.entries(booksByCategory)) {
        const group = document.createElement("optgroup");
        group.label = category;
        for (const b of books) {
            const opt = document.createElement("option");
            opt.value = b;
            opt.textContent = (labels && labels[b]) || b;
            group.appendChild(opt);
        }
        select.appendChild(group);
    }
    if (keepSelection && Array.from(select.options).some((o) => o.value === prev)) {
        select.value = prev;
    }
}

// =============================================================
//  Range rows -- each is an independently configurable
//  picker for book, mode, and chapter/verse or parasha/'aliyya. Multiple rows can
//  be fetched together and their verses concatenate in the order
//  they're listed (see doFetchAll).
// =============================================================
const RANGE_ROW_TEMPLATE = `
  <div class="range-head">
    <button class="range-summary" type="button" title="Change this range">…</button>
    <button class="range-remove" type="button" title="Remove this range">✕</button>
  </div>
  <div class="range-editor">
    <div class="field-row">
      <select class="range-mode">
        <option value="cv">Chapter / verse</option>
        <option value="pa">Parasha / 'aliyya</option>
        <option value="hf">Haftara</option>
      </select>
      <select class="range-book grow"></select>
    </div>
    <div class="field-row range-hf-controls" hidden><select class="range-haftara grow"></select></div>
    <div class="field-row range-cv-controls">
      From <select class="range-start-ch"></select>:<select class="range-start-vs"></select>
      to <select class="range-end-ch"></select>:<select class="range-end-vs"></select>
    </div>
    <div class="range-pa-controls" hidden>
      <div class="field-row">
        From <select class="range-parasha grow"></select>
        'aliyya <select class="range-aliyah"></select>
      </div>
      <div class="field-row">
        to <select class="range-parasha-end grow"></select>
        'aliyya <select class="range-aliyah-end"></select>
      </div>
    </div>
  </div>
`;

// The range in one line: "Bereshit 1:1–2:3", "Noaḥ · 'aliyya 2",
// "Noaḥ · 'aliyyot 2–5", "Noaḥ 6 – Lekh Lekha 2", or the haftara's own label.
function rangeSummary(row) {
    const q = (cls) => row.querySelector("." + cls);
    const mode = q("range-mode").value;
    const optionText = (sel) => (sel.selectedOptions[0] || {}).textContent || "";
    if (mode === "hf") return optionText(q("range-haftara")) || "Haftara";
    const book = optionText(q("range-book")).split(" · ")[0];
    if (mode === "pa") {
        const [p1, p2] = [optionText(q("range-parasha")), optionText(q("range-parasha-end"))];
        const [a1, a2] = [q("range-aliyah").value, q("range-aliyah-end").value];
        if (p1 !== p2) return `${p1} ${a1} – ${p2} ${a2}`;
        return a1 === a2 ? `${p1} · 'aliyya ${a1}` : `${p1} · 'aliyyot ${a1}–${a2}`;
    }
    const [sc, sv, ec, ev] = ["range-start-ch", "range-start-vs", "range-end-ch", "range-end-vs"].map((c) => q(c).value);
    if (sc === ec) return sv === ev ? `${book} ${sc}:${sv}` : `${book} ${sc}:${sv}–${ev}`;
    return `${book} ${sc}:${sv}–${ec}:${ev}`;
}

function setRangeOpen(row, open) {
    row.classList.toggle("open", open);
    row.querySelector(".range-editor").hidden = !open;
}

// After any change to a range: its summary, then the preview (debounced).
function rangeChanged(row) {
    row.querySelector(".range-summary").textContent = rangeSummary(row);
    scheduleRefresh(true);
}

async function onRangeModeChange(row) {
    const mode = row.querySelector(".range-mode").value;
    const isCV = mode === "cv";
    row.querySelector(".range-cv-controls").hidden = !isCV;
    row.querySelector(".range-pa-controls").hidden = mode !== "pa";
    row.querySelector(".range-hf-controls").hidden = mode !== "hf";
    // A haftara names its own books, so the book picker has nothing to do.
    row.querySelector(".range-book").hidden = mode === "hf";
    if (mode === "hf") {
        await fillHaftaraOptions(row.querySelector(".range-haftara"));
        return;
    }

    // Parasha/'aliyya mode only exists for the Tora -- restrict the book list
    // to the Tora so an invalid (book, mode) combination can't be selected at
    // all, rather than only failing later when fetched.
    const books = isCV ? cachedBooks : { Tora: cachedBooks.Tora };
    setBookOptions(row.querySelector(".range-book"), books, true, cachedBookLabels);

    await onRangeBookChange(row);
}

// The haftarot, grouped as get_haftarot returns them (each parasha's, then
// the special Shabbatot). Loaded once, the first time it's needed.
let cachedHaftarot = null;

async function fillHaftaraOptions(select) {
    if (!cachedHaftarot) cachedHaftarot = (await api().get_haftarot()).groups;
    const prev = select.value;
    select.innerHTML = "";
    for (const group of cachedHaftarot) {
        const optgroup = document.createElement("optgroup");
        optgroup.label = group.label;
        for (const item of group.items) {
            const opt = document.createElement("option");
            opt.value = item.slug;
            opt.textContent = item.label;
            optgroup.appendChild(opt);
        }
        select.appendChild(optgroup);
    }
    if (prev) select.value = prev;
}

async function onRangeBookChange(row) {
    const isCV = row.querySelector(".range-mode").value === "cv";
    if (isCV) {
        await refreshRangeChapterVerseDropdowns(row);
    } else {
        await refreshRangeParashaDropdown(row);
    }
}

// The numbers from..to, inclusive.
function numbersFrom(from, to) {
    return Array.from({ length: Math.max(0, to - from + 1) }, (_, i) => from + i);
}

async function refreshRangeChapterVerseDropdowns(row) {
    const book = row.querySelector(".range-book").value;
    const result = await api().get_chapter_count(book);
    if (!result.ok) {
        showToast("Could not load " + book + ": " + result.error, true);
        return;
    }
    row.dataset.chapterCount = result.count;
    setOptions(row.querySelector(".range-start-ch"), numbersFrom(1, result.count), true);
    await refreshRangeVerseDropdown(row, "range-start-ch", "range-start-vs", 1);
    await constrainRangeEnd(row);
}

async function refreshRangeVerseDropdown(row, chClass, vsClass, minVerse) {
    const book = row.querySelector(".range-book").value;
    const chapter = parseInt(row.querySelector("." + chClass).value, 10) || 1;
    const result = await api().get_verse_count(book, chapter);
    if (!result.ok) {
        showToast("Could not load verse count: " + result.error, true);
        return;
    }
    setOptions(row.querySelector("." + vsClass), numbersFrom(minVerse, result.count), true);
}

// A range can't end before it starts: the end pickers only offer
// chapters and verses from the start on, and an end the start has moved
// past is moved up to the start.
async function constrainRangeEnd(row) {
    const startCh = parseInt(row.querySelector(".range-start-ch").value, 10) || 1;
    const startVs = parseInt(row.querySelector(".range-start-vs").value, 10) || 1;
    setOptions(row.querySelector(".range-end-ch"), numbersFrom(startCh, parseInt(row.dataset.chapterCount, 10)), true);
    const endCh = parseInt(row.querySelector(".range-end-ch").value, 10);
    await refreshRangeVerseDropdown(row, "range-end-ch", "range-end-vs", endCh === startCh ? startVs : 1);
}

async function refreshRangeParashaDropdown(row) {
    const book = row.querySelector(".range-book").value;
    const parashaSelect = row.querySelector(".range-parasha");
    parashaSelect.innerHTML = "<option>Loading...</option>";
    const result = await api().get_parashot(book);
    if (!result.ok) {
        showToast("Could not load parashiyyot: " + result.error, true);
        parashaSelect.innerHTML = "";
        return;
    }
    row._parashot = result;  // for the end pickers (constrainParashaEnd)
    setOptions(parashaSelect, result.names, false, result.labels);
    await refreshRangeAliyahDropdown(row);
}

// The 'aliyyot of the parasha chosen in ``parashaClass``, from
// ``minAliyah`` on, into ``aliyahClass``.
async function fillAliyot(row, parashaClass, aliyahClass, minAliyah) {
    const book = row.querySelector(".range-book").value;
    const parasha = row.querySelector("." + parashaClass).value;
    if (!parasha) return;
    const result = await api().get_aliyah_count(book, parasha);
    if (!result.ok) {
        showToast("Could not load 'aliyyot: " + result.error, true);
        return;
    }
    setOptions(row.querySelector("." + aliyahClass), numbersFrom(minAliyah, result.count), true);
}

async function refreshRangeAliyahDropdown(row) {
    await fillAliyot(row, "range-parasha", "range-aliyah", 1);
    await constrainParashaEnd(row);
}

// As with chapters and verses, the end can't come before the start: the
// end parasha is the start's or a later one, and in the same parasha the
// end 'aliyya is the start's or later. A new range ends where it starts,
// one 'aliyya.
async function constrainParashaEnd(row) {
    const parashot = row._parashot;
    if (!parashot) return;
    const start = row.querySelector(".range-parasha").value;
    const from = Math.max(0, parashot.names.indexOf(start));
    const endSelect = row.querySelector(".range-parasha-end");
    const keep = parashot.names.slice(from).includes(endSelect.value);
    setOptions(endSelect, parashot.names.slice(from), keep, parashot.labels.slice(from));
    if (!keep) endSelect.value = start;
    const sameParasha = endSelect.value === start;
    const startAliyah = parseInt(row.querySelector(".range-aliyah").value, 10) || 1;
    await fillAliyot(row, "range-parasha-end", "range-aliyah-end", sameParasha ? startAliyah : 1);
}

async function addRangeRow() {
    const container = document.getElementById("ranges-container");
    for (const other of container.querySelectorAll(".range-row")) setRangeOpen(other, false);
    const row = document.createElement("div");
    row.className = "range-row range-card";
    row.innerHTML = RANGE_ROW_TEMPLATE;
    container.appendChild(row);
    setRangeOpen(row, true);

    // Each handler updates the dropdowns it affects, then the summary
    // and the preview.
    const on = (cls, handler) => row.querySelector("." + cls).addEventListener("change", async () => {
        await handler();
        rangeChanged(row);
    });
    on("range-mode", () => onRangeModeChange(row));
    on("range-book", () => onRangeBookChange(row));
    on("range-start-ch", async () => {
        await refreshRangeVerseDropdown(row, "range-start-ch", "range-start-vs", 1);
        await constrainRangeEnd(row);
    });
    on("range-start-vs", () => constrainRangeEnd(row));
    on("range-end-ch", () => constrainRangeEnd(row));
    on("range-end-vs", async () => {});
    on("range-parasha", () => refreshRangeAliyahDropdown(row));
    on("range-aliyah", () => constrainParashaEnd(row));
    on("range-parasha-end", () => constrainParashaEnd(row));
    on("range-aliyah-end", async () => {});
    on("range-haftara", async () => {});
    row.querySelector(".range-summary").addEventListener("click", () => {
        setRangeOpen(row, !row.classList.contains("open"));
    });
    row.querySelector(".range-remove").addEventListener("click", () => {
        if (document.querySelectorAll(".range-row").length <= 1) {
            showToast("At least one range is required.", true);
            return;
        }
        row.remove();
        scheduleRefresh(true);
    });

    await onRangeModeChange(row);
    rangeChanged(row);
    return row;
}

// =============================================================
//  Fetching verses (every range row, concatenated in order)
// =============================================================
// The Text view: one line per pasuq, each word clickable to colour its
// root once the roots are in (filled in as it scrolls, like the others).
function renderTextBox() {
    const plain = document.querySelector("#text-kind .active").dataset.kind === "plain";
    const textBox = document.getElementById("text-box");
    const words = currentShorashim && currentShorashim.verses.length === currentVerseData.length
        ? currentShorashim.verses : null;
    lazyFill(textBox, currentVerseData.map((_item, i) => i), (i) => {
        const line = words ? rootWordsHtml(words[i], plain)
            : diagramEscape(plain ? currentVerseData[i].plain : currentVerseData[i].pointed);
        return `<div class="tv-line">${line}</div>`;
    }, (lines) => {
        for (const line of lines) rootColours.paintAll(line);
        phraseMarks.paintLines(lines);
    }, textBox, false);
    renderRootsList();
}

// The passage's roots: the coloured ones first, in the order they were
// coloured, then the rest, the most used or the key words first;
// particles only if asked (or coloured).
function renderRootsList() {
    const list = document.getElementById("roots-list");
    const groups = currentShorashim ? currentShorashim.groups : {};
    const withParticles = document.getElementById("roots-particles").checked;
    const sort = document.querySelector("#roots-sort .active").dataset.sort;
    const coloured = [...rootColours.colours.keys()].filter((g) => g in groups);
    const rest = Object.keys(groups)
        .filter((g) => !rootColours.colours.has(g) && (withParticles || groups[g].kind !== "particle"))
        .sort((a, b) => ROOT_ORDERS[sort](groups[a], groups[b]));
    const shown = [...coloured, ...rest];
    list.innerHTML = shown.map((g, i) => {
        const info = groups[g];
        const words = info.words.map(([w, gloss, meaning]) => `${w} ${glossText(gloss, meaning)}`).join(" · ");
        const kind = info.kind === "name" ? ` <span class="root-kind">${nameKind(info)}</span>` : "";
        const ratio = sort === "key" && info.total
            ? `<span class="root-ratio${info.keyness > 0 ? "" : " under"}">${ratioText(info.ratio)}</span>` : "";
        const last = i === coloured.length - 1 && rest.length ? ' class="last-coloured"' : "";
        const colour = rootColours.colours.get(g);
        const spark = colour === undefined ? "" : sparklineHtml(rootPlaces(g), currentVerseData.length,
            ROOT_PALETTE[colour], `In ${plural(info.verses.length, "pasuq", "pesuqim")} of ${currentVerseData.length}: `
            + "click to go to the nearest");
        return `<li data-root="${g}"${last} title="${diagramEscape(`${words}\n${rootCountsText(info)}`)}">`
            + `<span class="root-label" data-g="${g}">${rootLabelHtml(info)}</span>`
            + `<span class="root-gloss">${glossHtml(info.gloss, info.meaning)}${kind}</span>`
            + `<span class="root-count">${info.count}</span>${ratio}${spark}</li>`;
    }).join("");
    rootColours.paintAll(list);
    document.getElementById("roots-count").textContent = shown.length ? `(${shown.length})` : "";
}

// Where a root's words are: pasuq index -> how many.
function rootPlaces(g) {
    const places = new Map();
    (currentShorashim ? currentShorashim.verses : []).forEach((words, v) => {
        const n = words.filter((w) => String(w[2]) === g).length;  // (the list's keys are strings)
        if (n) places.set(v, n);
    });
    return places;
}

// Colouring a root colours its words in the text, and brings its entry in
// the list up to the top, scrolling to it there.
const rootColours = new RootColours((changed) => {
    for (const g of changed) rootColours.paint(document.getElementById("text-box"), g);
    renderRootsList();
    const list = document.getElementById("roots-list");
    const item = changed.length === 1 && rootColours.colours.has(changed[0])
        ? list.querySelector(`li[data-root="${changed[0]}"]`) : null;
    if (item) {
        const l = list.getBoundingClientRect(), r = item.getBoundingClientRect();
        if (r.top < l.top) list.scrollTop -= l.top - r.top;
        else if (r.bottom > l.bottom) list.scrollTop += r.bottom - l.bottom;
    }
});

async function loadShorashim() {
    const result = await api().get_shorashim();
    currentShorashim = result.ok ? result : null;
    if (!result.ok) console.warn("No shorashim:", result.error);
    renderTextBox();
    loadPhrases();
}

// =============================================================
//  Phrases: the passage's refrains, echoes and idioms, and its formulas
//  (ankipasuk.phrases), beside the text in place of the shorashim. A
//  picked phrase is underlined in the text, in its own colour.
// =============================================================
// Also when the settings change.
async function loadPhrases() {
    const verses = currentVerseData;
    if (phraseViewerClose) phraseViewerClose();  // its phrase is gone
    currentPhrases = null;
    phraseAt.clear();
    renderPhrasesList();  // "Finding phrases…"
    const result = await api().get_phrases();
    if (verses !== currentVerseData) return;  // other pesuqim were loaded meanwhile
    currentPhrases = result.ok ? result : { error: result.error };
    phraseMarks.use(result.ok ? result.phrases : []);
    phraseMarks.paintLines(document.querySelectorAll("#text-box .tv-line"));
    renderPhrasesList();
}

let phraseKind = "refrain"; // the section shown

function renderPhrasesList() {
    const els = { tabs: document.getElementById("ph-tabs"), about: document.getElementById("ph-about"),
                  list: document.getElementById("phrases-list") };
    if (!currentPhrases || currentPhrases.error) {
        els.tabs.innerHTML = els.list.innerHTML = "";
        els.about.textContent = !currentPhrases ? (currentVerseData.length ? "Finding phrases…" : "")
            : `No phrases: ${currentPhrases.error}`;
        return;
    }
    renderPhrasePane(currentPhrases, phraseKind, els, [...phraseMarks.colours.keys()]);
    paintPhraseList();
}

// A picked phrase's row, marked in its colour, with where it is in the
// passage (a sparkline); with more than one occurrence here, arrows to go
// from one to the next in the text.
function paintPhraseList() {
    for (const el of document.querySelectorAll("#phrases-list li.ph")) {
        const id = Number(el.dataset.id);
        const colour = phraseMarks.colours.get(id);
        el.classList.toggle("picked", colour !== undefined);
        el.style.borderRightColor = colour === undefined ? "" : ROOT_PALETTE[colour];
        const spans = currentPhrases.phrases[id].spans;
        const old = el.querySelector(".spark");
        if (old) old.remove();
        if (colour !== undefined) {
            const places = new Map();
            for (const [v] of spans) places.set(v, (places.get(v) || 0) + 1);
            el.insertAdjacentHTML("beforeend", sparklineHtml(places, currentVerseData.length, ROOT_PALETTE[colour],
                `In ${plural(places.size, "pasuq", "pesuqim")} of ${currentVerseData.length}: click to go to the nearest`));
        }
        const n = spans.length;
        let nav = el.querySelector(".ph-jump");
        if (colour === undefined || n < 2) {
            if (nav) nav.remove();
            continue;
        }
        if (!nav) {
            nav = document.createElement("span");
            nav.className = "ph-jump";
            nav.innerHTML = '<button type="button" data-jump="-1" title="The one before, in the text">‹</button>'
                + '<span class="ph-pos"></span><button type="button" data-jump="1" title="The next, in the text">›</button>';
            el.querySelector(".ph-meta").append(nav);
        }
        nav.querySelector(".ph-pos").textContent = `${(phraseAt.get(id) || 0) + 1}/${n}`;
    }
}

// The occurrence of each picked phrase last shown: an index into its spans.
const phraseAt = new Map();

// Show a phrase's occurrence ``k`` in the text (from the last, round to
// the first), and flash it.
function jumpToPhrase(p, k) {
    const n = p.spans.length;
    if (!n) return;
    k = ((k % n) + n) % n;
    phraseAt.set(p.id, k);
    paintPhraseList();
    const [v, w] = p.spans[k];
    showInText(v, w, (box) => flashSpan(box, p.spans[k]));
}

// Bring word ``w`` of pasuq ``v`` into view in the text, if it isn't, then
// call ``then(box)``. Lines are filled as they near the view and move
// what's below them: placed again once they are.
function showInText(v, w, then) {
    const box = document.getElementById("text-box");
    const place = () => {
        const line = box.querySelector(`[data-i="${v}"]`);
        if (!line) return;
        const target = (w === undefined ? null : line.querySelector(`[data-k="${w}"]`)) || line;
        const b = box.getBoundingClientRect(), r = target.getBoundingClientRect();
        if (r.top < b.top + 4 || r.bottom > b.bottom - 4) box.scrollTop += r.top - b.top - box.clientHeight / 3;
    };
    place();
    setTimeout(place, 60);
    setTimeout(() => {
        place();
        then(box);
    }, 160);
}

// Briefly highlight elements of the text (after any flashed before).
function flashElements(box, els) {
    for (const el of box.querySelectorAll(".ph-flash")) el.classList.remove("ph-flash");
    void box.offsetWidth;  // so the same words flash again
    for (const el of els) el.classList.add("ph-flash");
}

// The first occurrence of a phrase in view, if one is.
function phraseInView(p) {
    const box = document.getElementById("text-box");
    const b = box.getBoundingClientRect();
    return p.spans.findIndex(([v]) => {
        const line = box.querySelector(`[data-i="${v}"]`);
        const r = line ? line.getBoundingClientRect() : null;
        return r && r.bottom > b.top && r.top < b.bottom;
    });
}

// Briefly highlight words ``[pasuq, word]`` to ``[pasuq2, word2]``, and
// what's between them.
function flashSpan(box, [v, k, v2, k2]) {
    const els = [];
    for (let i = v; i <= v2; i++) {
        const line = box.querySelector(`.tv-line[data-i="${i}"]`);
        if (!line) continue;
        const from = i === v ? k : -1, to = i === v2 ? k2 : Infinity;
        for (const el of line.querySelectorAll("[data-k], [data-s]")) {
            const x = Number(el.dataset.k ?? el.dataset.s);  // a separator: after its word
            if (x >= from && (el.dataset.k !== undefined ? x <= to : x < to)) els.push(el);
        }
    }
    flashElements(box, els);
}

const phraseCalls = {
    verses: (id) => api().get_phrase_verses(id),
    context: (id, place) => api().get_phrase_context(id, place),
};

const phraseMarks = new PhraseMarks((words) => {
    phraseMarks.paint(document.getElementById("text-box"), words);
    renderPhrasesList();  // the picked ones first
});

// =============================================================
//  Settings: the phrase tests' thresholds (api.get_settings), in a
//  dialog. A control is [data-setting]: a number (shown times its
//  data-scale) or a choice of chances or shares (SETTING_CHOICES).
// =============================================================
const SETTING_CHOICES = {
    chance: [1e-2, 1e-3, 1e-4, 1e-5, 1e-6].map((v) => [v, `1 in ${Math.round(1 / v).toLocaleString("en")}`]),
    share: [[0.25, "a quarter"], [1 / 3, "a third"], [0.5, "half"], [2 / 3, "two thirds"], [0.75, "three quarters"]],
};
let settingsDefaults = {};
let settingsOpened = ""; // the values when the dialog opened, to tell whether they changed

const sameSetting = (a, b) => Math.abs(a - b) <= 1e-9 * Math.max(Math.abs(a), Math.abs(b));

function settingControls() {
    return [...document.querySelectorAll("#settings-form [data-setting]")];
}

function settingValue(el) {
    const value = Number(el.value) / (el.tagName === "SELECT" ? 1 : Number(el.dataset.scale) || 1);
    return el.value !== "" && Number.isFinite(value) ? value : settingsDefaults[el.dataset.setting];
}

function settingText(el, value) {
    if (el.tagName === "SELECT") {
        const choice = SETTING_CHOICES[el.dataset.choices].find(([v]) => sameSetting(v, value));
        return choice ? choice[1] : String(value);
    }
    return String(Math.round(value * (Number(el.dataset.scale) || 1) * 100) / 100);
}

// A control not at its default is marked, and its tooltip gives the default.
function markSetting(el) {
    const fallback = settingsDefaults[el.dataset.setting];
    el.classList.toggle("changed", !sameSetting(settingValue(el), fallback));
    el.title = `Default: ${settingText(el, fallback)}`;
}

function showSettings(values) {
    for (const el of settingControls()) {
        const value = values[el.dataset.setting];
        if (el.tagName === "SELECT") {
            const choices = [...SETTING_CHOICES[el.dataset.choices]];
            if (!choices.some(([v]) => sameSetting(v, value))) choices.push([value, String(value)]);  // set by hand
            el.innerHTML = choices.map(([v, text]) => `<option value="${v}">${text}</option>`).join("");
            el.value = String(choices.find(([v]) => sameSetting(v, value))[0]);
        } else {
            el.value = settingText(el, value);
        }
        markSetting(el);
    }
}

function readSettings() {
    return Object.fromEntries(settingControls().map((el) => [el.dataset.setting, settingValue(el)]));
}

async function openSettings() {
    const result = await api().get_settings();
    settingsDefaults = result.defaults.phrases;
    for (const el of settingControls()) {
        const [low, high] = result.limits.phrases[el.dataset.setting];
        if (el.tagName !== "INPUT") continue;
        const scale = Number(el.dataset.scale) || 1;
        Object.assign(el, { min: low * scale, max: high * scale, step: 1, required: true });
    }
    showSettings(result.phrases);
    settingsOpened = JSON.stringify(readSettings());
    document.getElementById("settings-dialog").hidden = false;
    settingControls()[0].focus();
}

function closeSettings() {
    document.getElementById("settings-dialog").hidden = true;
}

// Saved, the phrases are found again with them (and in an open
// statistics window: api.save_settings).
async function saveSettings() {
    const values = readSettings();
    const changed = JSON.stringify(values) !== settingsOpened;
    const result = await api().save_settings({ phrases: values });
    if (!result.ok) return showToast(result.error, true);
    closeSettings();
    if (!changed) return;
    showToast("Phrase settings saved.");
    if (currentVerseData.length) loadPhrases();
}

// The Text and Tikkun views, pointed or letters only as chosen.
function renderVerseBoxes() {
    renderTextBox();
    const tikkunPointed = document.querySelector("#tikkun-kind .active").dataset.kind === "pointed";
    document.getElementById("tikkun-box").innerHTML = (tikkunPointed ? currentTikkunHtml.pointed : currentTikkunHtml.plain)
        || `<p class="muted" dir="ltr">${tikkunError ? diagramEscape(tikkunError) : "The scroll layout is for the Tora only."}</p>`;
    const n = currentVerseData.length;
    document.getElementById("line-count").textContent = n ? `${n} ${n === 1 ? "pasuq" : "pesuqim"} loaded` : "";
    const send = document.getElementById("btn-export-cloze-anki");
    send.textContent = n ? `Send ${n} ${n === 1 ? "pasuq" : "pesuqim"} to Anki` : "Send to Anki";
    send.disabled = !n;
    document.getElementById("preview-empty").hidden = n > 0;
}

// Every range, fetched afresh and concatenated in order. Returns false
// if one failed (whatever came before it stays shown).
async function doFetchAll() {
    // The backend appends, so start from nothing each time.
    await api().clear_ranges();
    currentVerseData = [];
    currentShorashim = null;
    currentPhrases = null;
    phraseMarks.use([]);
    currentTikkunHtml = { plain: "", pointed: "" };
    tikkunError = "";
    for (const row of document.querySelectorAll(".range-row")) {
        const book = row.querySelector(".range-book").value;
        const mode = row.querySelector(".range-mode").value;
        let result;
        let tikkunResult;
        if (mode === "cv") {
            const [startCh, startVs, endCh, endVs] = ["range-start-ch", "range-start-vs", "range-end-ch", "range-end-vs"]
                .map((c) => parseInt(row.querySelector("." + c).value, 10));
            result = await api().fetch_chapter_verse(book, startCh, startVs, endCh, endVs);
            if (result.ok) tikkunResult = await api().fetch_tikkun_chapter_verse(book, startCh, startVs, endCh, endVs);
        } else if (mode === "hf") {
            result = await api().fetch_haftara(row.querySelector(".range-haftara").value);
        } else {
            // From one 'aliyya to another: worked out as chapter and verse,
            // then loaded like any such range.
            const q = (c) => row.querySelector("." + c).value;
            const span = await api().get_parasha_span(
                book, q("range-parasha"), parseInt(q("range-aliyah"), 10),
                q("range-parasha-end"), parseInt(q("range-aliyah-end"), 10));
            if (span.ok) {
                const [startCh, startVs] = span.start;
                const [endCh, endVs] = span.end;
                result = await api().fetch_chapter_verse(book, startCh, startVs, endCh, endVs);
                if (result.ok) tikkunResult = await api().fetch_tikkun_chapter_verse(book, startCh, startVs, endCh, endVs);
            } else {
                result = span;
            }
        }
        if (!result.ok) {
            showToast("Could not load " + rangeSummary(row) + ": " + result.error, true);
            return false;
        }
        currentVerseData = result.verses;
        // Outside the Tora there's no scroll layout; a failure there only
        // loses that view, not the range.
        if (tikkunResult && tikkunResult.ok) {
            currentTikkunHtml = { plain: tikkunResult.plain_html, pointed: tikkunResult.pointed_html };
        } else if (tikkunResult) {
            tikkunError = tikkunResult.error;
        }
        document.getElementById("cache-status").textContent = result.cache_status;
    }
    const deck = document.getElementById("cloze-deck");
    if (!deck.dataset.typed) deck.value = await api().suggest_cloze_deck();
    return true;
}

// The preview follows the settings on its own: a change waits a moment
// for the next (so stepping through verses doesn't fetch each), then
// loads and regenerates. One update at a time -- the backend's verse list
// is shared -- with any change made meanwhile done straight after.
let refreshTimer = null;
let refreshing = false;
let pendingFetch = false;
let pendingRun = false;

function scheduleRefresh(fetch) {
    pendingFetch = pendingFetch || fetch;
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(runRefresh, 350);
}

async function runRefresh() {
    if (refreshing) {
        pendingRun = true;
        return;
    }
    refreshing = true;
    const status = document.getElementById("preview-status");
    try {
        do {
            pendingRun = false;
            const fetch = pendingFetch;
            pendingFetch = false;
            status.textContent = fetch ? "Loading…" : "Updating…";
            if (fetch && !(await doFetchAll())) {
                renderVerseBoxes();
                continue;
            }
            renderVerseBoxes();
            await doGenerate();
            if (fetch) await loadShorashim();
        } while (pendingRun || pendingFetch);
    } finally {
        refreshing = false;
        status.textContent = "";
    }
}

// =============================================================
//  Cloze generation
// =============================================================
async function doGenerate() {
    if (!currentVerseData.length) {
        currentClozeOutput = "";
        currentDiagrams = [];
        document.getElementById("output-box").innerHTML = "";
        document.getElementById("viz-box").innerHTML = "";
        return;
    }
    const maxLeafDisj = parseInt(document.getElementById("max-leaf-disj").value, 10) || 2;
    const resetPerLine = document.getElementById("reset-per-line").checked;
    const result = await api().generate_cloze(maxLeafDisj, resetPerLine);
    if (!result.ok) {
        showToast(result.error, true);
        return;
    }
    currentClozeOutput = result.output;
    currentDiagrams = result.diagrams;
    // One line per pasuq, filled in as it scrolls into view (diagram.js's
    // lazyFill): a whole book's markup as one block of text made every
    // layout of the page take seconds in WebKitGTK.
    const outputBox = document.getElementById("output-box");
    lazyFill(outputBox, result.output.split("\n"),
        (line) => `<div class="out-line">${diagramEscape(line)}</div>`, () => {}, outputBox, false);
    renderDiagrams(document.getElementById("viz-box"), result.diagrams);
}

async function refreshNoteTypes(quiet) {
    const select = document.getElementById("cloze-note-type");
    const result = await api().get_cloze_note_types();
    if (!result.ok) {
        if (!quiet) showToast("Could not reach Anki: " + result.error, true);
        return false;
    }
    if (!result.names.length) {
        select.innerHTML = '<option value="">(no suitable note type)</option>';
        if (!quiet) showToast("No note type in Anki has the cloze fields. Import one CSV first.", true);
        return false;
    }
    setOptions(select, result.names, false);
    select.value = result.selected;
    return true;
}

// Whether Anki is open, checked now and then: shown in the bar, and the
// note types are loaded each time it comes up.
let ankiUp = null;
async function checkAnki() {
    const up = (await api().anki_status()).ok;
    if (up !== ankiUp) {
        ankiUp = up;
        const pill = document.getElementById("anki-status");
        pill.classList.toggle("on", up);
        pill.textContent = up ? "Anki connected" : "Anki not running";
        if (up) {
            await refreshNoteTypes(true);
        } else {
            document.getElementById("cloze-note-type").innerHTML = '<option value="">(open Anki to choose)</option>';
        }
    }
}

async function doExportClozeToAnki() {
    const btn = document.getElementById("btn-export-cloze-anki");
    if (!document.getElementById("cloze-note-type").value && !(await refreshNoteTypes(false))) return;
    btn.disabled = true;
    btn.textContent = "Sending...";
    try {
        const result = await api().export_cloze_to_anki(
            parseInt(document.getElementById("max-leaf-disj").value, 10) || 2,
            document.getElementById("reset-per-line").checked,
            document.getElementById("cloze-deck").value,
            document.getElementById("cloze-note-type").value,
        );
        if (!result.ok) {
            showToast(result.error, true);
            return;
        }
        let msg = `Added ${result.notes_added} note(s) to ${result.deck}`;
        if (result.already_in_anki) msg += `; ${result.already_in_anki} already in Anki, left as they are`;
        if (result.failed) msg += `; ${result.failed} rejected by Anki`;
        showToast(msg, result.failed > 0);
    } finally {
        renderVerseBoxes();  // the button's label and state
    }
}

// =============================================================
//  Saving the diagrams: a dialog of options beside a live preview of
//  the page. The diagrams are drawn here at the page's width
//  (snapshotDiagrams) with the drawing options, then laid out by
//  ankipasuk.diagram_pages with the page options -- the same both for
//  the preview and for the file.
// =============================================================
const PREVIEW_PESUQIM = 12;  // the preview shows the first few
const PRINT_OPTIONS_KEY = "ankipasuk_print_options";
// Which options are the drawing's (diagram.js); the rest are the page's.
const DRAW_OPTIONS = ["textSize", "row", "labels", "labelSize", "grey", "bw"];

function optionInputs() {
    return [...document.querySelectorAll("#print-dialog [data-opt]")];
}

function readPrintOptions() {
    const o = {};
    for (const el of optionInputs()) {
        o[el.dataset.opt] = el.type === "checkbox" ? el.checked : el.type === "range" ? Number(el.value) : el.value;
    }
    const draw = Object.fromEntries(DRAW_OPTIONS.map((k) => [k, o[k]]));
    // The page needs to know about black and white and the grey brackets
    // too, for its legend and colours.
    const page = Object.fromEntries(Object.entries(o).filter(([k]) => !DRAW_OPTIONS.includes(k) || k === "bw" || k === "grey"));
    return { all: o, draw, page };
}

function showOptionValues() {
    const units = { textSize: "px", row: "px", labelSize: "px", margin_mm: "mm", spacing_px: "px" };
    for (const el of optionInputs()) {
        if (el.type === "range") el.nextElementSibling.textContent = el.value + (units[el.dataset.opt] || "");
    }
    const labels = document.querySelector('[data-opt="labels"]').value !== "none";
    document.querySelector('[data-opt="labelSize"]').disabled = !labels;
}

function restorePrintOptions() {
    let saved = {};
    try { saved = JSON.parse(localStorage.getItem(PRINT_OPTIONS_KEY) || "{}"); } catch (e) { /* none kept */ }
    for (const el of optionInputs()) {
        if (!(el.dataset.opt in saved)) continue;
        if (el.type === "checkbox") el.checked = saved[el.dataset.opt];
        else el.value = saved[el.dataset.opt];
    }
    showOptionValues();
}

function rememberPrintOptions() {
    try { localStorage.setItem(PRINT_OPTIONS_KEY, JSON.stringify(readPrintOptions().all)); } catch (e) { /* not kept */ }
}

function printSubtitle() {
    const n = parseInt(document.getElementById("max-leaf-disj").value, 10) || 2;
    return `${currentDiagrams.length} ${currentDiagrams.length === 1 ? "pasuq" : "pesuqim"} · groups per clause: ${n}`;
}

function setPrintStatus(text) {
    const el = document.getElementById("pd-status");
    el.textContent = text;
    el.hidden = !text;
}

function openPrintDialog() {
    if (!currentDiagrams.length) return showToast("Nothing loaded yet.", true);
    const title = document.getElementById("pd-title");
    title.value = [...document.querySelectorAll(".range-summary")].map((el) => el.textContent).join("; ");
    const shown = Math.min(PREVIEW_PESUQIM, currentDiagrams.length);
    document.getElementById("pd-note").textContent = currentDiagrams.length > shown
        ? `The preview shows the first ${shown} of the ${currentDiagrams.length} pesuqim; the file has them all.`
        : "";
    document.getElementById("print-dialog").hidden = false;
    renderPrintPreview();
}

function closePrintDialog() {
    document.getElementById("print-dialog").hidden = true;
    document.getElementById("pd-frame").srcdoc = "";
}

// The preview, redrawn a moment after the last change. Each run has its
// token, so a slow one finishing late doesn't replace a newer one.
let printPreviewTimer = null;
let printPreviewToken = 0;
function schedulePrintPreview() {
    clearTimeout(printPreviewTimer);
    printPreviewTimer = setTimeout(renderPrintPreview, 200);
}

async function renderPrintPreview() {
    const token = ++printPreviewToken;
    const { draw, page } = readPrintOptions();
    setPrintStatus("Drawing…");
    const width = await api().diagram_page_width(page);
    const body = await snapshotDiagrams(currentDiagrams.slice(0, PREVIEW_PESUQIM), width, null, draw);
    const result = await api().preview_diagrams(body, document.getElementById("pd-title").value, printSubtitle(), page);
    if (token !== printPreviewToken) return;
    setPrintStatus("");
    if (!result.ok) return setPrintStatus("Could not show the preview: " + result.error);
    const frame = document.getElementById("pd-frame");
    const scroll = frame.contentWindow ? frame.contentWindow.scrollY : 0;
    // The frame is scaled from outside to fit the sheet's width in the
    // dialog, so inside it the page keeps its true size and can be
    // measured for its page breaks.
    const [sheetW, sheetH] = sheetPx(page);
    const holder = frame.parentElement;
    const zoom = Math.min(1, (holder.clientWidth - 30) / (sheetW + 30));
    Object.assign(frame.style, {
        width: `${holder.clientWidth / zoom}px`, height: `${holder.clientHeight / zoom}px`,
        transform: `scale(${zoom})`, transformOrigin: "0 0",
    });
    frame.onload = () => {
        showPageBreaks(frame.contentDocument, sheetH, Number(page.margin_mm) * PX_PER_MM);
        frame.contentWindow.scrollTo(0, scroll);
    };
    frame.srcdoc = result.html;
}

const PX_PER_MM = 96 / 25.4;

// The sheet's width and height in px (diagram_pages.paper_mm).
function sheetPx(page) {
    const [w, h] = { A4: [210, 297], Letter: [215.9, 279.4] }[page.paper] || [210, 297];
    return (page.orientation === "landscape" ? [h, w] : [w, h]).map((mm) => mm * PX_PER_MM);
}

// The preview's one long sheet cut into pages where the PDF's are: a
// pasuq that doesn't fit what's left of a page starts the next (the PDF
// keeps each pasuq whole). A gap the colour of the desk stands between
// the sheets, with the page's number at the bottom of each.
function showPageBreaks(doc, sheetH, margin) {
    const body = doc.body;
    const contentH = sheetH - 2 * margin;
    const blocks = [...body.children];
    const top = () => body.getBoundingClientRect().top + margin;
    let pageStart = 0;
    let pageNo = 1;
    for (const el of blocks) {
        const r = el.getBoundingClientRect();
        const start = r.top - top();
        const end = r.bottom - top();
        if (end - pageStart <= contentH || start <= pageStart) continue;
        const rest = pageStart + contentH - start;  // what's left of this page
        const cut = doc.createElement("div");
        cut.style.cssText = `height: ${rest + 2 * margin + 16}px; margin: 0 -${margin}px; position: relative;`
            + ` background: linear-gradient(white 0 ${rest + margin}px, #8d8d8d ${rest + margin}px`
            + ` ${rest + margin + 16}px, white ${rest + margin + 16}px);`;
        cut.innerHTML = `<span style="position: absolute; left: 0; right: 0; top: ${rest + margin - 22}px;`
            + ` text-align: center; font: 8pt sans-serif; color: #999;">${pageNo}</span>`;
        el.before(cut);
        pageNo += 1;
        pageStart = el.getBoundingClientRect().top - top();
    }
    // The last sheet is a whole page long too, with its number.
    const end = body.lastElementChild.getBoundingClientRect().bottom - top();
    const pad = doc.createElement("div");
    pad.style.cssText = `height: ${Math.max(0, pageStart + contentH - end)}px; position: relative;`;
    pad.innerHTML = `<span style="position: absolute; left: 0; right: 0; bottom: -${margin - 22}px;`
        + ` text-align: center; font: 8pt sans-serif; color: #999;">${pageNo}</span>`;
    body.appendChild(pad);
    body.style.minHeight = "0";
}

async function doSaveDiagrams(fmt) {
    const { draw, page } = readPrintOptions();
    const buttons = [document.getElementById("pd-save-pdf"), document.getElementById("pd-save-html")];
    for (const b of buttons) b.disabled = true;
    try {
        const width = await api().diagram_page_width(page);
        const body = await snapshotDiagrams(currentDiagrams, width, (done, total) => {
            setPrintStatus(`Drawing ${done} of ${total}…`);
        }, draw);
        // WeasyPrint takes about a second for each six pesuqim.
        const long = currentDiagrams.length > 300 ? ` (about ${Math.ceil(currentDiagrams.length / 360)} min)` : "";
        setPrintStatus(fmt === "pdf" ? `Making the PDF…${long}` : "Saving…");
        const result = await api().export_diagrams(body, fmt, document.getElementById("pd-title").value,
            printSubtitle(), page);
        if (!result.ok) {
            if (result.error) showToast("Could not save: " + result.error, true);
            return; // null error: the save dialog was cancelled
        }
        const pages = result.pages ? ` (${result.pages} page${result.pages === 1 ? "" : "s"})` : "";
        showToast(`Saved to ${result.path}${pages}`, false);
        closePrintDialog();
    } finally {
        for (const b of buttons) b.disabled = false;
        setPrintStatus("");
    }
}

function wirePrintDialog() {
    restorePrintOptions();
    for (const el of optionInputs()) {
        el.addEventListener("input", () => {
            showOptionValues();
            rememberPrintOptions();
            schedulePrintPreview();
        });
    }
    document.getElementById("pd-title").addEventListener("input", schedulePrintPreview);
    document.getElementById("btn-save-diagrams").addEventListener("click", openPrintDialog);
    document.getElementById("pd-save-pdf").addEventListener("click", () => doSaveDiagrams("pdf"));
    document.getElementById("pd-save-html").addEventListener("click", () => doSaveDiagrams("html"));
    document.getElementById("pd-cancel").addEventListener("click", closePrintDialog);
    document.getElementById("pd-reset").addEventListener("click", () => {
        try { localStorage.removeItem(PRINT_OPTIONS_KEY); } catch (e) { /* nothing kept */ }
        for (const el of optionInputs()) {
            if (el.type === "checkbox") el.checked = el.defaultChecked;
            else if (el.tagName === "SELECT") el.value = [...el.options].find((op) => op.defaultSelected)?.value || el.options[0].value;
            else el.value = el.defaultValue;
        }
        showOptionValues();
        renderPrintPreview();
    });
    document.getElementById("print-dialog").addEventListener("click", (e) => {
        if (e.target.id === "print-dialog") closePrintDialog();
    });
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && !document.getElementById("print-dialog").hidden) closePrintDialog();
    });
}

async function doExportCsv() {
    const maxLeafDisj = parseInt(document.getElementById("max-leaf-disj").value, 10) || 2;
    const resetPerLine = document.getElementById("reset-per-line").checked;
    const result = await api().export_csv(maxLeafDisj, resetPerLine);
    if (!result.ok) {
        if (result.error) showToast(result.error, true);
        return; // null error = user cancelled the save dialog, not an error
    }
    showToast(`Exported ${result.count} card(s) to ${result.path}`, false);
}

// =============================================================
//  'Ammud ranges -- rows of "from 'ammud X to Y", like the source ranges
//  above; every 'ammud in every row is exported, once, to its own deck.
// =============================================================
const TOTAL_AMMUDIM = 245;

// The deck an 'ammud's cards go into is fixed: one per 'ammud (see
// qeriya.tiqqun_ammud_deck), shown, not typed.
function ammudDeck(amud) {
    return "Ammudim::" + String(amud).padStart(3, "0");
}

function selectedAmmudim() {
    const all = new Set();
    for (const row of document.querySelectorAll(".ammud-row")) {
        const start = parseInt(row.querySelector(".ammud-start").value, 10);
        const end = parseInt(row.querySelector(".ammud-end").value, 10);
        for (const n of numbersFrom(start, end)) all.add(n);
    }
    return [...all].sort((a, b) => a - b);
}

function updateAmmudDeck() {
    const ammudim = selectedAmmudim();
    let text = ammudDeck(ammudim[0]);
    if (ammudim.length > 1) {
        text = `${ammudim.length} 'ammudim, each to its own deck (${ammudDeck(ammudim[0])} … ${ammudDeck(ammudim.at(-1))})`;
    }
    document.getElementById("lpcg-deck").textContent = text;
    showAmmudPreview(ammudim.includes(previewAmmud) ? previewAmmud : ammudim[0]);
}

// The Tiqqun tab shows one of the chosen 'ammudim at a time, as its page.
let previewAmmud = null;
let previewToken = 0;
async function showAmmudPreview(n) {
    const ammudim = selectedAmmudim();
    const i = ammudim.indexOf(n);
    document.getElementById("ammud-prev").disabled = i <= 0;
    document.getElementById("ammud-next").disabled = i >= ammudim.length - 1;
    document.getElementById("ammud-preview-label").textContent =
        ammudim.length > 1 ? `'Ammud ${n} (${i + 1} of ${ammudim.length})` : `'Ammud ${n}`;
    if (n === previewAmmud || document.querySelector('[data-panel="tiqqun"]').hidden) return;
    previewAmmud = n;
    const token = ++previewToken;
    const result = await api().preview_ammud(n);
    if (token !== previewToken) return;  // another 'ammud was chosen meanwhile
    const frame = document.getElementById("ammud-frame");
    frame.srcdoc = result.ok ? result.html
        : `<p style="font-family:sans-serif;color:#b71c1c">Could not load 'ammud ${n}: ${diagramEscape(result.error)}</p>`;
}

function stepAmmudPreview(step) {
    const ammudim = selectedAmmudim();
    const next = ammudim[ammudim.indexOf(previewAmmud) + step];
    if (next !== undefined) showAmmudPreview(next);
}

// The end can't come before the start, as with the source ranges.
function constrainAmmudEnd(row) {
    const start = parseInt(row.querySelector(".ammud-start").value, 10);
    setOptions(row.querySelector(".ammud-end"), numbersFrom(start, TOTAL_AMMUDIM), true);
    updateAmmudDeck();
}

function addAmmudRow() {
    const row = document.createElement("div");
    row.className = "ammud-row";
    row.innerHTML = `
      'Ammud <select class="ammud-start"></select>
      to <select class="ammud-end"></select>
      <button class="btn-remove-ammud-range range-remove" type="button" title="Remove this range">✕</button>`;
    document.getElementById("ammud-ranges").appendChild(row);
    // A new row starts just after the last row's end, or at 1.
    const rows = document.querySelectorAll(".ammud-row");
    const prev = rows.length > 1 ? parseInt(rows[rows.length - 2].querySelector(".ammud-end").value, 10) : 0;
    const first = Math.min(prev + 1, TOTAL_AMMUDIM);
    setOptions(row.querySelector(".ammud-start"), numbersFrom(1, TOTAL_AMMUDIM), false);
    row.querySelector(".ammud-start").value = String(first);
    constrainAmmudEnd(row);
    row.querySelector(".ammud-start").addEventListener("change", () => constrainAmmudEnd(row));
    row.querySelector(".ammud-end").addEventListener("change", updateAmmudDeck);
    row.querySelector(".btn-remove-ammud-range").addEventListener("click", () => {
        if (document.querySelectorAll(".ammud-row").length <= 1) {
            showToast("At least one 'ammud range is required.", true);
            return;
        }
        row.remove();
        updateAmmudDeck();
    });
}

async function doExportPages() {
    const btn = document.getElementById("btn-export-pages");
    const ammudim = selectedAmmudim();
    const fmt = document.getElementById("page-format").value;
    btn.disabled = true;
    btn.textContent = "Saving...";
    try {
        const result = await api().export_ammud_pages(ammudim, fmt);
        if (!result.ok) {
            if (result.error) showToast("Export failed: " + result.error, true);
            return; // null error: the save dialog was cancelled
        }
        const what = result.count === 1 ? `'Ammud ${ammudim[0]}` : `${result.count} 'ammudim`;
        document.getElementById("lpcg-status").textContent = `${what} saved as ${fmt.toUpperCase()} to ${result.path}`;
        showToast("Saved.", false);
    } finally {
        btn.disabled = false;
        btn.textContent = "Save pages as";
    }
}

async function doExportAmud(toCsv) {
    const ammudim = selectedAmmudim();
    const args = [
        ammudim,
        document.getElementById("lpcg-card-division").value,
        parseInt(document.getElementById("lpcg-context-lines").value, 10) || 0,
        parseInt(document.getElementById("lpcg-recite-lines").value, 10) || 1,
        parseInt(document.getElementById("lpcg-group-size").value, 10) || 1,
    ];
    const btn = document.getElementById(toCsv ? "btn-export-amud-csv" : "btn-export-amud");
    const label = btn.textContent;
    const status = document.getElementById("lpcg-status");
    btn.disabled = true;
    btn.textContent = toCsv ? "Saving..." : "Exporting...";
    status.textContent = "";
    try {
        const result = toCsv ? await api().export_ammudim_csv(...args) : await api().export_ammudim_to_anki(...args);
        if (!result.ok) {
            if (result.error) showToast("Export failed: " + result.error, true);
            return; // null error: the save dialog was cancelled
        }
        const what = ammudim.length === 1 ? `'Ammud ${ammudim[0]}` : `${ammudim.length} 'ammudim`;
        if (toCsv) {
            status.textContent = `${what}: ${result.count} card(s) saved to ${result.path}`;
        } else {
            let msg = `${what}: ${result.notes_added} card(s) added`;
            if (result.already_in_anki) msg += `, ${result.already_in_anki} already in Anki (left as they are)`;
            if (result.failed) msg += `, ${result.failed} rejected by Anki`;
            status.textContent = msg;
        }
        showToast(toCsv ? "Saved." : "Exported to Anki.", false);
    } finally {
        btn.disabled = false;
        btn.textContent = label;
    }
}

// =============================================================
//  Tikkun.io scroll layout (source section) -- box/line/setuma CSS and
//  the STAM font itself, injected once from the same source lpcg.py's
//  own Anki-card CSS uses, so the two never drift apart.
// =============================================================
async function injectTikkunCss() {
    const scrollCss = await api().get_tikkun_scroll_css();
    const fontResult = await api().get_tikkun_font_css();
    const style = document.createElement("style");
    style.textContent = scrollCss + "\n" + (fontResult.ok ? fontResult.css : "");
    document.head.appendChild(style);
    if (!fontResult.ok) {
        console.warn("Could not load the tikkun.io STAM font:", fontResult.error);
    }
}

// Mirrors the Anki card's own on-card controls (lpcg.py's own
// _SIZE_CONTROLS_HTML / --ankipasuk-font-size, --ankipasuk-line-height-scale,
// --ankipasuk-width-scale) -- render_scroll_html's own CSS already reads
// these same custom properties (see lpcg.py's SCROLL_CSS), so adjusting
// them here resizes/respaces the box live with no re-fetch/re-render
// needed. Each control keeps its own localStorage key/CSS var here,
// separate from an Anki card's own -- this window and an Anki card's own
// webview are different browser contexts that share nothing.
function makeSizeControl(cssVar, storageKey, unit, { step, min, max, defaultValue }) {
    let current = defaultValue; // when there's no storage (a private web view), just for now
    const read = () => {
        try {
            const stored = localStorage.getItem(storageKey);
            if (stored) current = parseFloat(stored);
        } catch (e) { /* no storage */ }
        return current;
    };
    const apply = (value) => {
        document.documentElement.style.setProperty(cssVar, value + unit);
    };
    const adjust = (direction) => {
        current = Math.min(max, Math.max(min, read() + direction * step));
        try { localStorage.setItem(storageKey, current); } catch (e) { /* not kept */ }
        apply(current);
    };
    return { read, apply, adjust };
}

const tikkunFontSizeControl = makeSizeControl(
    "--ankipasuk-font-size", "ankipasuk_webgui_font_size_px", "px",
    { step: 2, min: 8, max: 60, defaultValue: 16 }, // 16 matches #tikkun-box's own default font-size
);
const tikkunLineHeightControl = makeSizeControl(
    "--ankipasuk-line-height-scale", "ankipasuk_webgui_line_height_scale", "",
    { step: 0.1, min: 0.7, max: 2.5, defaultValue: 1 },
);
const tikkunWidthControl = makeSizeControl(
    "--ankipasuk-width-scale", "ankipasuk_webgui_width_scale", "",
    { step: 0.1, min: 0.5, max: 2.5, defaultValue: 1 },
);

function applyStoredTikkunControls() {
    tikkunFontSizeControl.apply(tikkunFontSizeControl.read());
    tikkunLineHeightControl.apply(tikkunLineHeightControl.read());
    tikkunWidthControl.apply(tikkunWidthControl.read());
}

// The settings column, folded away or not, for both tabs at once; kept
// for next time.
function setSidebarCollapsed(collapsed) {
    document.body.classList.toggle("sidebar-collapsed", collapsed);
    for (const btn of document.querySelectorAll(".sidebar-toggle")) {
        btn.textContent = collapsed ? "▶ Settings" : "◀";
        btn.title = collapsed ? "Show the settings" : "Hide the settings, to see the preview on its own";
    }
    try {
        localStorage.setItem("ankipasuk_sidebar_collapsed", collapsed ? "1" : "");
    } catch (e) { /* storage unavailable: just not remembered */ }
}

// A row of buttons of which one is active (the preview's tabs, the
// pointed / letters-only switches); ``onPick`` gets the picked button.
function segmented(container, onPick) {
    for (const btn of container.querySelectorAll("button")) {
        btn.addEventListener("click", () => {
            for (const b of container.querySelectorAll("button")) b.classList.toggle("active", b === btn);
            onPick(btn);
        });
    }
}

// =============================================================
//  Clipboard
// =============================================================
async function copyText(text) {
    try {
        await navigator.clipboard.writeText(text);
        showToast("Copied to clipboard", false);
    } catch (e) {
        showToast("Could not copy: " + e, true);
    }
}

// =============================================================
//  Wiring
// =============================================================
window.addEventListener("pywebviewready", async () => {
    cachedBooks = await api().get_books();
    cachedBookLabels = await api().get_book_labels();
    document.getElementById("cache-status").textContent = await api().get_cache_status();
    injectTikkunCss();
    applyStoredTikkunControls();
    renderVerseBoxes();
    await addRangeRow(); // start with one range, loaded straight away

    let collapsed = false;
    try { collapsed = localStorage.getItem("ankipasuk_sidebar_collapsed") === "1"; } catch (e) { /* none kept */ }
    setSidebarCollapsed(collapsed);
    for (const btn of document.querySelectorAll(".sidebar-toggle")) {
        btn.addEventListener("click", () => setSidebarCollapsed(!document.body.classList.contains("sidebar-collapsed")));
    }

    segmented(document.getElementById("main-tabs"), (btn) => {
        for (const panel of document.querySelectorAll(".workspace")) panel.hidden = panel.dataset.panel !== btn.dataset.tab;
        document.getElementById("line-count").hidden = btn.dataset.tab !== "cloze";
        if (btn.dataset.tab === "tiqqun") updateAmmudDeck();  // loads the preview the first time
    });
    segmented(document.getElementById("preview-tabs"), (btn) => {
        for (const view of document.querySelectorAll(".preview-body .view")) view.hidden = view.dataset.view !== btn.dataset.view;
    });
    segmented(document.getElementById("text-kind"), renderTextBox);
    document.getElementById("text-box").addEventListener("click", (e) => {
        const word = e.target.closest(".w");
        if (word) rootColours.toggle(word.dataset.g);
    });
    document.getElementById("roots-list").addEventListener("click", (e) => {
        const item = e.target.closest("li[data-root]");
        if (!item) return;
        const spark = e.target.closest(".spark");
        if (spark) {  // go to the nearest pasuq with the root, and flash its words there
            const g = item.dataset.root, v = sparklinePasuq(spark, e.clientX);
            const first = (currentShorashim.verses[v] || []).findIndex((word) => String(word[2]) === g);
            showInText(v, first < 0 ? undefined : first, (box) => flashElements(box,
                box.querySelectorAll(`.tv-line[data-i="${v}"] [data-g="${g}"]`)));
            return;
        }
        rootColours.toggle(item.dataset.root);
    });
    addRootTooltips(document.getElementById("text-box"), (g) => currentShorashim && currentShorashim.groups[g]);
    document.getElementById("btn-clear-roots").addEventListener("click", () => {
        rootColours.clear();
        phraseMarks.clear();
    });
    segmented(document.getElementById("panel-kind"), (btn) => {
        for (const pane of document.querySelectorAll("#roots-panel .panel-pane")) pane.hidden = pane.dataset.pane !== btn.dataset.pane;
        document.getElementById("roots-panel").classList.toggle("wide", btn.dataset.pane === "phrases");
        if (btn.dataset.pane === "phrases") renderPhrasesList();
    });
    document.getElementById("ph-tabs").addEventListener("click", (e) => {
        const tab = e.target.closest("button[data-kind]");
        if (!tab) return;
        phraseKind = tab.dataset.kind;
        renderPhrasesList();
        document.getElementById("phrases-list").scrollTop = 0;
    });
    // A row picks its phrase (underlined in the text, and shown: the
    // first occurrence in view, or else the first); its arrows go from one
    // occurrence to the next; a place opens its viewer.
    document.getElementById("phrases-list").addEventListener("click", (e) => {
        if (e.target.closest(".ph-more button")) {
            togglePhrasesAll(phraseKind);
            renderPhrasesList();
            return;
        }
        const item = e.target.closest("li.ph");
        if (!item) return;
        const p = currentPhrases.phrases[Number(item.dataset.id)];
        const place = e.target.closest(".ph-place");
        if (place) {
            e.preventDefault();
            openPhraseViewer(p, phraseKind, phraseCalls, Number(place.dataset.place));
            return;
        }
        const spark = e.target.closest(".spark");
        if (spark) {  // the occurrence in (or nearest) the pasuq clicked
            const v = sparklinePasuq(spark, e.clientX);
            jumpToPhrase(p, Math.max(p.spans.findIndex(([at]) => at === v), 0));
            return;
        }
        const jump = e.target.closest(".ph-jump button");
        if (jump) {
            jumpToPhrase(p, (phraseAt.get(p.id) || 0) + Number(jump.dataset.jump));
            return;
        }
        if (e.target.closest(".ph-jump")) return;
        phraseMarks.toggle(p.id);
        if (phraseMarks.colours.has(p.id)) {
            document.getElementById("phrases-list").scrollTop = 0;  // it's now at the top
            jumpToPhrase(p, Math.max(phraseInView(p), 0));
        } else {
            phraseAt.delete(p.id);
        }
    });
    document.getElementById("roots-particles").addEventListener("change", renderRootsList);
    segmented(document.getElementById("roots-sort"), renderRootsList);
    segmented(document.getElementById("tikkun-kind"), renderVerseBoxes);

    document.getElementById("btn-add-range").addEventListener("click", addRangeRow);
    document.getElementById("max-leaf-disj").addEventListener("input", () => scheduleRefresh(false));
    document.getElementById("reset-per-line").addEventListener("change", () => scheduleRefresh(false));
    document.getElementById("cloze-deck").addEventListener("input", (e) => { e.target.dataset.typed = "1"; });

    document.getElementById("tikkun-font-minus").addEventListener("click", () => tikkunFontSizeControl.adjust(-1));
    document.getElementById("tikkun-font-plus").addEventListener("click", () => tikkunFontSizeControl.adjust(1));
    document.getElementById("tikkun-line-height-minus").addEventListener(
        "click", () => tikkunLineHeightControl.adjust(-1));
    document.getElementById("tikkun-line-height-plus").addEventListener(
        "click", () => tikkunLineHeightControl.adjust(1));
    document.getElementById("tikkun-width-minus").addEventListener("click", () => tikkunWidthControl.adjust(-1));
    document.getElementById("tikkun-width-plus").addEventListener("click", () => tikkunWidthControl.adjust(1));

    document.getElementById("btn-export-csv").addEventListener("click", doExportCsv);
    wirePrintDialog();
    document.getElementById("btn-export-cloze-anki").addEventListener("click", doExportClozeToAnki);
    checkAnki();
    setInterval(checkAnki, 8000);

    document.getElementById("btn-clear-cache").addEventListener("click", async () => {
        if (!confirm("Clear the local Sefaria cache? Future fetches will re-download from the network.")) return;
        const result = await api().clear_cache();
        document.getElementById("cache-status").textContent = result.cache_status;
        showToast("Cache cleared", false);
    });

    document.getElementById("btn-copy-text").addEventListener("click", () => {
        const pointed = document.querySelector("#text-kind .active").dataset.kind === "pointed";
        copyText(currentVerseData.map((v) => (pointed ? v.pointed : v.plain)).join("\n"));
    });
    document.getElementById("btn-copy-cloze").addEventListener("click", () => {
        if (!currentClozeOutput) return showToast("Nothing loaded yet.", true);
        copyText(currentClozeOutput);
    });

    document.getElementById("btn-stats").addEventListener("click", async () => {
        const maxLeafDisj = parseInt(document.getElementById("max-leaf-disj").value, 10) || 2;
        const result = await api().open_stats_window(maxLeafDisj);
        if (!result.ok) showToast(result.error, true);
    });
    document.getElementById("btn-anki-tools").addEventListener("click", async () => {
        await api().open_anki_connect_window();
    });
    document.getElementById("btn-settings").addEventListener("click", openSettings);
    const settingsDialog = document.getElementById("settings-dialog");
    settingsDialog.addEventListener("click", (e) => {
        if (e.target === settingsDialog || e.target.closest("[data-close]")) closeSettings();
    });
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && !settingsDialog.hidden) closeSettings();
    });
    settingsDialog.addEventListener("input", (e) => {
        if (e.target.dataset.setting) markSetting(e.target);
    });
    document.getElementById("st-reset").addEventListener("click", () => showSettings(settingsDefaults));
    document.getElementById("settings-form").addEventListener("submit", (e) => {
        e.preventDefault();
        saveSettings();
    });

    addAmmudRow();
    document.getElementById("btn-add-ammud-range").addEventListener("click", addAmmudRow);
    document.getElementById("ammud-prev").addEventListener("click", () => stepAmmudPreview(-1));
    document.getElementById("ammud-next").addEventListener("click", () => stepAmmudPreview(1));
    document.getElementById("btn-export-pages").addEventListener("click", doExportPages);
    document.getElementById("btn-export-amud").addEventListener("click", () => doExportAmud(false));
    document.getElementById("btn-export-amud-csv").addEventListener("click", () => doExportAmud(true));

    const updateCardDivisionVisibility = () => {
        const isRowMode = document.getElementById("lpcg-card-division").value === "row";
        document.getElementById("lpcg-row-mode-settings").hidden = !isRowMode;
    };
    updateCardDivisionVisibility();
    document.getElementById("lpcg-card-division").addEventListener("change", updateCardDivisionVisibility);
});
