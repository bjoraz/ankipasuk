// =============================================================
//  Verb forms: each verb's form as OSHB's morphology codes it (the
//  shorashim's words carry it, ankipasuk.shorashim_build.verb_form), in
//  seven groups or all eleven forms. The Verbs pane counts them and draws
//  the passage as a strip, a block per verb in order; while it's open the
//  verbs are coloured in the text. Forms only: reading them as a story's
//  mainline or background is an interpretation, left to the reader.
// =============================================================

// Each form: its name, its colour, and what it is (shown on hover).
const VERB_FORMS = {
    w: ["wayyiqtol", "#1565c0", "Wayyiqtol (vav-consecutive imperfect): וַ, with the next letter doubled, "
        + "before a prefix form: וַיֹּאמֶר. The usual form for past events told in sequence."],
    p: ["qatal", "#e65100", "Qatal (perfect, the suffix conjugation): the person in its ending: אָמַר, "
        + "אָמַרְתִּי. Mostly done or past action; with a verb of state, the state."],
    i: ["yiqtol", "#2e7d32", "Yiqtol (imperfect, the prefix conjugation): the person in its prefix: יֹאמַר, "
        + "תֹּאמַר. Future, repeated or possible action."],
    q: ["weqatal", "#00838f", "Weqatal (vav-consecutive perfect): וְ before a qatal: וְאָמַרְתָּ. Mostly "
        + "future or repeated action, or instructions, often after a yiqtol or an imperative."],
    v: ["imperative", "#c62828", "Imperative: a command, in the second person only: אֱמֹר, לֵךְ."],
    j: ["jussive", "#ad1457", "Jussive: a wish or command for the third person, or with אַל a prohibition: "
        + "יְהִי, אַל־תִּירָא. Often a shortened yiqtol."],
    h: ["cohortative", "#9e9d24", "Cohortative: a wish or resolve of the first person, often with ־ָה: "
        + "נֵלְכָה, אֶשְׁמְרָה."],
    r: ["participle (active)", "#6a1b9a", "Active participle: a verbal adjective, the one doing: הֹלֵךְ, "
        + "יֹשֵׁב. Ongoing action, or the doer, as a noun."],
    s: ["participle (passive)", "#ab47bc", "Passive participle (of qal): the one it's done to: בָּרוּךְ, "
        + "כָּתוּב."],
    a: ["infinitive absolute", "#a1887f", "Infinitive absolute: the bare verbal noun, often beside its own "
        + "verb for emphasis (מוֹת יוּמָת), or standing for a command."],
    c: ["infinitive construct", "#6d4c41", "Infinitive construct: the verbal noun, with prepositions and "
        + "suffixes: לֵאמֹר, בְּשׁוּבוֹ (to say, when he returns)."],
};

// The seven groups: each a form, or forms alike in kind.
const VERB_GROUPS = [
    ["w", "wayyiqtol", "#1565c0", ["w"]],
    ["p", "qatal", "#e65100", ["p"]],
    ["i", "yiqtol", "#2e7d32", ["i"]],
    ["q", "weqatal", "#00838f", ["q"]],
    ["vol", "volitive", "#c62828", ["v", "j", "h"], "Volitives: the forms of command and wish."],
    ["ptc", "participle", "#6a1b9a", ["r", "s"], "Participles: the verb as an adjective."],
    ["inf", "infinitive", "#6d4c41", ["a", "c"], "Infinitives: the verb as a noun."],
];

// The kinds shown, as [key, name, colour, forms, about]: the groups, or
// each form.
function verbKinds(allForms) {
    return allForms ? Object.entries(VERB_FORMS).map(([f, [name, colour]]) => [f, name, colour, [f]]) : VERB_GROUPS;
}

// What a kind is, for its hover: a form's line, or a group's and each of
// its forms'.
function verbAbout([, , , forms, about]) {
    return forms.length === 1 ? VERB_FORMS[forms[0]][2] : [about, ...forms.map((f) => VERB_FORMS[f][2])].join("\n\n");
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
    // A section's end goes after the last verb before it: between a verb
    // and the next, the strongest end of the pesuqim from the verb's on
    // (a pasuq without verbs can end a section too).
    const w = Math.max(0.6, n / 260);
    const endOf = (v) => (breaks[v] || []).filter((b) => !Array.isArray(b)).pop();
    sequence.forEach(([v], i) => {
        const next = i + 1 < n ? sequence[i + 1][0] : breaks.length;  // the next verb's pasuq
        if (next === v) return;
        let end = null;
        for (let u = v; u < next; u++) {
            const e = endOf(u);
            if (e === "P" || (e && !end)) end = e;
        }
        if (end) {
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
    return kinds.map((kind) => {
        const [key, name, colour, forms] = kind;
        const n = forms.reduce((sum, f) => sum + (counts[f] || 0), 0);
        return `<li data-kind="${key}" title="${diagramEscape(verbAbout(kind))}" class="${hidden.has(key) ? "off" : ""}">`
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
