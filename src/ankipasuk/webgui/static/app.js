"use strict";

let currentVerseData = [];
let currentTikkunHtml = { plain: "", pointed: "" };
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
  <div class="row">
    <label>Mode:
      <select class="range-mode">
        <option value="cv">Chapter / Verse</option>
        <option value="pa">Parasha / 'Aliyya</option>
        <option value="hf">Haftara</option>
      </select>
    </label>
    <label class="range-book-label">Book:
      <select class="range-book"></select>
    </label>

    <span class="range-hf-controls inline-group" hidden>
      <label>Haftara: <select class="range-haftara"></select></label>
    </span>

    <span class="range-cv-controls inline-group">
      <label>Start chapter: <select class="range-start-ch"></select></label>
      <label>Start verse: <select class="range-start-vs"></select></label>
      <label>End chapter: <select class="range-end-ch"></select></label>
      <label>End verse: <select class="range-end-vs"></select></label>
    </span>

    <span class="range-pa-controls inline-group" hidden>
      <label>Parasha: <select class="range-parasha"></select></label>
      <label>'Aliyya: <select class="range-aliyah"></select></label>
    </span>

    <button class="btn-remove-range" type="button" title="Remove this range">Remove</button>
  </div>
`;

async function onRangeModeChange(row) {
    const mode = row.querySelector(".range-mode").value;
    const isCV = mode === "cv";
    row.querySelector(".range-cv-controls").hidden = !isCV;
    row.querySelector(".range-pa-controls").hidden = mode !== "pa";
    row.querySelector(".range-hf-controls").hidden = mode !== "hf";
    // A haftara names its own books, so the book picker has nothing to do.
    row.querySelector(".range-book-label").hidden = mode === "hf";
    if (mode === "hf") {
        fillHaftaraOptions(row.querySelector(".range-haftara"));
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

async function refreshRangeChapterVerseDropdowns(row) {
    const book = row.querySelector(".range-book").value;
    const result = await api().get_chapter_count(book);
    if (!result.ok) {
        showToast("Could not load " + book + ": " + result.error, true);
        return;
    }
    const chapters = Array.from({ length: result.count }, (_, i) => i + 1);
    setOptions(row.querySelector(".range-start-ch"), chapters, true);
    setOptions(row.querySelector(".range-end-ch"), chapters, true);
    await refreshRangeVerseDropdown(row, "range-start-ch", "range-start-vs");
    await refreshRangeVerseDropdown(row, "range-end-ch", "range-end-vs");
}

async function refreshRangeVerseDropdown(row, chClass, vsClass) {
    const book = row.querySelector(".range-book").value;
    const chapter = parseInt(row.querySelector("." + chClass).value, 10) || 1;
    const result = await api().get_verse_count(book, chapter);
    if (!result.ok) {
        showToast("Could not load verse count: " + result.error, true);
        return;
    }
    const verses = Array.from({ length: result.count }, (_, i) => i + 1);
    setOptions(row.querySelector("." + vsClass), verses, true);
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

function addRangeRow() {
    const container = document.getElementById("ranges-container");
    const row = document.createElement("div");
    row.className = "range-row";
    row.innerHTML = RANGE_ROW_TEMPLATE;
    container.appendChild(row);

    row.querySelector(".range-mode").addEventListener("change", () => onRangeModeChange(row));
    row.querySelector(".range-book").addEventListener("change", () => onRangeBookChange(row));
    row.querySelector(".range-start-ch").addEventListener("change", () =>
        refreshRangeVerseDropdown(row, "range-start-ch", "range-start-vs"));
    row.querySelector(".range-end-ch").addEventListener("change", () =>
        refreshRangeVerseDropdown(row, "range-end-ch", "range-end-vs"));
    row.querySelector(".range-parasha").addEventListener("change", () => refreshRangeAliyahDropdown(row));
    row.querySelector(".btn-remove-range").addEventListener("click", () => {
        if (document.querySelectorAll(".range-row").length <= 1) {
            showToast("At least one range is required.", true);
            return;
        }
        row.remove();
    });

    onRangeModeChange(row);
    return row;
}

// =============================================================
//  Fetching verses (every range row, concatenated in order)
// =============================================================
function renderVerseBoxes() {
    const pointedBox = document.getElementById("pointed-box");
    const plainBox = document.getElementById("plain-box");
    const useTikkun = document.getElementById("tikkun-view-toggle").checked;

    if (useTikkun) {
        const placeholder = "<em>No Tora content in the current range(s).</em>";
        pointedBox.innerHTML = currentTikkunHtml.pointed || placeholder;
        plainBox.innerHTML = currentTikkunHtml.plain || placeholder;
    } else {
        pointedBox.innerHTML = "";
        plainBox.innerHTML = "";
        for (const item of currentVerseData) {
            const p = document.createElement("div");
            p.textContent = item.pointed;
            pointedBox.appendChild(p);

            const t = document.createElement("div");
            t.textContent = item.plain;
            plainBox.appendChild(t);
        }
    }
    document.getElementById("line-count").textContent = "Lines: " + currentVerseData.length;
}

async function doFetchAll() {
    const btn = document.getElementById("btn-fetch");
    btn.disabled = true;
    btn.textContent = "Fetching...";
    try {
        // Always start from a clean accumulated state -- otherwise
        // clicking "Fetch all ranges" a second time (e.g. after editing
        // one row) would double up everything fetched the first time,
        // since the backend appends rather than replaces.
        await api().clear_ranges();
        currentVerseData = [];
        currentTikkunHtml = { plain: "", pointed: "" };
        renderVerseBoxes();

        const rows = document.querySelectorAll(".range-row");
        for (const row of rows) {
            const book = row.querySelector(".range-book").value;
            const mode = row.querySelector(".range-mode").value;
            let result;
            let tikkunResult;
            if (mode === "cv") {
                const startCh = parseInt(row.querySelector(".range-start-ch").value, 10);
                const startVs = parseInt(row.querySelector(".range-start-vs").value, 10);
                const endCh = parseInt(row.querySelector(".range-end-ch").value, 10);
                const endVs = parseInt(row.querySelector(".range-end-vs").value, 10);
                result = await api().fetch_chapter_verse(book, startCh, startVs, endCh, endVs);
                if (result.ok) {
                    tikkunResult = await api().fetch_tikkun_chapter_verse(book, startCh, startVs, endCh, endVs);
                }
            } else if (mode === "hf") {
                result = await api().fetch_haftara(row.querySelector(".range-haftara").value);
            } else {
                const parasha = row.querySelector(".range-parasha").value;
                const aliyah = parseInt(row.querySelector(".range-aliyah").value, 10);
                result = await api().fetch_parashah_aliyah(book, parasha, aliyah);
                if (result.ok) {
                    tikkunResult = await api().fetch_tikkun_parashah_aliyah(book, parasha, aliyah);
                }
            }

            if (!result.ok) {
                showToast("Fetch failed: " + result.error, true);
                return; // whatever ranges succeeded before this one stay visible
            }
            currentVerseData = result.verses;
            // A range outside the Tora leaves tikkunResult.ok true with nothing
            // new added -- only a genuine failure here is worth losing
            // the tikkun display over, and even then the flat text above
            // already fetched fine, so just drop the tikkun HTML rather
            // than failing the whole range.
            if (tikkunResult && tikkunResult.ok) {
                currentTikkunHtml = { plain: tikkunResult.plain_html, pointed: tikkunResult.pointed_html };
            }
            renderVerseBoxes();
            document.getElementById("cache-status").textContent = result.cache_status;
        }
        document.getElementById("cloze-deck").value = await api().suggest_cloze_deck();
    } finally {
        btn.disabled = false;
        btn.textContent = "Fetch all ranges";
    }
}

async function doClearRanges() {
    const result = await api().clear_ranges();
    currentVerseData = result.verses;
    currentTikkunHtml = { plain: "", pointed: "" };
    renderVerseBoxes();
    showToast("Ranges cleared", false);
}

// =============================================================
//  Cloze generation
// =============================================================
async function doGenerate() {
    const maxLeafDisj = parseInt(document.getElementById("max-leaf-disj").value, 10) || 2;
    const resetPerLine = document.getElementById("reset-per-line").checked;
    const result = await api().generate_cloze(maxLeafDisj, resetPerLine);
    if (!result.ok) {
        showToast(result.error, true);
        return;
    }
    document.getElementById("output-box").textContent = result.output;
    document.getElementById("tokens-box").textContent = result.tokens;
    document.getElementById("viz-box").innerHTML = result.viz_html;
}

// The analysis (cloze numbers, closing ta'amim, the per-pasuq table) is
// always in the generated HTML; the checkbox only shows or hides it, so
// toggling needs no round trip. The choice is remembered per browser.
function wireAnalysisToggle() {
    const box = document.getElementById("show-analysis");
    try {
        box.checked = localStorage.getItem("showAnalysis") === "1";
    } catch (e) { /* storage unavailable: start unchecked */ }
    const apply = () => {
        document.getElementById("viz-box").classList.toggle("show-analysis", box.checked);
        try {
            localStorage.setItem("showAnalysis", box.checked ? "1" : "0");
        } catch (e) { /* not remembered, still applied */ }
    };
    box.addEventListener("change", apply);
    apply();
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
        btn.disabled = false;
        btn.textContent = "Send to Anki";
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
//  'Aliyya range export to Anki (tiqqun cards)
// =============================================================
async function refreshLpcgParashaDropdowns() {
    const book = document.getElementById("lpcg-book").value;
    const result = await api().get_parashot(book);
    if (!result.ok) {
        showToast("Could not load parashiyyot: " + result.error, true);
        return;
    }
    setOptions(document.getElementById("lpcg-start-parasha"), result.names, true, result.labels);
    setOptions(document.getElementById("lpcg-end-parasha"), result.names, true, result.labels);
    await refreshLpcgAliyahDropdown("start");
    await refreshLpcgAliyahDropdown("end");
}

async function refreshLpcgAliyahDropdown(which) {
    const book = document.getElementById("lpcg-book").value;
    const parasha = document.getElementById("lpcg-" + which + "-parasha").value;
    if (!parasha) return;
    const result = await api().get_aliyah_count(book, parasha);
    if (!result.ok) {
        showToast("Could not load 'aliyyot: " + result.error, true);
        return;
    }
    const aliyot = Array.from({ length: result.count }, (_, i) => i + 1);
    setOptions(document.getElementById("lpcg-" + which + "-aliyah"), aliyot, true);
}

function lpcgSettings() {
    return {
        deckName: document.getElementById("lpcg-deck").value.trim(),
        cardDivision: document.getElementById("lpcg-card-division").value,
        contextLines: parseInt(document.getElementById("lpcg-context-lines").value, 10) || 0,
        reciteLines: parseInt(document.getElementById("lpcg-recite-lines").value, 10) || 1,
        groupSize: parseInt(document.getElementById("lpcg-group-size").value, 10) || 1,
    };
}

// What a tiqqun export did, for the status line under the panel.
function lpcgSummary(result, what, toCsv) {
    if (toCsv) return `${what}: ${result.count} card(s) saved to ${result.path}`;
    let msg = `${what}: ${result.notes_added} card(s) added`;
    if (result.already_in_anki) msg += `, ${result.already_in_anki} already in Anki (left as they are)`;
    if (result.failed) msg += `, ${result.failed} rejected by Anki`;
    return msg;
}

async function runLpcgExport(btn, label, call, describe, toCsv) {
    const status = document.getElementById("lpcg-status");
    btn.disabled = true;
    btn.textContent = toCsv ? "Saving..." : "Exporting...";
    status.textContent = "";
    try {
        const result = await call();
        if (!result.ok) {
            if (result.error) showToast("Export failed: " + result.error, true);
            return; // null error: the save dialog was cancelled
        }
        status.textContent = lpcgSummary(result, describe(result), toCsv);
        showToast(toCsv ? "Saved." : "Exported to Anki.", false);
    } finally {
        btn.disabled = false;
        btn.textContent = label;
    }
}

async function doExportLpcg(toCsv) {
    const s = lpcgSettings();
    if (!s.deckName) {
        showToast("Enter an Anki deck name.", true);
        return;
    }
    const args = [
        document.getElementById("lpcg-book").value,
        document.getElementById("lpcg-start-parasha").value,
        parseInt(document.getElementById("lpcg-start-aliyah").value, 10),
        document.getElementById("lpcg-end-parasha").value,
        parseInt(document.getElementById("lpcg-end-aliyah").value, 10),
        s.deckName, s.cardDivision, s.contextLines, s.reciteLines, s.groupSize,
    ];
    const btn = document.getElementById(toCsv ? "btn-export-lpcg-csv" : "btn-export-lpcg");
    await runLpcgExport(
        btn, toCsv ? "Save as CSV" : "Export 'aliyyot to Anki",
        () => (toCsv ? api().export_aliyot_csv(...args) : api().export_aliyot_to_anki(...args)),
        (r) => (r.aliyot ? `${r.aliyot} ${r.aliyot === 1 ? "'aliyya" : "'aliyyot"}` : "'Aliyyot"),
        toCsv,
    );
}

async function doExportAmud(toCsv) {
    const s = lpcgSettings();
    const amud = parseInt(document.getElementById("lpcg-amud").value, 10);
    if (!amud || amud < 1 || amud > 245) {
        showToast("Enter an 'ammud number from 1 to 245.", true);
        return;
    }
    if (!s.deckName) {
        showToast("Enter an Anki deck name.", true);
        return;
    }
    const args = [amud, s.deckName, s.cardDivision, s.contextLines, s.reciteLines, s.groupSize];
    const btn = document.getElementById(toCsv ? "btn-export-amud-csv" : "btn-export-amud");
    await runLpcgExport(
        btn, toCsv ? "Save as CSV" : "Export 'ammud to Anki",
        () => (toCsv ? api().export_amud_csv(...args) : api().export_amud_to_anki(...args)),
        (r) => (r.book ? `${r.book} 'ammud ${r.amud}` : `'Ammud ${amud}`),
        toCsv,
    );
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
    { step: 2, min: 8, max: 60, defaultValue: 16 }, // 16 matches .text-box's own default font-size
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

function updateTikkunViewVisibility() {
    const useTikkun = document.getElementById("tikkun-view-toggle").checked;
    document.getElementById("tikkun-display-controls").hidden = !useTikkun;
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
    wireAnalysisToggle();
    addRangeRow(); // start with exactly one range row
    document.getElementById("cache-status").textContent = await api().get_cache_status();
    injectTikkunCss();
    applyStoredTikkunControls();

    document.getElementById("btn-add-range").addEventListener("click", addRangeRow);
    document.getElementById("btn-fetch").addEventListener("click", doFetchAll);
    document.getElementById("btn-clear-ranges").addEventListener("click", doClearRanges);
    document.getElementById("tikkun-view-toggle").addEventListener("change", () => {
        updateTikkunViewVisibility();
        renderVerseBoxes();
    });
    updateTikkunViewVisibility();
    document.getElementById("tikkun-font-minus").addEventListener("click", () => tikkunFontSizeControl.adjust(-1));
    document.getElementById("tikkun-font-plus").addEventListener("click", () => tikkunFontSizeControl.adjust(1));
    document.getElementById("tikkun-line-height-minus").addEventListener(
        "click", () => tikkunLineHeightControl.adjust(-1));
    document.getElementById("tikkun-line-height-plus").addEventListener(
        "click", () => tikkunLineHeightControl.adjust(1));
    document.getElementById("tikkun-width-minus").addEventListener("click", () => tikkunWidthControl.adjust(-1));
    document.getElementById("tikkun-width-plus").addEventListener("click", () => tikkunWidthControl.adjust(1));

    document.getElementById("btn-generate").addEventListener("click", doGenerate);
    document.getElementById("btn-export-csv").addEventListener("click", doExportCsv);
    document.getElementById("btn-export-cloze-anki").addEventListener("click", doExportClozeToAnki);
    document.getElementById("btn-refresh-note-types").addEventListener("click", () => refreshNoteTypes(false));
    document.getElementById("cloze-deck").value = await api().suggest_cloze_deck();
    refreshNoteTypes(true); // Anki may not be open yet: stay quiet, retried on send

    document.getElementById("btn-clear-cache").addEventListener("click", async () => {
        if (!confirm("Clear the local Sefaria cache? Future fetches will re-download from the network.")) return;
        const result = await api().clear_cache();
        document.getElementById("cache-status").textContent = result.cache_status;
        showToast("Cache cleared", false);
    });

    document.getElementById("btn-copy-pointed").addEventListener("click", () => {
        copyText(currentVerseData.map((v) => v.pointed).join("\n"));
    });
    document.getElementById("btn-copy-plain").addEventListener("click", () => {
        copyText(currentVerseData.map((v) => v.plain).join("\n"));
    });
    document.getElementById("btn-copy-cloze").addEventListener("click", () => {
        copyText(document.getElementById("output-box").textContent);
    });

    document.getElementById("btn-stats").addEventListener("click", async () => {
        const maxLeafDisj = parseInt(document.getElementById("max-leaf-disj").value, 10) || 2;
        await api().open_stats_window(maxLeafDisj);
    });
    document.getElementById("btn-anki-tools").addEventListener("click", async () => {
        await api().open_anki_connect_window();
    });

    document.getElementById("lpcg-deck").value = await api().get_lpcg_deck_name();
    setBookOptions(document.getElementById("lpcg-book"), { Tora: cachedBooks.Tora }, false, cachedBookLabels);
    await refreshLpcgParashaDropdowns();
    document.getElementById("lpcg-book").addEventListener("change", refreshLpcgParashaDropdowns);
    document.getElementById("lpcg-start-parasha").addEventListener("change", () => refreshLpcgAliyahDropdown("start"));
    document.getElementById("lpcg-end-parasha").addEventListener("change", () => refreshLpcgAliyahDropdown("end"));
    document.getElementById("btn-export-lpcg").addEventListener("click", () => doExportLpcg(false));
    document.getElementById("btn-export-lpcg-csv").addEventListener("click", () => doExportLpcg(true));
    document.getElementById("btn-export-amud").addEventListener("click", () => doExportAmud(false));
    document.getElementById("btn-export-amud-csv").addEventListener("click", () => doExportAmud(true));

    const updateCardDivisionVisibility = () => {
        const isRowMode = document.getElementById("lpcg-card-division").value === "row";
        document.getElementById("lpcg-row-mode-settings").hidden = !isRowMode;
    };
    updateCardDivisionVisibility();
    document.getElementById("lpcg-card-division").addEventListener("change", updateCardDivisionVisibility);
});
