// =============================================================
//  Verb forms: each verb's form as OSHB's morphology codes it (the
//  shorashim's words carry it, ankipasuk.shorashim_build.verb_form), in
//  seven groups or all eleven forms. The Verbs pane counts them and draws
//  the passage as a strip, a block per verb in order; while it's open the
//  verbs are coloured in the text. Forms only: reading them as a story's
//  mainline or background is an interpretation, left to the reader.
// =============================================================

const VERB_FORMS = {
    w: ["wayyiqtol", "#1565c0"],
    p: ["qatal", "#e65100"],
    i: ["yiqtol", "#2e7d32"],
    q: ["weqatal", "#00838f"],
    v: ["imperative", "#c62828"],
    j: ["jussive", "#ad1457"],
    h: ["cohortative", "#9e9d24"],
    r: ["participle (active)", "#6a1b9a"],
    s: ["participle (passive)", "#ab47bc"],
    a: ["infinitive absolute", "#a1887f"],
    c: ["infinitive construct", "#6d4c41"],
};

// The seven groups: each a form, or forms alike in kind.
const VERB_GROUPS = [
    ["w", "wayyiqtol", "#1565c0", ["w"]],
    ["p", "qatal", "#e65100", ["p"]],
    ["i", "yiqtol", "#2e7d32", ["i"]],
    ["q", "weqatal", "#00838f", ["q"]],
    ["vol", "volitive", "#c62828", ["v", "j", "h"]],
    ["ptc", "participle", "#6a1b9a", ["r", "s"]],
    ["inf", "infinitive", "#6d4c41", ["a", "c"]],
];

// The kinds shown, as [key, name, colour, forms]: the groups, or each form.
function verbKinds(allForms) {
    return allForms ? Object.entries(VERB_FORMS).map(([f, [name, colour]]) => [f, name, colour, [f]]) : VERB_GROUPS;
}

// The loaded pesuqim's verbs in order, as [pasuq, word, form], from the
// shorashim's words ([text, separator, group, form]).
function verbSequence(verses) {
    const out = [];
    verses.forEach((words, v) => words.forEach((w, k) => { if (w[3]) out.push([v, k, w[3]]); }));
    return out;
}

// The strip: a block per verb, the first on the right as the text reads,
// in its kind's colour (pale if hidden); below it, a tick where a Masoretic
// section ends (taller for a petuḥa).
function verbStripHtml(sequence, kinds, hidden, breaks) {
    const n = sequence.length;
    if (!n) return '<p class="muted">No verbs here.</p>';
    const colourOf = {};
    for (const [key, , colour, forms] of kinds) for (const f of forms) colourOf[f] = hidden.has(key) ? "#e3e7ea" : colour;
    const blocks = sequence.map(([, , f], i) => `<rect x="${n - 1 - i}" y="0" width="1" height="1" fill="${colourOf[f]}"/>`);
    const w = Math.max(0.6, n / 260);
    sequence.forEach(([v], i) => {
        const next = sequence[i + 1];
        const end = (breaks[v] || []).filter((b) => !Array.isArray(b)).pop();
        if (end && (!next || next[0] !== v)) {
            blocks.push(`<rect x="${n - 1 - i - w / 2}" y="${end === "P" ? 1.08 : 1.2}" width="${w}" height="${end === "P" ? 0.32 : 0.2}" fill="#5d4037"/>`);
        }
    });
    return `<svg class="vf-strip-svg" viewBox="0 0 ${n} 1.4" preserveAspectRatio="none" data-n="${n}">`
        + `<title>Each verb in order, from the right; a tick below where a section ends. Click to go to the verb.</title>`
        + blocks.join("") + "</svg>";
}

// The kinds with their counts, each a toggle.
function verbListHtml(sequence, kinds, hidden) {
    const counts = {};
    for (const [, , f] of sequence) counts[f] = (counts[f] || 0) + 1;
    const total = sequence.length || 1;
    return kinds.map(([key, name, colour, forms]) => {
        const n = forms.reduce((sum, f) => sum + (counts[f] || 0), 0);
        const of = forms.length > 1 ? ` title="${forms.map((f) => VERB_FORMS[f][0]).join(", ")}"` : "";
        return `<li data-kind="${key}"${of} class="${hidden.has(key) ? "off" : ""}">`
            + `<span class="vf-swatch" style="background:${colour}"></span><span class="vf-name">${name}</span>`
            + `<span class="vf-n">${n}</span><span class="vf-pct">${Math.round((100 * n) / total)}%</span></li>`;
    }).join("");
}

// Colour the text's verbs ([data-f]) by kind, or not at all (``kinds`` null).
function colourVerbs(box, kinds, hidden) {
    for (const f of Object.keys(VERB_FORMS)) box.style.removeProperty(`--vf-${f}`);
    if (!kinds) return;
    for (const [key, , colour, forms] of kinds) {
        if (!hidden.has(key)) for (const f of forms) box.style.setProperty(`--vf-${f}`, colour);
    }
}
