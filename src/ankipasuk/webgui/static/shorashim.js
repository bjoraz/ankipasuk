// =============================================================
//  Shorashim: words coloured by their root (ankipasuk.shorashim).
//  Shared by the main window's Text view and the statistics window.
//  A word is [text, separator, group]; words of one group share a
//  root (or are one root-less word, in all its forms).
// =============================================================

// Sasha Trubetskoy's 20 distinct colours, in his order: each next one
// as far as it can be from those before. A colour is a background, so
// the dark ones get white text.
const ROOT_PALETTE = [
    "#e6194B", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4", "#42d4f4", "#f032e6",
    "#bfef45", "#fabed4", "#469990", "#dcbeff", "#9A6324", "#fffac8", "#800000", "#aaffc3",
    "#808000", "#ffd8b1", "#000075", "#a9a9a9",
];
const ROOT_PALETTE_DARK = new Set([0, 3, 5, 10, 12, 14, 16, 18]);

// The .hl-N classes, made once from the palette.
(function addRootColourStyles() {
    const style = document.createElement("style");
    style.textContent = ROOT_PALETTE.map((colour, i) =>
        `.hl-${i} { background: ${colour}; color: ${ROOT_PALETTE_DARK.has(i) ? "white" : "black"}; }`).join("\n");
    document.head.appendChild(style);
})();

// A group's name: its letters (א־מ־ר) or word, and where BDB has more
// than one with the same letters, its number, in BDB's order (ל־ח־מ II).
const ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"];
// Where something occurs in the loaded pesuqim, as a strip under its entry:
// a tick at each pasuq it's in (taller where it's there more than once),
// the first pasuq on the right, as the text reads. ``counts`` is a Map of
// pasuq index -> times; ``n`` how many pesuqim are loaded.
function sparklineHtml(counts, n, colour, title) {
    if (!n || !counts.size) return "";
    const w = Math.max(1, n / 180);  // at least about a pixel wide
    const ticks = [...counts].map(([v, times]) => {
        const h = times > 1 ? 1 : 0.6;
        return `<rect x="${n - v - w}" y="${1 - h}" width="${w}" height="${h}"/>`;
    }).join("");
    return `<svg class="spark" viewBox="0 0 ${n} 1" preserveAspectRatio="none" fill="${colour}"`
        + ` data-n="${n}" data-at="${[...counts.keys()].join(",")}"><title>${diagramEscape(title)}</title>${ticks}</svg>`;
}

// The pasuq a click on a sparkline points to: the nearest one with a tick.
function sparklinePasuq(svg, clientX) {
    const r = svg.getBoundingClientRect();
    const n = Number(svg.dataset.n);
    const at = svg.dataset.at.split(",").map(Number);
    const v = Math.floor(((r.right - clientX) / r.width) * n);
    return at.reduce((best, x) => (Math.abs(x - v) < Math.abs(best - v) ? x : best), at[0]);
}

function rootLabelHtml(info) {
    const n = info.number ? ` <span class="root-n">${ROMAN[info.number] || info.number}</span>` : "";
    return diagramEscape(info.display) + n;
}

// What a name is: a people's (חִתִּי, מוֹאָבִי), or a proper name -- not
// just "name" or "people", which are glosses too (שֵׁם, עַם).
function nameKind(info) {
    return info.people ? "name of a people" : "proper name";
}

// A gloss: BDB's, and for some common words a plain meaning beside it
// (shorashim_build.MEANINGS). The meaning comes first and BDB's follows,
// muted -- unless the meaning already says it ("do, make" for "do").
function glossParts(gloss, meaning) {
    if (!meaning) return { main: gloss || "", bdb: "" };
    const said = meaning.toLowerCase().split(/,\s*/);
    return { main: meaning, bdb: gloss && !said.includes(gloss.toLowerCase()) ? gloss : "" };
}

function glossHtml(gloss, meaning) {
    const { main, bdb } = glossParts(gloss, meaning);
    return diagramEscape(main) + (bdb ? ` <span class="bdb" title="BDB's gloss">${diagramEscape(bdb)}</span>` : "");
}

function glossText(gloss, meaning) {
    const { main, bdb } = glossParts(gloss, meaning);
    return bdb ? `${main} (BDB: ${bdb})` : main;
}

// The orders a list of groups goes in: the most used first, or the key
// words first -- those the passage uses far more than the Tanakh as a
// whole (ankipasuk.shorashim.keyness).
const ROOT_ORDERS = {
    count: (a, b) => b.count - a.count || a.display.localeCompare(b.display),
    key: (a, b) => b.keyness - a.keyness || b.count - a.count,
};

// How many times as often as in the Tanakh: "×5.2", "×190".
function ratioText(ratio) {
    return `×${ratio >= 10 ? Math.round(ratio) : ratio.toFixed(1)}`;
}

function rootCountsText(info) {
    const here = `${info.count} ${info.count === 1 ? "time" : "times"} here`;
    if (!info.total) return here;
    return `${here}, ${info.total} in the Tanakh: ${ratioText(info.ratio)} its rate there`;
}

// A word's tooltip: its root (or word) and gloss, and how often it's here
// and in the Tanakh. (A left-to-right mark first, so the line reads as in
// the list: the root, its number, then the gloss.)
function rootTitle(info) {
    const n = info.number ? ` ${ROMAN[info.number] || info.number}` : "";
    const kind = info.kind === "name" ? ` (${nameKind(info)})` : "";
    return `\u200e${info.display}${n} \u00b7 ${glossText(info.gloss, info.meaning)}${kind}\n${rootCountsText(info)}`;
}

// Words get their tooltip when first pointed at, rather than one written
// out for each of a passage's thousands. ``lookup`` gives a group's info.
function addRootTooltips(container, lookup) {
    container.addEventListener("mouseover", (e) => {
        const word = e.target.closest(".w");
        if (!word || word.title) return;
        const info = lookup(word.dataset.g);
        if (info) word.title = rootTitle(info);
    });
}

function stripPointing(text) {
    return text.normalize("NFD").replace(/\p{Mn}/gu, "").replace(/[\u05c3\u05c0]/g, "").normalize("NFC");
}

// One pasuq's words as HTML: each word a span with its index (``data-k``),
// a clickable one where it has a group (``.w``, ``data-g``), and what
// follows it a span too (``data-s``, the word it follows), so a phrase's
// underline can run on between its words; maqaf kept between words, or a
// space for letters only.
function rootWordsHtml(words, plain, extra = {}) {
    return words.map(([text, sep, g, form], k) => {
        const shown = diagramEscape(plain ? stripPointing(text) : text);
        const after = plain && sep === "\u05be" ? " " : sep;
        const between = after ? `<span data-s="${k}">${after}</span>` : "";
        if (!shown.trim()) return shown + between + (extra[k] || "");
        const f = form ? ` data-f="${form}"` : "";  // a verb's form (verbs.js)
        const word = g === null || g === undefined
            ? `<span data-k="${k}"${f}>${shown}</span>` : `<span class="w" data-g="${g}" data-k="${k}"${f}>${shown}</span>`;
        return word + between + (extra[k] || "");
    }).join("");
}

// A Masoretic break, as printed Tanakhs show it: פ for a petuḥa, ס for a
// setuma (see ankipasuk.sections).
function sectionBreakHtml(kind) {
    const [letter, what] = kind === "P" ? ["פ", "Petuḥa: an open section ends here"]
        : ["ס", "Setuma: a closed section ends here"];
    return `<span class="tv-break" title="${what}">${letter}</span>`;
}

// Which roots are coloured, and with which colour: in the order they're
// clicked, each taking the first colour no coloured root has; with all
// twenty in use, the colours go round again. ``onChange`` gets the groups
// that changed.
class RootColours {
    constructor(onChange) {
        this.colours = new Map(); // group -> palette index, in the order clicked
        this.clicks = 0;
        this.onChange = onChange;
    }

    toggle(g) {
        g = String(g);
        if (this.colours.has(g)) {
            this.colours.delete(g);
        } else {
            const used = new Set(this.colours.values());
            let colour = ROOT_PALETTE.findIndex((_c, i) => !used.has(i));
            if (colour < 0) colour = this.clicks % ROOT_PALETTE.length;
            this.colours.set(g, colour);
            this.clicks += 1;
        }
        this.onChange([g]);
    }

    clear() {
        const was = [...this.colours.keys()];
        this.colours.clear();
        this.clicks = 0;
        this.onChange(was);
    }

    // Colour (or uncolour) every element of group ``g`` under ``root``.
    paint(root, g) {
        const colour = this.colours.get(String(g));
        for (const el of root.querySelectorAll(`[data-g="${g}"]`)) setRootColour(el, colour);
    }

    // Colour everything under ``root`` that's coloured (new lines of a
    // lazily filled view).
    paintAll(root) {
        for (const el of root.querySelectorAll("[data-g]")) setRootColour(el, this.colours.get(el.dataset.g));
    }
}

function setRootColour(el, colour) {
    for (const c of [...el.classList]) if (c.startsWith("hl-")) el.classList.remove(c);
    if (colour !== undefined) el.classList.add(`hl-${colour}`);
}
