"use strict";

let currentVerseData = [];
let cachedBooks = null; // {"Torah": [...], "Nevi'im": [...], "Megillot": [...]}

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

function setOptions(select, values, keepSelection) {
    const prev = select.value;
    select.innerHTML = "";
    for (const v of values) {
        const opt = document.createElement("option");
        opt.value = String(v);
        opt.textContent = String(v);
        select.appendChild(opt);
    }
    if (keepSelection && values.map(String).includes(prev)) {
        select.value = prev;
    }
}

function setBookOptions(select, booksByCategory, keepSelection) {
    const prev = select.value;
    select.innerHTML = "";
    for (const [category, books] of Object.entries(booksByCategory)) {
        const group = document.createElement("optgroup");
        group.label = category;
        for (const b of books) {
            const opt = document.createElement("option");
            opt.value = b;
            opt.textContent = b;
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
//  book/mode/chapter-verse-or-parashah-aliyah picker. Multiple rows can
//  be fetched together and their verses concatenate in the order
//  they're listed (see doFetchAll).
// =============================================================
const RANGE_ROW_TEMPLATE = `
  <div class="row">
    <label>Mode:
      <select class="range-mode">
        <option>Chapter / Verse</option>
        <option>Parashah / Aliyah</option>
      </select>
    </label>
    <label>Book:
      <select class="range-book"></select>
    </label>

    <span class="range-cv-controls inline-group">
      <label>Start chapter: <select class="range-start-ch"></select></label>
      <label>Start verse: <select class="range-start-vs"></select></label>
      <label>End chapter: <select class="range-end-ch"></select></label>
      <label>End verse: <select class="range-end-vs"></select></label>
    </span>

    <span class="range-pa-controls inline-group" hidden>
      <label>Parashah: <select class="range-parasha"></select></label>
      <label>Aliyah: <select class="range-aliyah"></select></label>
    </span>

    <button class="btn-remove-range" type="button" title="Remove this range">Remove</button>
  </div>
`;

async function onRangeModeChange(row) {
    const isCV = row.querySelector(".range-mode").value === "Chapter / Verse";
    row.querySelector(".range-cv-controls").hidden = !isCV;
    row.querySelector(".range-pa-controls").hidden = isCV;

    // Parashah/Aliyah only exists for Torah -- restrict the book list to
    // Torah so an invalid (book, mode) combination can't be selected at
    // all, rather than only failing later when fetched.
    const books = isCV ? cachedBooks : { Torah: cachedBooks.Torah };
    setBookOptions(row.querySelector(".range-book"), books, true);

    await onRangeBookChange(row);
}

async function onRangeBookChange(row) {
    const isCV = row.querySelector(".range-mode").value === "Chapter / Verse";
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
        showToast("Could not load parashot: " + result.error, true);
        parashaSelect.innerHTML = "";
        return;
    }
    setOptions(parashaSelect, result.names, false);
    await refreshRangeAliyahDropdown(row);
}

async function refreshRangeAliyahDropdown(row) {
    const book = row.querySelector(".range-book").value;
    const parasha = row.querySelector(".range-parasha").value;
    if (!parasha) return;
    const result = await api().get_aliyah_count(book, parasha);
    if (!result.ok) {
        showToast("Could not load aliyot: " + result.error, true);
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
        renderVerseBoxes();

        const rows = document.querySelectorAll(".range-row");
        for (const row of rows) {
            const book = row.querySelector(".range-book").value;
            const mode = row.querySelector(".range-mode").value;
            let result;
            if (mode === "Chapter / Verse") {
                const startCh = parseInt(row.querySelector(".range-start-ch").value, 10);
                const startVs = parseInt(row.querySelector(".range-start-vs").value, 10);
                const endCh = parseInt(row.querySelector(".range-end-ch").value, 10);
                const endVs = parseInt(row.querySelector(".range-end-vs").value, 10);
                result = await api().fetch_chapter_verse(book, startCh, startVs, endCh, endVs);
            } else {
                const parasha = row.querySelector(".range-parasha").value;
                const aliyah = parseInt(row.querySelector(".range-aliyah").value, 10);
                result = await api().fetch_parashah_aliyah(book, parasha, aliyah);
            }

            if (!result.ok) {
                showToast("Fetch failed: " + result.error, true);
                return; // whatever ranges succeeded before this one stay visible
            }
            currentVerseData = result.verses;
            renderVerseBoxes();
            document.getElementById("cache-status").textContent = result.cache_status;
        }
    } finally {
        btn.disabled = false;
        btn.textContent = "Fetch all ranges";
    }
}

async function doClearRanges() {
    const result = await api().clear_ranges();
    currentVerseData = result.verses;
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
    addRangeRow(); // start with exactly one range row
    document.getElementById("cache-status").textContent = await api().get_cache_status();

    document.getElementById("btn-add-range").addEventListener("click", addRangeRow);
    document.getElementById("btn-fetch").addEventListener("click", doFetchAll);
    document.getElementById("btn-clear-ranges").addEventListener("click", doClearRanges);

    document.getElementById("btn-generate").addEventListener("click", doGenerate);
    document.getElementById("btn-export-csv").addEventListener("click", doExportCsv);

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
});
