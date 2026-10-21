// =============================================================
//  Phrases (ankipasuk.phrases): a passage's recurring word sequences,
//  in sections -- refrains, echoes, idioms, and formulas set apart.
//  Shared by the main window's Text view and the statistics window.
//  A phrase is {id, kinds, formula, variant, text, here, total, places,
//  chapters, books, marks: [[pasuq, word]], verses, children}.
// =============================================================

const PHRASE_SECTIONS = [
    ["refrain", "Refrains", "Repeated here more often than chance would give"],
    ["echo", "Echoes", "Shared with one to three other places in the Tanakh"],
    ["idiom", "Idioms", "Fixed expressions, used across the Tanakh"],
];

// A long phrase shortened: its first words … its last, and how many.
function phraseShort(text, max = 9) {
    const words = text.split(" ");
    if (words.length <= max) return text;
    return `${words.slice(0, 5).join(" ")} … ${words.slice(-3).join(" ")} (${words.length} words)`;
}

// What a phrase's entry says when pointed at.
function phraseTitle(p) {
    const lines = [`${p.here} ${p.here === 1 ? "time" : "times"} here, ${p.total} in the Tanakh`];
    if (p.kinds.includes("echo") && p.places.length) lines.push(`Also: ${p.places.map((x) => x.ref).join(", ")}`);
    if (p.kinds.includes("idiom")) lines.push(`In ${p.chapters} chapters of ${p.books} ${p.books === 1 ? "book" : "books"}`);
    if (p.variant) lines.push("A rare wording of God's name");
    if (p.formula) lines.push(`A formula: ${p.formula}`);
    return lines.join("\n");
}

// The sections a phrase is also in, besides ``kind``.
function phraseAlso(p, kind) {
    const names = { refrain: "refrain", echo: "echo", idiom: "idiom" };
    return p.kinds.filter((k) => k !== kind).map((k) => names[k]);
}

// Words ([text, separator, (group,) marked]) as HTML, the marked ones
// highlighted.
function markedWordsHtml(words) {
    return words.map((w) => {
        const [text, sep] = w;
        const marked = w[w.length - 1];
        const shown = diagramEscape(text);
        return (marked ? `<span class="hl-0">${shown}</span>` : shown) + sep;
    }).join("");
}

// Which phrases are underlined, in which colour: as RootColours (click
// order, the first free colour of the same palette), but marking words
// -- ``[pasuq, word]`` -- under each line of the text (``.tv-line``,
// ``data-i`` its pasuq; a word ``[data-k]``).
class PhraseMarks {
    constructor(onChange) {
        this.colours = new Map(); // phrase id -> palette index
        this.clicks = 0;
        this.phrases = [];
        this.byWord = new Map(); // "pasuq:word" -> [palette index, ...]
        this.onChange = onChange;
    }

    use(phrases) {
        this.phrases = phrases || [];
        this.colours.clear();
        this.clicks = 0;
        this.byWord.clear();
    }

    toggle(id) {
        id = Number(id);
        if (this.colours.has(id)) {
            this.colours.delete(id);
        } else {
            const used = new Set(this.colours.values());
            let colour = ROOT_PALETTE.findIndex((_c, i) => !used.has(i));
            if (colour < 0) colour = this.clicks % ROOT_PALETTE.length;
            this.colours.set(id, colour);
            this.clicks += 1;
        }
        this._index();
        this.onChange(this.phrases[id] ? this.phrases[id].marks : []);
    }

    clear() {
        const words = [...this.byWord.keys()].map((key) => key.split(":").map(Number));
        this.colours.clear();
        this.clicks = 0;
        this.byWord.clear();
        this.onChange(words);
    }

    _index() {
        this.byWord.clear();
        for (const [id, colour] of this.colours) {
            for (const [v, k] of this.phrases[id].marks) {
                const key = `${v}:${k}`;
                if (!this.byWord.has(key)) this.byWord.set(key, []);
                this.byWord.get(key).push(colour);
            }
        }
    }

    // Underline ``words`` ([pasuq, word]) under ``root``, as they now are.
    paint(root, words) {
        for (const [v, k] of words) {
            const el = root.querySelector(`.tv-line[data-i="${v}"] [data-k="${k}"]`);
            if (el) setPhraseUnderline(el, this.byWord.get(`${v}:${k}`));
        }
    }

    // Every word of these lines (new lines of a lazily filled view).
    paintLines(lines) {
        for (const line of lines) {
            const v = line.dataset.i;
            for (const el of line.querySelectorAll("[data-k]")) setPhraseUnderline(el, this.byWord.get(`${v}:${el.dataset.k}`));
        }
    }
}

// One underline per phrase, 3px each, stacked below the word (an outer
// shadow shows only outside the word's box, and the first is on top).
function setPhraseUnderline(el, colours) {
    el.style.boxShadow = colours && colours.length
        ? colours.map((c, i) => `0 ${3 * (i + 1)}px 0 0 ${ROOT_PALETTE[c]}`).join(", ")
        : "";
}
