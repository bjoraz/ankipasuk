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
// ``data-i`` its pasuq; a word ``[data-k]``, what follows it ``[data-s]``).
// Each picked phrase keeps one track, the first no phrase sharing a word
// with it has, so its line stays at one depth from its first word to its
// last, and runs on between them.
class PhraseMarks {
    constructor(onChange) {
        this.colours = new Map(); // phrase id -> palette index
        this.clicks = 0;
        this.phrases = [];
        this.byWord = new Map(); // "pasuq:word" -> phrase ids, by track (sparse)
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
        const before = [...this.byWord.keys()];
        this._index();
        this.onChange([...new Set([...before, ...this.byWord.keys()])].map((key) => key.split(":").map(Number)));
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
        const placed = []; // [track, Set of "pasuq:word"]
        for (const id of this.colours.keys()) {
            const words = new Set(this.phrases[id].marks.map(([v, k]) => `${v}:${k}`));
            let track = 0;
            while (placed.some(([t, ws]) => t === track && [...words].some((w) => ws.has(w)))) track += 1;
            placed.push([track, words]);
            for (const w of words) {
                if (!this.byWord.has(w)) this.byWord.set(w, []);
                this.byWord.get(w)[track] = id;
            }
        }
    }

    // Underline the lines with ``words`` ([pasuq, word]) under ``root``.
    paint(root, words) {
        for (const v of new Set(words.map(([pasuq]) => pasuq))) {
            const line = root.querySelector(`.tv-line[data-i="${v}"]`);
            if (line) this.paintLines([line]);
        }
    }

    // Every word of these lines (new lines of a lazily filled view), and
    // what's between two words of the same phrase.
    paintLines(lines) {
        for (const line of lines) {
            const v = line.dataset.i;
            for (const el of line.querySelectorAll("[data-k]")) this._underline(el, this.byWord.get(`${v}:${el.dataset.k}`));
            for (const el of line.querySelectorAll("[data-s]")) {
                const k = Number(el.dataset.s);
                const here = this.byWord.get(`${v}:${k}`), next = this.byWord.get(`${v}:${k + 1}`);
                this._underline(el, here && next ? here.map((id, t) => (next[t] === id ? id : undefined)) : null);
            }
        }
    }

    // A 3px line per track below the element: the phrase's colour where it
    // has one, the page's white where not (an outer shadow shows only
    // outside the element's box, and the first is on top).
    _underline(el, ids) {
        const tracks = ids ? ids.map((id) => (id === undefined ? undefined : this.colours.get(id))) : [];
        if (!tracks.some((c) => c !== undefined)) {
            el.style.boxShadow = "";
            el.style.borderRadius = "";
            return;
        }
        el.style.boxShadow = Array.from(tracks, (c, t) => `0 ${3 * (t + 1)}px 0 0 ${c === undefined ? "white" : ROOT_PALETTE[c]}`)
            .join(", ");
        el.style.borderRadius = "0";
    }
}

// A phrase's entry in a list, underlined in its colour (or not).
function setPhraseUnderline(el, colour) {
    el.style.boxShadow = colour === undefined ? "" : `0 3px 0 0 ${ROOT_PALETTE[colour]}`;
}
