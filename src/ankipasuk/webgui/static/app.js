"use strict";

let currentVerseData = [];

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

// =============================================================
//  Mode / dropdown wiring
// =============================================================
async function refreshModeVisibility() {
    const isCV = document.getElementById("mode").value === "Chapter / Verse";
    document.getElementById("cv-controls").hidden = !isCV;
    document.getElementById("pa-controls").hidden = isCV;
    if (isCV) {
        await refreshChapterVerseDropdowns();
    } else {
        await refreshParashaDropdown();
    }
}

async function refreshChapterVerseDropdowns() {
    const book = document.getElementById("book").value;
    const chapterCount = await api().get_chapter_count(book);
    const chapters = Array.from({ length: chapterCount }, (_, i) => i + 1);

    setOptions(document.getElementById("start-ch"), chapters, true);
    setOptions(document.getElementById("end-ch"), chapters, true);
    await refreshVerseDropdown("start-ch", "start-vs");
    await refreshVerseDropdown("end-ch", "end-vs");
}

async function refreshVerseDropdown(chSelectId, vsSelectId) {
    const book = document.getElementById("book").value;
    const chapter = parseInt(document.getElementById(chSelectId).value, 10) || 1;
    const verseCount = await api().get_verse_count(book, chapter);
    const verses = Array.from({ length: verseCount }, (_, i) => i + 1);
    setOptions(document.getElementById(vsSelectId), verses, true);
}

async function refreshParashaDropdown() {
    const book = document.getElementById("book").value;
    const parashaSelect = document.getElementById("parasha");
    parashaSelect.innerHTML = "<option>Loading...</option>";
    const result = await api().get_parashot(book);
    if (!result.ok) {
        showToast("Could not load parashot: " + result.error, true);
        parashaSelect.innerHTML = "";
        return;
    }
    setOptions(parashaSelect, result.names, false);
    await refreshAliyahDropdown();
}

async function refreshAliyahDropdown() {
    const book = document.getElementById("book").value;
    const parasha = document.getElementById("parasha").value;
    if (!parasha) return;
    const result = await api().get_aliyah_count(book, parasha);
    if (!result.ok) {
        showToast("Could not load aliyot: " + result.error, true);
        return;
    }
    const aliyot = Array.from({ length: result.count }, (_, i) => i + 1);
    setOptions(document.getElementById("aliyah"), aliyot, true);
}

// =============================================================
//  Fetching verses
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

async function doFetch() {
    const btn = document.getElementById("btn-fetch");
    btn.disabled = true;
    btn.textContent = "Fetching...";
    try {
        const book = document.getElementById("book").value;
        const mode = document.getElementById("mode").value;
        let result;
        if (mode === "Chapter / Verse") {
            const startCh = parseInt(document.getElementById("start-ch").value, 10);
            const startVs = parseInt(document.getElementById("start-vs").value, 10);
            const endCh = parseInt(document.getElementById("end-ch").value, 10);
            const endVs = parseInt(document.getElementById("end-vs").value, 10);
            result = await api().fetch_chapter_verse(book, startCh, startVs, endCh, endVs);
        } else {
            const parasha = document.getElementById("parasha").value;
            const aliyah = parseInt(document.getElementById("aliyah").value, 10);
            result = await api().fetch_parashah_aliyah(book, parasha, aliyah);
        }

        if (!result.ok) {
            showToast("Fetch failed: " + result.error, true);
            return;
        }
        currentVerseData = result.verses;
        renderVerseBoxes();
        document.getElementById("cache-status").textContent = result.cache_status;
    } finally {
        btn.disabled = false;
        btn.textContent = "Fetch range from Sefaria";
    }
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
    const books = await api().get_books();
    setOptions(document.getElementById("book"), books, false);
    document.getElementById("cache-status").textContent = await api().get_cache_status();
    await refreshModeVisibility();

    document.getElementById("mode").addEventListener("change", refreshModeVisibility);
    document.getElementById("book").addEventListener("change", refreshModeVisibility);
    document.getElementById("start-ch").addEventListener("change", () => refreshVerseDropdown("start-ch", "start-vs"));
    document.getElementById("end-ch").addEventListener("change", () => refreshVerseDropdown("end-ch", "end-vs"));
    document.getElementById("parasha").addEventListener("change", refreshAliyahDropdown);

    document.getElementById("btn-fetch").addEventListener("click", doFetch);
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
