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

function showVersePopup(title, labels) {
    const sorted = [...new Set(labels)].sort((a, b) => {
        const pa = parseVerseLabel(a);
        const pb = parseVerseLabel(b);
        return pa.book.localeCompare(pb.book) || pa.ch - pb.ch || pa.vs - pb.vs;
    });
    let html = `<div class="modal-overlay" id="modal-overlay"><div class="modal">`;
    html += `<h3>${title}</h3><div class="muted">${sorted.length} verse(s)</div>`;
    for (const label of sorted) {
        const entry = verseLookup[label];
        html += `<div class="verse-ref">${label}</div>`;
        html += `<div class="verse-text">${entry ? escapeHtml(entry.pointed) : "(text unavailable)"}</div>`;
    }
    html += `<button id="modal-close">Close</button></div></div>`;
    document.getElementById("verse-modal").innerHTML = html;
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
//  By chapter
// =============================================================
async function loadChapterData() {
    const data = await api().get_chapter_data();
    const container = document.getElementById("chapter-content");
    const maxWords = Math.max(...data.chapters.map((c) => c.avg_words), 1);
    let html = "";
    for (const c of data.chapters) {
        const pct = (c.avg_words / maxWords) * 100;
        const key = `${c.book} ${c.chapter}`;
        html += `<div class="bar-row" data-verses='${JSON.stringify(c.verses)}' data-key="${key}">
            <div class="bar-label">${c.book} Ch ${c.chapter}</div>
            <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
            <div class="bar-count">${c.avg_words.toFixed(1)}w / ${c.avg_disj.toFixed(1)}dg</div>
        </div>`;
    }
    container.innerHTML = html;
    for (const row of container.querySelectorAll(".bar-row")) {
        row.addEventListener("click", () => {
            const verses = JSON.parse(row.dataset.verses);
            showVersePopup(`Chapter ${row.dataset.key}`, verses);
        });
    }
}

// =============================================================
//  Trope frequency
// =============================================================
async function loadTropeFrequency() {
    const tropes = await api().get_trope_frequency();
    const container = document.getElementById("trope-content");
    let html = "<div>Click a trope to see which verses contain it.</div><br>";
    for (const t of tropes) {
        html += `<div class="trope-row" data-verses='${JSON.stringify(t.verses)}' data-name="${t.name}">
            ${t.name}: ${t.count}</div>`;
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
function renderStructureGroups(container, groups, axisLabel) {
    let html = "<div>Click a structure to see its verses.</div>";
    for (const group of groups) {
        html += `<div class="axis-header">${axisLabel} = ${group.axis_value} (${group.structures.reduce((a, s) => a + s.count, 0)} verses)</div>`;
        for (const s of group.structures) {
            html += `<div class="struct-line" data-verses='${JSON.stringify(s.verses)}'>&nbsp;&nbsp;${s.label} &times;${s.count}</div>`;
        }
    }
    container.innerHTML = html;
    for (const row of container.querySelectorAll(".struct-line")) {
        row.addEventListener("click", () => {
            showVersePopup("Structure", JSON.parse(row.dataset.verses));
        });
    }
}

async function loadStructure() {
    const container = document.getElementById("structure-content");

    async function showSubtab(key) {
        if (key === "by-word-count") {
            renderStructureGroups(container, await api().get_structure_by_word_count(), "Words in verse");
        } else if (key === "by-disj-count") {
            renderStructureGroups(container, await api().get_structure_by_disj_count(), "Disjunctive groups");
        } else {
            const summary = await api().get_structure_summary();
            let html = "<div>Most common verse shapes, most-shared first.</div><br>";
            for (const s of summary) {
                html += `<div class="struct-line" data-verses='${JSON.stringify(s.verses)}'>${s.label} &times;${s.count}</div>`;
            }
            container.innerHTML = html;
            for (const row of container.querySelectorAll(".struct-line")) {
                row.addEventListener("click", () => showVersePopup("Structure", JSON.parse(row.dataset.verses)));
            }
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
    verseLookup = await api().get_verse_lookup();
    document.getElementById("summary-text").textContent = await api().get_summary();

    for (const btn of document.querySelectorAll("#tabs .tab-btn")) {
        btn.addEventListener("click", () => switchTab(btn.dataset.tab));
    }
    switchTab("summary");

    await loadDistributions();
    await loadChapterData();
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
