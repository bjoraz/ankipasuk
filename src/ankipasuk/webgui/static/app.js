"use strict";

let currentVerseData = [];
let currentTikkunHtml = { plain: "", pointed: "" };
let currentClozeOutput = ""; // the full cloze markup, for Copy (the box only holds what's in view)
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
    <div class="field-row range-pa-controls" hidden>
      <select class="range-parasha grow"></select>
      'Aliyya <select class="range-aliyah"></select>
    </div>
  </div>
`;

// The range in one line: "Bereshit 1:1–2:3", "Bereshit · Noaḥ · 'aliyya 2",
// or the haftara's own label.
function rangeSummary(row) {
    const q = (cls) => row.querySelector("." + cls);
    const mode = q("range-mode").value;
    const optionText = (sel) => (sel.selectedOptions[0] || {}).textContent || "";
    if (mode === "hf") return optionText(q("range-haftara")) || "Haftara";
    const book = optionText(q("range-book")).split(" · ")[0];
    if (mode === "pa") return `${book} · ${optionText(q("range-parasha"))} · 'aliyya ${q("range-aliyah").value}`;
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
    setOptions(parashaSelect, result.names, false, result.labels);
    await refreshRangeAliyahDropdown(row);
}

async function refreshRangeAliyahDropdown(row) {
    const book = row.querySelector(".range-book").value;
    const parasha = row.querySelector(".range-parasha").value;
    if (!parasha) return;
    const result = await api().get_aliyah_count(book, parasha);
    if (!result.ok) {
        showToast("Could not load 'aliyyot: " + result.error, true);
        return;
    }
    const aliyot = Array.from({ length: result.count }, (_, i) => i + 1);
    setOptions(row.querySelector(".range-aliyah"), aliyot, true);
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
    on("range-aliyah", async () => {});
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
// The Text and Tikkun views, pointed or letters only as chosen.
function renderVerseBoxes() {
    const pointed = document.querySelector("#text-kind .active").dataset.kind === "pointed";
    const textBox = document.getElementById("text-box");
    textBox.innerHTML = "";
    for (const item of currentVerseData) {
        const line = document.createElement("div");
        line.textContent = pointed ? item.pointed : item.plain;
        textBox.appendChild(line);
    }
    const tikkunPointed = document.querySelector("#tikkun-kind .active").dataset.kind === "pointed";
    document.getElementById("tikkun-box").innerHTML = (tikkunPointed ? currentTikkunHtml.pointed : currentTikkunHtml.plain)
        || '<p class="muted" dir="ltr">The scroll layout is for the Tora only.</p>';
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
    currentTikkunHtml = { plain: "", pointed: "" };
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
            const parasha = row.querySelector(".range-parasha").value;
            const aliyah = parseInt(row.querySelector(".range-aliyah").value, 10);
            result = await api().fetch_parashah_aliyah(book, parasha, aliyah);
            if (result.ok) tikkunResult = await api().fetch_tikkun_parashah_aliyah(book, parasha, aliyah);
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
    const read = () => {
        const stored = localStorage.getItem(storageKey);
        return stored ? parseFloat(stored) : defaultValue;
    };
    const apply = (value) => {
        document.documentElement.style.setProperty(cssVar, value + unit);
    };
    const adjust = (direction) => {
        const next = Math.min(max, Math.max(min, read() + direction * step));
        localStorage.setItem(storageKey, next);
        apply(next);
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
    segmented(document.getElementById("text-kind"), renderVerseBoxes);
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
