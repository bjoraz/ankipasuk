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

// The pesuqim with one root's words in them, as text, those words coloured.
async function showRootPopup(row) {
    const verses = await api().get_shorashim_verses(Number(row.g));
    let html = `<div class="modal-overlay" id="modal-overlay"><div class="modal">`;
    html += `<h3 dir="auto">${rootLabelHtml(row)} <span class="muted">${glossHtml(row.gloss, row.meaning)}</span></h3>`;
    html += `<div class="muted">${row.count} time(s), in ${verses.length} pasuq/pesuqim`
        + `${row.total ? `; ${row.total} in the Tanakh, ${ratioText(row.ratio)} its rate there` : ""}</div>`;
    for (const v of verses) {
        html += `<div class="verse-ref">${escapeHtml(v.ref)}</div><div class="verse-text pasuq-text">${rootWordsHtml(v.words, false)}</div>`;
    }
    html += `<button id="modal-close">Close</button></div></div>`;
    document.getElementById("verse-modal").innerHTML = html;
    for (const el of document.querySelectorAll(`#verse-modal [data-g="${row.g}"]`)) el.classList.add("hl-0");
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
//  Shorashim: every root in the loaded pesuqim, the most used or the key
//  words first
// =============================================================
async function loadShorashim() {
    const rows = await api().get_shorashim();
    const byGroup = new Map(rows.map((r) => [String(r.g), r]));
    const container = document.getElementById("shorashim-content");
    const render = () => {
        const particles = document.getElementById("sh-particles").checked;
        const names = document.getElementById("sh-names").checked;
        const byKey = document.getElementById("sh-sort").value === "key";
        const shown = rows.filter((r) => (particles || r.kind !== "particle") && (names || r.kind !== "name"))
            .sort(ROOT_ORDERS[byKey ? "key" : "count"]);
        // The bar: how often, or how key (none for a word used less than in the Tanakh).
        const size = (r) => (byKey ? Math.max(r.keyness, 0) : r.count);
        const max = Math.max(...shown.map(size), 1);
        container.innerHTML = shown.map((r) => {
            const words = r.words.map(([w, gloss, meaning]) => `${w} ${glossText(gloss, meaning)}`).join(" · ");
            const ratio = byKey && r.total
                ? ` · <span class="ratio${r.keyness > 0 ? "" : " under"}">${ratioText(r.ratio)}</span>` : "";
            return `<div class="bar-row sh-row" data-i="${rows.indexOf(r)}"
                title="${escapeHtml(`${words}\n${rootCountsText(r)}`)}">
                <div class="bar-label"><span class="root-label">${rootLabelHtml(r)}</span></div>
                <div class="sh-gloss">${glossHtml(r.gloss, r.meaning)}${r.kind === "name" ? " (proper name)" : ""}</div>
                <div class="bar-track"><div class="bar-fill" style="width:${(size(r) / max) * 100}%"></div></div>
                <div class="bar-count">${r.count} in ${r.pesuqim}${ratio}</div></div>`;
        }).join("") || "<div class='muted'>None.</div>";
        if (shown.length) {
            const legend = byKey ? "times in pesuqim · × the Tanakh's rate" : "times in pesuqim";
            container.innerHTML = `<div class="muted" style="text-align:right">${shown.length} shown · ${legend}</div>`
                + container.innerHTML;
        }
    };
    render();
    container.addEventListener("click", (e) => {
        const el = e.target.closest(".sh-row");
        if (el) showRootPopup(rows[Number(el.dataset.i)]);
    });
    document.getElementById("sh-particles").addEventListener("change", render);
    document.getElementById("sh-names").addEventListener("change", render);
    document.getElementById("sh-sort").addEventListener("change", render);
    addRootTooltips(document.getElementById("verse-modal"), (g) => byGroup.get(g));
}

// =============================================================
//  Phrases: refrains, echoes, idioms, and formulas (ankipasuk.phrases)
// =============================================================
async function loadPhrases() {
    const container = document.getElementById("phrases-content");
    container.innerHTML = "<p class='muted'>Finding phrases…</p>";
    const result = await api().get_phrases();
    if (!result.ok) {
        container.innerHTML = `<p class="muted">No phrases: ${escapeHtml(result.error)}</p>`;
        return;
    }
    const P = result.phrases;
    const row = (id, kind, child) => {
        const p = P[id];
        const also = phraseAlso(p, kind).map((a) => ` <span class="ph-tag">${a}</span>`).join("");
        let info = kind === "echo" ? p.places.map((x) => x.ref).join(", ")
            : kind === "idiom" ? `in ${p.chapters} chapters of ${p.books} ${p.books === 1 ? "book" : "books"}` : "";
        if (p.variant) info += (info ? " · " : "") + "a rare wording of God's name";
        return `<div class="ph-row${child ? " ph-child" : ""}" data-id="${id}" title="${diagramEscape(phraseTitle(p))}">`
            + `<div class="ph-text">${escapeHtml(phraseShort(p.text, 16))}</div>`
            + `<div class="ph-count">${p.here} / ${p.total}</div>`
            + `<div class="ph-info">${escapeHtml(info)}${also}</div></div>`
            + (child ? "" : (p.children[kind] || []).map((k) => row(k, kind, true)).join(""));
    };
    let html = '<div class="muted" style="text-align:right">times here / in the Tanakh</div>';
    for (const [kind, name, about] of PHRASE_SECTIONS) {
        const ids = result.sections[kind];
        html += `<details class="ph-sec" open><summary>${name} <span class="muted">${ids.length} · ${about}</span></summary>`
            + (ids.map((id) => row(id, kind, false)).join("") || "<div class='muted'>None.</div>") + "</details>";
    }
    const formulas = result.sections.formula;
    const count = formulas.reduce((n, [, ids]) => n + ids.length, 0);
    html += `<details class="ph-sec"><summary>Formulas <span class="muted">${count} · Phrases that only frame: `
        + "who speaks, a name, a number, God's names</span></summary>"
        + formulas.map(([name, ids]) => `<div class="ph-class">${escapeHtml(name)}</div>`
            + ids.map((id) => row(id, "formula", false)).join("")).join("") + "</details>";
    container.innerHTML = html;
    container.addEventListener("click", (e) => {
        const el = e.target.closest(".ph-row");
        if (el) showPhrasePopup(P[Number(el.dataset.id)]);
    });
}

// A phrase's pesuqim here, its words highlighted; then, once fetched, its
// other places.
let phrasePopup = 0;
async function showPhrasePopup(p) {
    const mine = ++phrasePopup;
    const verses = await api().get_phrase_verses(p.id);
    const elsewhere = p.total - p.here;
    let html = `<div class="modal-overlay" id="modal-overlay"><div class="modal">`;
    html += `<h3 class="pasuq-text" dir="rtl">${escapeHtml(phraseShort(p.text, 30))}</h3>`;
    html += `<div class="muted">${escapeHtml(phraseTitle(p)).replace(/\n/g, "<br>")}</div>`;
    for (const v of verses) {
        html += `<div class="verse-ref">${escapeHtml(v.ref)}</div><div class="verse-text pasuq-text">${markedWordsHtml(v.words)}</div>`;
    }
    if (elsewhere > 0) html += `<h4>Elsewhere</h4><div id="phrase-places" class="muted">Fetching from Sefaria…</div>`;
    html += `<button id="modal-close">Close</button></div></div>`;
    document.getElementById("verse-modal").innerHTML = html;
    document.getElementById("modal-overlay").addEventListener("click", (e) => {
        if (e.target.id === "modal-overlay") closeModal();
    });
    document.getElementById("modal-close").addEventListener("click", closeModal);
    if (elsewhere <= 0) return;
    const result = await api().get_phrase_places(p.id);
    const box = document.getElementById("phrase-places");
    if (mine !== phrasePopup || !box) return;  // closed, or another opened meanwhile
    box.classList.remove("muted");
    box.innerHTML = result.places.map((place) => `<div class="verse-ref">${escapeHtml(place.ref)}</div>`
        + (place.error ? `<div class="muted">${escapeHtml(place.error)}</div>`
            : `<div class="verse-text pasuq-text">${markedWordsHtml(place.words)}</div>`)).join("")
        + (result.more ? `<div class="muted">and ${result.more} more</div>` : "");
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
    await loadShorashim();
    await loadPhrases();

    document.getElementById("btn-export-stats-csv").addEventListener("click", async () => {
        const result = await api().export_csv();
        if (!result.ok) {
            if (result.error) alert(result.error);
            return;
        }
        alert("Exported to " + result.path);
    });
});
