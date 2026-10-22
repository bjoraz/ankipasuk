// =============================================================
//  Phrases (ankipasuk.phrases): a passage's recurring word sequences,
//  in sections -- refrains, echoes, idioms, and formulas set apart.
//  Shared by the main window's Text view and the statistics window: the
//  section tabs and lists (renderPhrasePane), and a phrase's viewer
//  (openPhraseViewer), and the archive (openPhraseArchive). A phrase is
//  {id, key, kinds, formula, exceptional, text, here, total, places:
//  [{ref}], chapters, books, marks: [[pasuq, word]], verses}; a frame has
//  its frame too. An archived phrase (its key in the result's archive) is
//  left out everywhere until it's restored.
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
    ["frame", "Frames", (n) => `${plural(n, "frame")}: units of Masoretic sections that open and close with the same `
        + "words, a single section or a petuḥa section first. A single word's frame is a candidate: some are chance."],
];
// A frame section's groups (a formula's are its classes).
const PHRASE_GROUPS = { sections: "Phrases: a section", runs: "Phrases: a run of sections", words: "Words (candidates)" };
const PHRASE_KIND_NAMES = { refrain: "a refrain", echo: "an echo", idiom: "an idiom", formula: "a formula",
                            frame: "a frame" };

// A long phrase shortened: its first words … its last, and how many.
function phraseShort(text, max = 9) {
    const words = text.split(" ");
    if (words.length <= max) return text;
    return `${words.slice(0, 5).join(" ")} … ${words.slice(-3).join(" ")} (${words.length} words)`;
}

// Formulas and frames come in groups: [[name, ids], ...].
const PHRASE_GROUPED = new Set(["formula", "frame"]);

// The keys of the archived phrases.
function phraseArchived(result) {
    return new Set((result.archive || []).map((e) => e.key));
}

// A section's phrases, by id, the archived left out: a list, or for
// formulas and frames, [[group, ids], ...] (its empty groups left out).
function phraseSection(result, kind, archived = phraseArchived(result)) {
    const live = (ids) => ids.filter((id) => !archived.has(result.phrases[id].key));
    const section = result.sections[kind] || [];
    return PHRASE_GROUPED.has(kind) ? section.map(([name, ids]) => [name, live(ids)]).filter(([, ids]) => ids.length)
        : live(section);
}

function phraseCount(result, kind, archived) {
    const section = phraseSection(result, kind, archived);
    return PHRASE_GROUPED.has(kind) ? section.reduce((n, [, ids]) => n + ids.length, 0) : section.length;
}

// Groups folded unless opened (words' frames), and those the user folded
// or opened: remembered.
const PHRASE_FOLDED = new Set(["frame:words"]);
const PHRASE_GROUPS_KEY = "ankipasuk_phrase_groups";
const phraseGroupsFlipped = new Set((() => {
    try { return JSON.parse(localStorage.getItem(PHRASE_GROUPS_KEY) || "[]"); } catch (e) { return []; }
})());

function phraseGroupOpen(kind, name) {
    const key = `${kind}:${name}`;
    return PHRASE_FOLDED.has(key) === phraseGroupsFlipped.has(key);
}

function togglePhraseGroup(kind, name) {
    const key = `${kind}:${name}`;
    if (phraseGroupsFlipped.has(key)) phraseGroupsFlipped.delete(key);
    else phraseGroupsFlipped.add(key);
    try { localStorage.setItem(PHRASE_GROUPS_KEY, JSON.stringify([...phraseGroupsFlipped])); } catch (e) { /* not kept */ }
}

// A frame's unit: "1:1–2:3", or with its book, "Bereshit 1:1–2:3".
function frameSpan(f, withBook = false) {
    const split = (ref) => [ref.slice(0, ref.lastIndexOf(" ")), ref.slice(ref.lastIndexOf(" ") + 1)];
    const [[book, at1], [, at2]] = [split(f.first), split(f.last)];
    return `${withBook ? `${book} ` : ""}${at1}–${at2}`;
}

function oneIn(chance) {
    const n = Math.round(1 / chance);
    return `1 in ${n.toLocaleString("en")}`;
}

// What a frame's unit is: a single section, a petuḥa section (from one
// petuḥa to the next, setumot between), or a run of sections.
function frameUnitText(f) {
    if (f.unit === "setuma") return "a setuma section";
    if (f.unit === "petuha") {
        return f.sections === 1 ? "a petuḥa section" : `a petuḥa section with ${plural(f.sections - 1, "setuma", "setumot")}`;
    }
    return plural(f.sections, "section");
}

// One line about a phrase, for its viewer: "An echo · once here · 2 in
// the Tanakh · also an idiom".
function phraseSummary(p, kind) {
    if (kind === "frame") {
        const f = p.frame;
        return [`${f.word ? "A word's frame, a candidate" : "A frame"}: ${frameSpan(f, true)}`,
                frameUnitText(f), `${oneIn(f.chance)} by chance`].join(" · ");
    }
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
function phraseRowHtml(p, kind, lastPicked = false) {
    if (kind === "frame") return frameRowHtml(p, lastPicked);
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
    return `<li class="ph${lastPicked ? " last-picked" : ""}" data-id="${p.id}">`
        + `<div class="ph-text" dir="rtl" title="${diagramEscape(p.text)}">${diagramEscape(phraseShort(p.text))}</div>`
        + `<div class="ph-meta"><span class="ph-n" title="Times in these pesuqim">${p.here}×</span>`
        + (where ? ` · ${where}` : "") + rare + PHRASE_ARCHIVE_BUTTON + "</div></li>";
}

const PHRASE_ARCHIVE_BUTTON = ' <button type="button" class="ph-archive" title="Put it in the archive: hidden here '
    + 'and in every passage, in all its sections, until you restore it">archive</button>';

// A frame in its list: its words, then its unit, its chance, and its ends
// that aren't loaded (links to the viewer).
function frameRowHtml(p, lastPicked) {
    const f = p.frame;
    const ends = p.places.map((x, k) => `<a href="#" class="ph-place" data-place="${k}" title="Read it in its chapter">`
        + `${diagramEscape(x.ref.slice(x.ref.lastIndexOf(" ") + 1))}</a>`).join(", ");
    return `<li class="ph${lastPicked ? " last-picked" : ""}" data-id="${p.id}">`
        + `<div class="ph-text" dir="rtl" title="${diagramEscape(p.text)}">${diagramEscape(phraseShort(p.text))}</div>`
        + `<div class="ph-meta"><span class="ph-n" title="${diagramEscape(frameSpan(f, true))}">${frameSpan(f)}</span>`
        + ` · ${frameUnitText(f)} · <span title="How likely by chance">${oneIn(f.chance)}</span>`
        + (ends ? ` · also ${ends}` : "") + PHRASE_ARCHIVE_BUTTON + "</div></li>";
}

// A section shows its first few phrases (the strongest: each is ranked),
// and all of them when asked; which sections show all is remembered.
const PHRASES_SHOWN = 12;
const PHRASES_ALL_KEY = "ankipasuk_phrases_all";
const phrasesAll = new Set((() => {
    try { return JSON.parse(localStorage.getItem(PHRASES_ALL_KEY) || "[]"); } catch (e) { return []; }
})());

function togglePhrasesAll(kind) {
    if (phrasesAll.has(kind)) phrasesAll.delete(kind);
    else phrasesAll.add(kind);
    try { localStorage.setItem(PHRASES_ALL_KEY, JSON.stringify([...phrasesAll])); } catch (e) { /* not kept */ }
}

// The tabs, the picked section's line, and its list, into ``els`` ({tabs,
// about, list}), from ``result`` (the bridge's get_phrases): ``first``, the
// phrases picked (in the order picked), above the rest; a group's header
// folds it. Below, the archive, if anything is in it. Clicks on these
// are for phrasePaneClick.
function renderPhrasePane(result, kind, els, first = []) {
    const archived = phraseArchived(result);
    els.tabs.innerHTML = PHRASE_SECTIONS.map(([k, name]) =>
        `<button type="button" data-kind="${k}"${k === kind ? ' class="active"' : ""}>${name}`
        + `<span class="ph-tab-n">${phraseCount(result, k, archived)}</span></button>`).join("");
    const [, , about] = PHRASE_SECTIONS.find(([k]) => k === kind);
    els.about.textContent = about(phraseCount(result, kind, archived), result.thresholds);
    const P = result.phrases;
    const grouped = PHRASE_GROUPED.has(kind);
    const groups = phraseSection(result, kind, archived);
    const section = grouped ? groups.flatMap(([, ids]) => ids) : groups;
    const inSection = new Set(section);
    const top = first.filter((id) => inSection.has(id));
    const shown = new Set(top);
    const topRows = top.map((id, i) => phraseRowHtml(P[id], kind, i === top.length - 1)).join("");
    let room = phrasesAll.has(kind) ? Infinity : PHRASES_SHOWN;
    const take = (ids) => {
        const taken = ids.filter((id) => !shown.has(id)).slice(0, Math.max(room, 0));
        room -= taken.length;
        return taken;
    };
    // Rows that could show: those of the open groups.
    const n = grouped ? groups.filter(([name]) => phraseGroupOpen(kind, name)).reduce((m, [, ids]) => m + ids.length, 0)
        : section.length;
    const rows = grouped
        ? groups.map(([name, ids]) => {
            const open = phraseGroupOpen(kind, name);
            const taken = open ? take(ids) : [];
            if (open && !taken.length) return "";  // (no room: Show all)
            return `<li class="ph-class ph-fold${open ? " open" : ""}" data-group="${diagramEscape(name)}" `
                + `title="${open ? "Fold" : "Show"} them">${diagramEscape(PHRASE_GROUPS[name] || name)}`
                + ` <span class="ph-class-n">${ids.length}</span></li>`
                + taken.map((id) => phraseRowHtml(P[id], kind)).join("");
        }).join("")
        : take(groups).map((id) => phraseRowHtml(P[id], kind)).join("");
    const more = n <= PHRASES_SHOWN ? ""
        : `<li class="ph-more"><button type="button" class="link">${phrasesAll.has(kind)
            ? `Show the first ${PHRASES_SHOWN}` : `Show all ${n}`}</button></li>`;
    const all = result.sections[kind] || [];
    const here = (grouped ? all.flatMap(([, ids]) => ids) : all).filter((id) => archived.has(P[id].key)).length;
    const archive = archived.size
        ? `<li class="ph-archived"><button type="button" class="link ph-archive-open" title="The phrases you archived: `
            + `restore any of them">Archive (${archived.size})</button>`
            + (here ? `<span class="muted"> · ${here} from this section</span>` : "") + "</li>"
        : "";
    els.list.innerHTML = (topRows + rows || '<li class="ph-none">None here.</li>') + more + archive;
}

// The list's own clicks, the same in both windows: Show all, a group's
// header, a row's archive button, and the archive. True if it was one.
// ``calls`` are the bridge's: {archive(id, kind), restore(keys)}; then
// ``redraw()``, after ``archived(phrase)`` for one just archived.
function phrasePaneClick(e, result, kind, calls, redraw, archived = () => {}) {
    if (e.target.closest(".ph-more button")) {
        togglePhrasesAll(kind);
        redraw();
        return true;
    }
    const fold = e.target.closest(".ph-fold");
    if (fold) {
        togglePhraseGroup(kind, fold.dataset.group);
        redraw();
        return true;
    }
    if (e.target.closest(".ph-archive-open")) {
        openPhraseArchive(result, calls, redraw);
        return true;
    }
    const button = e.target.closest(".ph-archive");
    if (!button) return false;
    const p = result.phrases[Number(button.closest("li.ph").dataset.id)];
    calls.archive(p.id, kind).then((r) => {
        if (!r.ok) return phraseArchiveError(r.error);
        result.archive = r.archive;
        archived(p);
        redraw();
    });
    return true;
}

function phraseArchiveError(error) {
    if (typeof showToast === "function") showToast(error, true);
    else console.error(error);
}

// The archive, over the window: every archived phrase, the last first,
// each with its section, its pasuq and when, and a button to restore it
// (those in this passage marked "here"). ``calls`` as phrasePaneClick's;
// ``redraw()`` after a phrase is restored. phraseArchiveChanged (in each
// window) has it show what another window did.
let phraseArchiveDialog = null; // {result, render}, while it's open
function openPhraseArchive(result, calls, redraw) {
    if (phraseArchiveDialog) phraseArchiveDialog.close();
    const overlay = document.createElement("div");
    overlay.className = "ph-viewer-overlay";
    overlay.innerHTML = '<div class="ph-viewer ph-archive-box" role="dialog" aria-modal="true">'
        + '<header class="ph-viewer-head"><div class="ph-archive-title">Archive</div>'
        + '<div class="ph-viewer-sub">The phrases you archived, the last first. Each is left out of every passage '
        + 'until you restore it.</div>'
        + '<button type="button" class="ph-viewer-close" title="Close (Esc)">×</button></header>'
        + '<ol class="ph-list ph-archive-list"></ol>'
        + '<footer class="ph-archive-foot"><button type="button" class="link ph-restore-all">Restore all</button></footer>'
        + "</div>";
    document.body.appendChild(overlay);
    const list = overlay.querySelector(".ph-archive-list");
    const render = () => {
        const here = new Set(dialog.result.phrases.map((p) => p.key));
        const archive = dialog.result.archive || [];
        list.innerHTML = archive.map((e) => `<li class="ph" data-key="${diagramEscape(e.key)}">`
            + `<div class="ph-text" dir="rtl">${diagramEscape(phraseShort(e.text || ""))}</div>`
            + `<div class="ph-meta">${diagramEscape(PHRASE_KIND_NAMES[e.kind] || e.kind)}`
            + (e.where ? ` · ${diagramEscape(e.where)}` : "") + (e.date ? ` · archived ${diagramEscape(e.date)}` : "")
            + (here.has(e.key) ? ' · <span class="ph-here-tag">here</span>' : "")
            + ' <button type="button" class="ph-restore">Restore</button></div></li>').join("")
            || '<li class="ph-none">Nothing is archived.</li>';
        overlay.querySelector(".ph-restore-all").hidden = archive.length < 2;
    };
    const restore = (keys) => calls.restore(keys).then((r) => {
        if (!r.ok) return phraseArchiveError(r.error);
        dialog.result.archive = r.archive;
        render();
        redraw();
    });
    const onKey = (e) => { if (e.key === "Escape") close(); };
    const close = () => {
        overlay.remove();
        document.removeEventListener("keydown", onKey);
        phraseArchiveDialog = null;
    };
    const dialog = { result, render, close };
    phraseArchiveDialog = dialog;
    document.addEventListener("keydown", onKey);
    overlay.addEventListener("click", (e) => {
        if (e.target === overlay || e.target.closest(".ph-viewer-close")) close();
        const one = e.target.closest(".ph-restore");
        if (one) restore([one.closest("li").dataset.key]);
        if (e.target.closest(".ph-restore-all")) restore((dialog.result.archive || []).map((x) => x.key));
    });
    render();
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
        ? `<section class="ph-there"><h4>${kind === "frame" ? "Outside the passage" : "Elsewhere"} `
            + `<span class="muted">${plural(p.elsewhere, "pasuq", "pesuqim")}</span></h4>`
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
            + `<span class="ph-vs-n" dir="ltr">${result.ch}:${v.vs}</span>${markedWordsHtml(v.words)}</p>`).join("");
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
