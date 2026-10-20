"use strict";

function api() {
    return window.pywebview.api;
}

let verseLookup = {};

function switchTab(tabId) {
    for (const btn of document.querySelectorAll("#tabs .tab-btn")) {
        btn.classList.toggle("active", btn.dataset.tab === tabId);
    }
    for (const panel of document.querySelectorAll(".tab-panel")) {
        panel.classList.toggle("active", panel.dataset.panel === tabId);
    }
}

function switchSubtab(container, subtabId) {
    for (const btn of container.querySelectorAll(".subtab-btn")) {
        btn.classList.toggle("active", btn.dataset.subtab === subtabId);
    }
}

// =============================================================
//  Verse popup
// =============================================================
function parseVerseLabel(label) {
    // Labels are "book ch:vs" (e.g. "Genesis 1:1", "I Samuel 3:16") --
    // book can itself contain spaces, so split off the trailing
    // "ch:vs" token rather than splitting on the first space.
    const m = label.match(/^(.*) (\d+):(\d+)$/);
    if (!m) return { book: "", ch: 0, vs: 0 };
    return { book: m[1], ch: Number(m[2]), vs: Number(m[3]) };
}

// The pesuqim behind a bar or row, each drawn as its diagram (diagram.js).
async function showVersePopup(title, labels) {
    const sorted = [...new Set(labels)].sort((a, b) => {
        const pa = parseVerseLabel(a);
        const pb = parseVerseLabel(b);
        return pa.book.localeCompare(pb.book) || pa.ch - pb.ch || pa.vs - pb.vs;
    });
    let html = `<div class="modal-overlay" id="modal-overlay"><div class="modal">`;
    html += `<h3>${escapeHtml(title)}</h3><div class="muted">${sorted.length} verse(s)</div>`;
    html += `<div id="modal-diagrams"></div><button id="modal-close">Close</button></div></div>`;
    document.getElementById("verse-modal").innerHTML = html;
    // The modal box is what scrolls, so it's what the lazy drawing watches.
    renderDiagrams(document.getElementById("modal-diagrams"), await api().get_diagrams(sorted),
        document.querySelector("#verse-modal .modal"));
    document.getElementById("modal-overlay").addEventListener("click", (e) => {
        if (e.target.id === "modal-overlay") closeModal();
    });
    document.getElementById("modal-close").addEventListener("click", closeModal);
}

function closeModal() {
    document.getElementById("verse-modal").innerHTML = "";
}

function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
}

// =============================================================
//  Bar chart rendering
// =============================================================
function renderBarChart(container, bars, axisLabel) {
    const maxCount = Math.max(...bars.map((b) => b.count), 1);
    let html = "";
    for (const bar of bars) {
        const pct = (bar.count / maxCount) * 100;
        html += `<div class="bar-row" data-verses='${JSON.stringify(bar.verses)}' data-key="${bar.key}">
            <div class="bar-label">${bar.key}</div>
            <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
            <div class="bar-count">${bar.count}</div>
        </div>`;
    }
    container.innerHTML = html;
    for (const row of container.querySelectorAll(".bar-row")) {
        row.addEventListener("click", () => {
            const verses = JSON.parse(row.dataset.verses);
            if (!verses.length) return;  // an empty bin, kept to show the gap
            showVersePopup(`${axisLabel} = ${row.dataset.key}`, verses);
        });
    }
}

async function loadDistributions() {
    const distributions = await api().get_distributions();
    const labels = {
        word_count: "Words in verse",
        disj_count: "Minimum disjunctive groups",
        clause_count: `Cloze clauses (max ${distributions.max_leaf_disj}/leaf)`,
        depth: `Split-tree depth (max ${distributions.max_leaf_disj}/leaf)`,
        ratio: "Words per disjunctive group",
    };

    function showSubtab(key) {
        const content = document.getElementById("dist-content");
        renderBarChart(content, distributions[key], labels[key]);
    }

    const subtabs = document.getElementById("dist-subtabs");
    for (const btn of subtabs.querySelectorAll(".subtab-btn")) {
        btn.addEventListener("click", () => {
            switchSubtab(subtabs, btn.dataset.subtab);
            showSubtab(btn.dataset.subtab);
        });
    }
    subtabs.querySelector(".subtab-btn").classList.add("active");
    showSubtab("word_count");
}

// =============================================================
//  Mafsiqim (how often each ta'am occurs)
// =============================================================
async function loadTropeFrequency() {
    const tropes = await api().get_trope_frequency();
    const container = document.getElementById("trope-content");
    // Labelled as in the diagrams: Hebrew name, coloured by rank, rank 1 first.
    const maxCount = Math.max(...tropes.map((t) => t.count), 1);
    let html = "<div>Click a ta'am to see which verses contain it.</div>";
    let rank = null;
    for (const t of tropes) {
        if (t.rank !== rank) {
            rank = t.rank;
            html += `<div class="axis-header">${rank ? `Rank ${rank}` : "Other"}</div>`;
        }
        const pct = (t.count / maxCount) * 100;
        html += `<div class="bar-row trope-row" data-verses='${JSON.stringify(t.verses)}' data-name="${escapeHtml(t.hebrew)}">
            <div class="bar-label wide"><span class="taam-chip dg-r${t.rank}" title="${escapeHtml(t.name)}">${escapeHtml(t.hebrew)}</span></div>
            <div class="bar-track"><div class="bar-fill dg-r${t.rank}" style="width:${pct}%"></div></div>
            <div class="bar-count">${t.count}</div></div>`;
    }
    container.innerHTML = html;
    for (const row of container.querySelectorAll(".trope-row")) {
        row.addEventListener("click", () => {
            const verses = JSON.parse(row.dataset.verses);
            showVersePopup(row.dataset.name, verses);
        });
    }
}

// =============================================================
//  Structure
// =============================================================
// Each structure: how many pesuqim share it, its signature and the diagram
// of its first pasuq; click for them all. Lazily, as the page scrolls: there can be
// hundreds.
function structureHtml(s) {
    if (s.header) return `<div class="axis-header">${escapeHtml(s.header)}</div>`;
    // The signature goes on the diagram's reference line, taking no width
    // from the diagram itself.
    const html = diagramHtml(s.example.diagram, s.example.ref).replace(
        '<div class="dg-ref">', `<div class="dg-ref"><span class="struct-sig">${escapeHtml(s.label)}</span>`);
    return `<div class="struct-entry"><div class="struct-count">&times;${s.count}</div>${html}</div>`;
}

function renderStructures(container, items) {
    lazyFill(container, items, structureHtml, (entries) => {
        for (const el of entries) {
            const s = items[Number(el.dataset.i)];
            if (s.header) continue;
            if (!el.dataset.bound) {
                el.dataset.bound = "1";
                el.addEventListener("click", () => showVersePopup(`Structure ×${s.count}`, s.verses));
            }
        }
        drawUnits(entries.flatMap((el) => [...el.querySelectorAll(".dg-inner")]));
    }, null, true);
}

function groupedStructures(groups, axisLabel) {
    return groups.flatMap((g) => [
        { header: `${axisLabel} = ${g.axis_value} (${g.structures.reduce((a, s) => a + s.count, 0)} verses)` },
        ...g.structures,
    ]);
}

async function loadStructure() {
    const container = document.getElementById("structure-content");

    async function showSubtab(key) {
        if (key === "by-word-count") {
            renderStructures(container, groupedStructures(await api().get_structure_by_word_count(), "Words in verse"));
        } else if (key === "by-disj-count") {
            renderStructures(container, groupedStructures(await api().get_structure_by_disj_count(), "Disjunctive groups"));
        } else {
            renderStructures(container, await api().get_structure_summary());
        }
    }

    const subtabButtons = document.querySelectorAll('[data-panel="structure"] .subtab-btn');
    for (const btn of subtabButtons) {
        btn.addEventListener("click", () => {
            for (const b of subtabButtons) b.classList.toggle("active", b === btn);
            showSubtab(btn.dataset.subtab);
        });
    }
    subtabButtons[0].classList.add("active");
    await showSubtab("by-word-count");
}

// =============================================================
//  Wiring
// =============================================================
window.addEventListener("pywebviewready", async () => {
    const fontStyle = document.createElement("style");  // the STAM font, for the diagrams
    fontStyle.textContent = await api().get_font_css();
    document.head.appendChild(fontStyle);
    verseLookup = await api().get_verse_lookup();
    document.getElementById("summary-text").textContent = await api().get_summary();

    for (const btn of document.querySelectorAll("#tabs .tab-btn")) {
        btn.addEventListener("click", () => switchTab(btn.dataset.tab));
    }
    switchTab("summary");

    await loadDistributions();
    await loadTropeFrequency();
    await loadStructure();

    document.getElementById("btn-export-stats-csv").addEventListener("click", async () => {
        const result = await api().export_csv();
        if (!result.ok) {
            if (result.error) alert(result.error);
            return;
        }
        alert("Exported to " + result.path);
    });
});
