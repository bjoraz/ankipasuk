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

function stripPointing(text) {
    return text.normalize("NFD").replace(/\p{Mn}/gu, "").replace(/[\u05c3\u05c0]/g, "").normalize("NFC");
}

// One pasuq's words as HTML: each word with a group a clickable span
// (``data-g``); maqaf kept between words, or a space for letters only.
function rootWordsHtml(words, plain) {
    return words.map(([text, sep, g]) => {
        const shown = diagramEscape(plain ? stripPointing(text) : text);
        const after = plain && sep === "\u05be" ? " " : sep;
        const word = g === null || g === undefined || !shown.trim()
            ? shown : `<span class="w" data-g="${g}">${shown}</span>`;
        return word + after;
    }).join("");
}

// Which roots are coloured, and with which colour: in the order they're
// clicked, each taking the first colour no coloured root has; with all
// twenty in use, the colours go round again.
class RootColours {
    constructor(onChange) {
        this.colours = new Map(); // group -> palette index
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
        this.onChange(g);
    }

    clear() {
        const was = [...this.colours.keys()];
        this.colours.clear();
        this.clicks = 0;
        for (const g of was) this.onChange(g);
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
