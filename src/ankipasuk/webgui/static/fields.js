// =============================================================
//  Semantic fields (ankipasuk.semantics): each word's domains in the
//  Semantic Dictionary of Biblical Hebrew's tree, all brought to one
//  level. The Fields pane lists the passage's fields, the most used or
//  the key ones first; clicking one, or a word, colours its words with
//  the shorashim's palette while the pane is open. A word in two coloured
//  fields is striped in both colours. A field is {label, path, count,
//  verses, words: [[lemma, glosses, times]], total, keyness, ratio}.
// =============================================================

const FIELD_ORDERS = {
    count: (a, b) => b.count - a.count || a.label.localeCompare(b.label),
    key: (a, b) => b.keyness - a.keyness || b.count - a.count,
};

// Where a field is in the tree, above it: "Objects › Natural World".
function fieldParent(info) {
    return info.path.slice(0, -1).join(" › ");
}

function fieldCountsText(info) {
    const here = `${info.count} ${info.count === 1 ? "word" : "words"} here`;
    if (!info.total) return here;
    return `${here}, ${info.total.toLocaleString("en")} in the Tanakh: ${ratioText(info.ratio)} its rate there`;
}

// A field's tooltip: its place in the tree, its counts, its commonest
// words here. (A left-to-right mark first, so the Hebrew sits in its line.)
function fieldTitle(info) {
    const words = info.words.map(([lemma, gloss, n]) => `‎${lemma} · ${gloss} (${n})`).join("\n");
    return `${info.path.join(" › ")}\n${fieldCountsText(info)}\n\n${words}`;
}

// A field in the list: its name, where it is in the tree, how often here
// (and, for key fields, how many times its rate in the Tanakh), its
// commonest words here; coloured ones with where they are (a sparkline).
function fieldRowHtml(key, info, colour, sort, lastColoured, spark) {
    const ratio = sort === "key" && info.total
        ? `<span class="root-ratio${info.keyness > 0 ? "" : " under"}">${ratioText(info.ratio)}</span>` : "";
    const label = colour === undefined ? "fd-label" : `fd-label hl-${colour}`;
    return `<li data-field="${key}"${lastColoured ? ' class="last-coloured"' : ""} title="${diagramEscape(fieldTitle(info))}">`
        + `<span class="${label}">${diagramEscape(info.label)}</span>`
        + `<span class="fd-parent">${diagramEscape(fieldParent(info))}</span>`
        + `<span class="root-count">${info.count}</span>${ratio}`
        + `<span class="fd-words" dir="rtl">${info.words.slice(0, 4).map(([lemma]) => diagramEscape(lemma)).join(" · ")}</span>`
        + `${spark}</li>`;
}

// A word's senses, for its tooltip: each sense's glosses and domains.
function sensesText(senses, ids) {
    return ids.map((id) => {
        const [lemma, gloss, , paths] = senses[id];
        return `‎${lemma} · ${gloss}\n${paths.map((p) => `  ${p}`).join("\n")}`;
    }).join("\n");
}

// The background of a word in coloured fields: one colour, or stripes of
// each, with the text in a colour that reads on them.
function fieldPaint(indices) {
    if (indices.length === 1) {
        return [ROOT_PALETTE[indices[0]], ROOT_PALETTE_DARK.has(indices[0]) ? "white" : "black"];
    }
    const band = 5;
    const stops = indices.map((c, i) => `${ROOT_PALETTE[c]} ${i * band}px ${(i + 1) * band}px`).join(", ");
    return [`repeating-linear-gradient(135deg, ${stops})`, "black"];
}

// Which fields are coloured, as RootColours: in the order clicked, each
// the first free colour. ``onChange`` gets the fields that changed.
class FieldColours {
    constructor(onChange) {
        this.colours = new Map(); // field -> palette index
        this.clicks = 0;
        this.onChange = onChange;
    }

    // Colour these fields (a word's) -- or, if they're all coloured
    // already, take their colours off.
    toggle(fields) {
        if (fields.every((f) => this.colours.has(f))) {
            for (const f of fields) this.colours.delete(f);
        } else {
            for (const f of fields) {
                if (this.colours.has(f)) continue;
                const used = new Set(this.colours.values());
                let colour = ROOT_PALETTE.findIndex((_c, i) => !used.has(i));
                if (colour < 0) colour = this.clicks % ROOT_PALETTE.length;
                this.colours.set(f, colour);
                this.clicks += 1;
            }
        }
        this.onChange(fields);
    }

    clear() {
        const was = [...this.colours.keys()];
        this.colours.clear();
        this.clicks = 0;
        this.onChange(was);
    }

    // Paint the words of these fields under ``root``.
    paint(root, fields) {
        const els = new Set(fields.flatMap((f) => [...root.querySelectorAll(`[data-d~="${f}"]`)]));
        for (const el of els) this._paint(el);
    }

    // Paint every word with a field under ``root`` (new lines of a lazily
    // filled view).
    paintAll(root) {
        for (const el of root.querySelectorAll("[data-d]")) this._paint(el);
    }

    _paint(el) {
        const shown = el.dataset.d.split(" ").map((f) => this.colours.get(f)).filter((c) => c !== undefined);
        if (!shown.length) {
            el.style.removeProperty("--fd");
            el.style.removeProperty("--fd-text");
            el.classList.remove("fd-striped");
            return;
        }
        const [background, text] = fieldPaint(shown);
        el.style.setProperty("--fd", background);
        el.style.setProperty("--fd-text", text);
        el.classList.toggle("fd-striped", shown.length > 1);
    }
}

// The settings dialog's choices: each level, how many of the Tanakh's
// words SDBH files at it, deeper (cut back to it) and shallower (their
// last level repeated). ``levels`` is level -> share (get_field_settings).
function fieldLevelChoicesHtml(settings) {
    const pct = (x) => `${Math.round(x * 100)}%`;
    const share = (test) => Object.entries(settings.levels).filter(([n]) => test(Number(n)))
        .reduce((sum, [, s]) => sum + s, 0);
    return settings.choices.map((level) => {
        const at = share((n) => n === level), deeper = share((n) => n > level), higher = share((n) => n < level);
        const parts = [`${pct(at)} of the words are filed at it`];
        if (deeper) parts.push(`${pct(deeper)} deeper are cut back to it`);
        if (higher) parts.push(`${pct(higher)} higher repeat their last level`);
        return `<label><input type="radio" name="fs-level" value="${level}"> Level ${level}`
            + `${level === settings.default ? " (the default)" : ""}: <span class="muted">${parts.join("; ")}</span></label>`;
    }).join("");
}

function fieldDepthsText(settings) {
    const entries = Object.entries(settings.levels).map(([n, s]) => [Number(n), s]);
    const top = entries.filter(([n]) => n <= 2).reduce((sum, [, s]) => sum + s, 0);
    const rest = entries.filter(([n]) => n > 2).map(([n, s]) => `${n}: ${Math.round(s * 100)}%`);
    return `How deep SDBH files the Tanakh's words: levels 1–2: ${Math.round(top * 100)}% · ${rest.join(" · ")}.`;
}
