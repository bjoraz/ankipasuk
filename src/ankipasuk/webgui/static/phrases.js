// =============================================================
//  Phrases (ankipasuk.phrases): a passage's recurring word sequences,
//  in sections -- refrains, echoes, idioms, and formulas set apart.
//  Shared by the main window's Text view and the statistics window: the
//  section tabs and lists (renderPhrasePane), and a phrase's viewer
//  (openPhraseViewer). A phrase is {id, kinds, formula, exceptional, text,
//  here, total, places: [{ref}], chapters, books, marks: [[pasuq, word]],
//  verses}.
// =============================================================

function plural(n, one, many = `${one}s`) {
    return `${n} ${n === 1 ? one : many}`;
}

const NUMBER_WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];

// The sections, and the line that says what one holds (``n`` of them,
// found with ``t``, the thresholds: Settings).
const PHRASE_SECTIONS = [
    ["refrain", "Refrains", (n) => `${plural(n, "phrase")} repeated here more often than chance would give.`],
    ["echo", "Echoes", (n, t) => `${plural(n, "phrase")} shared with only `
        + (t.echo_places === 1 ? "one other pasuq" : `one to ${NUMBER_WORDS[t.echo_places] || t.echo_places} other pesuqim`)
        + " in the Tanakh. Click a place to read it in its chapter."],
    ["idiom", "Idioms", (n) => `${plural(n, "fixed expression")}, used across the Tanakh.`],
    ["formula", "Formulas", (n) => `${plural(n, "formula")}: phrases that only frame (who speaks, a name, a number, `
        + "God's names)."],
];
const PHRASE_KIND_NAMES = { refrain: "a refrain", echo: "an echo", idiom: "an idiom" };

// A long phrase shortened: its first words … its last, and how many.
function phraseShort(text, max = 9) {
    const words = text.split(" ");
    if (words.length <= max) return text;
    return `${words.slice(0, 5).join(" ")} … ${words.slice(-3).join(" ")} (${words.length} words)`;
}

function phraseCount(result, kind) {
    return kind === "formula" ? result.sections.formula.reduce((n, [, ids]) => n + ids.length, 0)
        : result.sections[kind].length;
}

// One line about a phrase, for its viewer: "An echo · once here · 2 in
// the Tanakh · also an idiom".
function phraseSummary(p, kind) {
    const what = kind === "formula" ? `A formula (${p.formula})` : PHRASE_KIND_NAMES[kind].replace(/^a/, "A");
    const parts = [what, p.here === 1 ? "once here" : `${p.here} times here`, `${p.total} in the Tanakh`];
    if (kind === "idiom") parts.push(`in ${plural(p.chapters, "chapter")} of ${plural(p.books, "book")}`);
    const also = p.kinds.filter((k) => k !== kind).map((k) => PHRASE_KIND_NAMES[k]);
    if (also.length) parts.push(`also ${also.join(" and ")}`);
    if (p.exceptional) parts.push(exceptionalTitle(p).replace(/^A/, "a"));
    return parts.join(" · ");
}

// Why a title of God is listed, not set apart as a formula.
function exceptionalTitle(p) {
    return p.exceptional === "rare" ? `A title of God found only ${plural(p.total, "time")} in the Tanakh`
        : `A title of God mostly here: ${p.here} of its ${p.total} times in the Tanakh`;
}

// A phrase in a list: its text, then how often here and where else (a
// link to its viewer: each place, for an echo).
function phraseRowHtml(p, kind) {
    let where = "";
    if (kind === "echo") {
        where = p.places.map((x, k) => `<a href="#" class="ph-place" data-place="${k}" title="Read it in its chapter">`
            + `${diagramEscape(x.ref)}</a>`).join(", ");
    } else if (p.elsewhere) {
        where = '<a href="#" class="ph-place" data-place="0" title="The other pesuqim it\'s in, each in its chapter">'
            + `${p.elsewhere} elsewhere</a>`;
    }
    const rare = p.exceptional ? ` <span class="ph-rare" title="${diagramEscape(exceptionalTitle(p))}">`
        + `${p.exceptional === "rare" ? "rare" : "mostly here"}</span>` : "";
    return `<li class="ph" data-id="${p.id}">`
        + `<div class="ph-text" dir="rtl" title="${diagramEscape(p.text)}">${diagramEscape(phraseShort(p.text))}</div>`
        + `<div class="ph-meta"><span class="ph-n" title="Times in these pesuqim">${p.here}×</span>`
        + (where ? ` · ${where}` : "") + rare + "</div></li>";
}

// The tabs, the picked section's line, and its list, into ``els`` ({tabs,
// about, list}), from ``result`` (the bridge's get_phrases).
function renderPhrasePane(result, kind, els) {
    els.tabs.innerHTML = PHRASE_SECTIONS.map(([k, name]) =>
        `<button type="button" data-kind="${k}"${k === kind ? ' class="active"' : ""}>${name}`
        + `<span class="ph-tab-n">${phraseCount(result, k)}</span></button>`).join("");
    const [, , about] = PHRASE_SECTIONS.find(([k]) => k === kind);
    els.about.textContent = about(phraseCount(result, kind), result.thresholds);
    const P = result.phrases;
    const rows = kind === "formula"
        ? result.sections.formula.map(([name, ids]) => `<li class="ph-class">${diagramEscape(name)}</li>`
            + ids.map((id) => phraseRowHtml(P[id], kind)).join("")).join("")
        : result.sections[kind].map((id) => phraseRowHtml(P[id], kind)).join("");
    els.list.innerHTML = rows || '<li class="ph-none">None here.</li>';
}

// Words ([text, separator, (group,) marked]) as HTML, each run of marked
// words one highlight, the spaces between them included.
function markedWordsHtml(words) {
    let html = "";
    let open = false;
    words.forEach((w, k) => {
        const [text, sep] = w;
        const marked = w[w.length - 1];
        const next = words[k + 1];
        if (marked && !open) {
            html += '<span class="ph-hit">';
            open = true;
        }
        html += diagramEscape(text);
        if (open && !(next && next[next.length - 1])) {
            html += "</span>";
            open = false;
        }
        html += sep;
    });
    return html;
}

// A phrase's viewer, over the window: its pesuqim here, its words marked,
// and beside them one of its other places in its whole chapter (fetched),
// the pasuq tinted, scrolled to it. ``calls`` are the bridge's:
// {verses(id), context(id, place)}; ``place``, the one to show first.
let phraseViewerClose = null;
function openPhraseViewer(p, kind, calls, place = 0) {
    if (phraseViewerClose) phraseViewerClose();
    const more = p.elsewhere - p.places.length;
    // A few places as buttons; more, as a list to step through.
    const picker = p.places.length <= 6
        ? p.places.map((x, k) => `<button type="button" data-place="${k}">${diagramEscape(x.ref)}</button>`).join("")
        : '<button type="button" class="ph-step" data-step="-1" title="The one before">‹</button>'
            + `<select class="ph-pick">${p.places.map((x, k) => `<option value="${k}">${diagramEscape(x.ref)}</option>`).join("")}</select>`
            + '<button type="button" class="ph-step" data-step="1" title="The next">›</button>';
    const there = p.places.length
        ? `<section class="ph-there"><h4>Elsewhere <span class="muted">${plural(p.elsewhere, "pasuq", "pesuqim")}</span></h4>`
            + `<div class="ph-places">${picker}${more > 0 ? `<span class="muted">and ${more} more</span>` : ""}</div>`
            + '<div class="ph-chapter-title"></div><div class="ph-chapter"></div></section>'
        : "";
    const overlay = document.createElement("div");
    overlay.className = "ph-viewer-overlay";
    overlay.innerHTML = '<div class="ph-viewer" role="dialog" aria-modal="true">'
        + '<header class="ph-viewer-head">'
        + `<div class="ph-viewer-title" dir="rtl">${diagramEscape(phraseShort(p.text, 30))}</div>`
        + `<div class="ph-viewer-sub">${diagramEscape(phraseSummary(p, kind))}</div>`
        + '<button type="button" class="ph-viewer-close" title="Close (Esc)">×</button></header>'
        + `<div class="ph-viewer-body${there ? "" : " single"}">`
        + '<section class="ph-here"><h4>Here</h4><div class="ph-verses muted">Loading…</div></section>'
        + there + "</div></div>";
    document.body.appendChild(overlay);
    const onKey = (e) => { if (e.key === "Escape") close(); };
    const close = () => {
        overlay.remove();
        document.removeEventListener("keydown", onKey);
        phraseViewerClose = null;
    };
    phraseViewerClose = close;
    document.addEventListener("keydown", onKey);
    overlay.addEventListener("click", (e) => {
        if (e.target === overlay || e.target.closest(".ph-viewer-close")) close();
        const btn = e.target.closest(".ph-places button[data-place]");
        if (btn) showPlace(Number(btn.dataset.place));
        const step = e.target.closest(".ph-step");
        if (step) showPlace(Math.min(Math.max(current + Number(step.dataset.step), 0), p.places.length - 1));
    });
    overlay.addEventListener("change", (e) => {
        if (e.target.classList.contains("ph-pick")) showPlace(Number(e.target.value));
    });

    calls.verses(p.id).then((verses) => {
        const box = overlay.querySelector(".ph-verses");
        box.classList.remove("muted");
        box.innerHTML = verses.map((v) => `<div class="ph-ref">${diagramEscape(v.ref)}</div>`
            + `<div class="ph-pasuq pasuq-text" dir="rtl">${markedWordsHtml(v.words)}</div>`).join("");
    });

    let shown = 0;
    let current = 0;
    async function showPlace(k) {
        const mine = ++shown;
        current = k;
        for (const b of overlay.querySelectorAll(".ph-places button[data-place]")) {
            b.classList.toggle("active", Number(b.dataset.place) === k);
        }
        const pick = overlay.querySelector(".ph-pick");
        if (pick) pick.value = String(k);
        for (const b of overlay.querySelectorAll(".ph-step")) {
            b.disabled = k + Number(b.dataset.step) < 0 || k + Number(b.dataset.step) >= p.places.length;
        }
        const box = overlay.querySelector(".ph-chapter");
        const title = overlay.querySelector(".ph-chapter-title");
        title.textContent = "";
        box.innerHTML = '<p class="muted">Fetching from Sefaria…</p>';
        const result = await calls.context(p.id, k);
        if (mine !== shown || !overlay.isConnected) return;
        if (!result.ok) {
            box.innerHTML = `<p class="muted">${diagramEscape(result.ref)}: couldn't fetch it (${diagramEscape(result.error)}).</p>`;
            return;
        }
        title.textContent = result.title;
        box.innerHTML = result.verses.map((v) => `<p class="ph-vs pasuq-text${v.hit ? " hit" : ""}" dir="rtl">`
            + `<span class="ph-vs-n">${v.vs}</span>${markedWordsHtml(v.words)}</p>`).join("");
        const hit = box.querySelector(".ph-vs.hit");  // (the chapter box is its offset parent)
        if (hit) box.scrollTop = Math.max(0, hit.offsetTop - box.clientHeight / 4);
    }
    if (there) showPlace(Math.min(place, p.places.length - 1));
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
