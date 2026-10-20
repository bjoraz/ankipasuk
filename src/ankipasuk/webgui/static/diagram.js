// =============================================================
//  Pasuq diagrams, after Joshua Jacobson's: each mafsiq's bracket
//  spans the text it closes, labelled with its rank and Hebrew name;
//  rank 1 on top, down to rank 4 just above the words. Shared by the
//  main window and the statistics window. The data comes from
//  ankipasuk.diagram.pasuq_diagram; this measures where each word
//  landed and draws the brackets as SVG over the text.
// =============================================================
// How a diagram is drawn. The app uses these as they are; the print
// preview (snapshotDiagrams) can change any of them.
const DIAGRAM_DEFAULTS = {
    row: 15,          // px per bracket row
    labels: "full",   // "full" (1 אתנח), "name", "rank", or "none"
    labelSize: 10.5,  // px
    grey: true,       // draw the divisions the cards don't make
};
const DIAGRAM_PAD = 3;
const SVG_NS = "http://www.w3.org/2000/svg";
// How far ahead of the visible part to draw, so scrolling doesn't show
// undrawn pesuqim.
const DIAGRAM_AHEAD = "800px 0px";

// A label's box height for a label text size (13px at the usual 10.5px).
function labelHeightFor(o) {
    return Math.round(o.labelSize * 1.24);
}

function diagramEscape(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
}

// One pasuq: its units (the atnaḥ half and the sof pasuq half) side by
// side, wrapping onto a new line when they don't fit. The brackets are
// drawn later, when it comes into view (see renderDiagrams).
function diagramHtml(diagram, ref) {
    const units = diagram.units.map((unit) => {
        const words = unit.words
            .map((w) => `<span class="dg-word" data-g="${w.g}">${diagramEscape(w.text)}</span>`)
            .join(" ");
        return `<div class="dg-unit"><div class="dg-inner" data-boxes='${diagramEscape(JSON.stringify(unit.boxes))}'>`
            + `<svg class="dg-brackets"></svg><div class="dg-text" dir="rtl">${words}</div></div></div>`;
    }).join("");
    const refHtml = ref ? `<div class="dg-ref">${diagramEscape(ref)}</div>` : "";
    return `<div class="dg-pasuq">${refHtml}<div class="dg-units">${units}</div></div>`;
}

// Where each group's words landed, relative to its unit's text. A read
// only -- see drawUnits for why reads and writes are kept apart.
function measureUnit(inner) {
    const text = inner.querySelector(".dg-text");
    const base = text.getBoundingClientRect();
    const groups = {};
    for (const span of text.querySelectorAll(".dg-word")) {
        const r = span.getBoundingClientRect();
        const g = groups[span.dataset.g];
        groups[span.dataset.g] = g ? { l: Math.min(g.l, r.left), r: Math.max(g.r, r.right) } : { l: r.left, r: r.right };
    }
    for (const k in groups) {
        groups[k] = { l: groups[k].l - base.left, r: groups[k].r - base.left };
    }
    return { groups, width: text.offsetWidth };
}

// The boxes to draw, each with its row: without the grey ones, the rows
// close up so no row is left empty (the order of the rows is kept).
function shownBoxes(boxes, o) {
    if (o.grey) return boxes;
    const kept = boxes.filter((b) => !b.grey);
    const rows = [...new Set(kept.map((b) => b.h))].sort((x, y) => x - y);
    return kept.map((b) => ({ ...b, h: rows.indexOf(b.h) + 1 }));
}

function labelText(b, o) {
    if (o.labels === "name") return b.name;
    if (o.labels === "rank") return String(b.rank);
    return `${b.rank} ${b.name}`;
}

function paintUnit(inner, m, o) {
    const boxes = shownBoxes(JSON.parse(inner.dataset.boxes), o);
    const text = inner.querySelector(".dg-text");
    const svg = inner.querySelector("svg");
    svg.innerHTML = "";
    const withLabels = o.labels !== "none";
    const labelHeight = labelHeightFor(o);
    // A bracket's top sits mid-label, or just under the row's top without one.
    const top = withLabels ? labelHeight / 2 + 0.5 : 2;
    const height = boxes.length ? Math.max(...boxes.map((b) => b.h)) * o.row + DIAGRAM_PAD : 0;
    text.style.marginTop = height + "px";
    svg.setAttribute("width", m.width);
    svg.setAttribute("height", height);
    const labels = [];
    // Tallest first, so a lower bracket's label is drawn over the lines above it.
    for (const b of [...boxes].sort((a, c) => c.h - a.h)) {
        const right = m.groups[b.from].r - 1;
        const left = m.groups[b.to].l + 1;
        const y = height - b.h * o.row + top;
        const g = document.createElementNS(SVG_NS, "g");
        g.setAttribute("class", `dg-r${b.rank}` + (b.grey ? " dg-grey" : ""));
        const path = document.createElementNS(SVG_NS, "path");
        path.setAttribute("class", "dg-line");
        path.setAttribute("d", `M${left},${height} V${y} H${right} V${height}`);
        g.appendChild(path);
        if (withLabels) {
            const label = document.createElementNS(SVG_NS, "g");
            label.setAttribute("class", "dg-label");
            const rect = document.createElementNS(SVG_NS, "rect");
            const t = document.createElementNS(SVG_NS, "text");
            t.textContent = labelText(b, o);
            const cx = (left + right) / 2;
            t.setAttribute("x", cx);
            t.setAttribute("y", y + o.labelSize * 0.362);
            t.setAttribute("text-anchor", "middle");
            if (o.labelSize !== DIAGRAM_DEFAULTS.labelSize) t.style.fontSize = o.labelSize + "px";
            label.appendChild(rect);
            label.appendChild(t);
            g.appendChild(label);
            labels.push({ rect, t, cx, y });
        }
        svg.appendChild(g);
    }
    return labels;
}

// Draw a batch of units: every measurement first, then every change, then
// the label widths in one more pass. Interleaving them would make the
// browser lay the page out again for every unit -- which, for a whole
// book, took tens of seconds.
// Label widths come from a canvas in the labels' font: much cheaper than
// asking each SVG text for its length, which in WebKit is slow.
let labelCanvas = null;
let labelFamily = null;
function labelWidth(text, size) {
    if (!labelCanvas) {
        labelCanvas = document.createElement("canvas").getContext("2d");
        const sample = document.createElementNS(SVG_NS, "svg");
        sample.innerHTML = '<g class="dg-label"><text>א</text></g>';
        document.body.appendChild(sample);
        labelFamily = getComputedStyle(sample.querySelector("text")).fontFamily;
        sample.remove();
    }
    labelCanvas.font = `${size}px ${labelFamily}`;
    return labelCanvas.measureText(text).width;
}

function drawUnits(inners, options) {
    const o = { ...DIAGRAM_DEFAULTS, ...options };
    const labelHeight = labelHeightFor(o);
    const measured = inners.map(measureUnit);
    const labels = inners.flatMap((inner, i) => paintUnit(inner, measured[i], o));
    const widths = labels.map((l) => labelWidth(l.t.textContent, o.labelSize) + 6);
    labels.forEach((l, i) => {
        l.rect.setAttribute("x", l.cx - widths[i] / 2);
        l.rect.setAttribute("y", l.y - labelHeight / 2);
        l.rect.setAttribute("width", widths[i]);
        l.rect.setAttribute("height", labelHeight);
        l.rect.setAttribute("rx", 2);
    });
    // Which units overflow, all read before any is marked: marking one and
    // then reading the next would lay the page out again for each.
    const units = inners.map((inner) => inner.parentElement);
    const scrolls = units.map((unit) => unit.scrollWidth > unit.clientWidth + 1);
    units.forEach((unit, i) => {
        unit.classList.toggle("dg-scrolls", scrolls[i]);
        wheelAlong(unit);
    });
}

// The mouse wheel scrolls a too-wide unit along its line: down moves on
// through the pasuq (leftwards). At either end the page scrolls as usual.
function wheelAlong(unit) {
    if (unit.dataset.wheel) return;
    unit.dataset.wheel = "1";
    unit.addEventListener("wheel", (e) => {
        if (!unit.classList.contains("dg-scrolls")) return;
        const delta = Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY;
        const max = unit.scrollWidth - unit.clientWidth;
        const pos = Math.abs(unit.scrollLeft);  // RTL: 0 at the start, negative onwards
        if ((delta > 0 && pos >= max - 1) || (delta < 0 && pos <= 0)) return;
        e.preventDefault();
        unit.scrollLeft -= delta;
    }, { passive: false });
}

let fontReady = null;
function diagramFontReady() {
    if (!fontReady) {
        const probe = document.createElement("span");
        probe.className = "dg-text";
        document.body.appendChild(probe);
        const family = getComputedStyle(probe).fontFamily;
        probe.remove();
        fontReady = document.fonts.load(`22px ${family}`, "בְּ").catch(() => null)
            .then(() => document.fonts.ready);
    }
    return fontReady;
}

// Fill ``container`` with one entry per item, lazily: each starts as an
// empty placeholder and gets its real HTML (``htmlFor(item)``) only when
// it comes into view or close to it, while ``root`` scrolls; ``onFilled``
// then gets the new elements, in batches. A whole book stays
// quick. ``refill`` (true for the diagrams) also re-runs ``onFilled`` for
// entries coming back into view after a width change.
function lazyFill(container, items, htmlFor, onFilled, root, refill) {
    container.innerHTML = items.map((_it, i) => `<div class="dg-pending" data-i="${i}"></div>`).join("");
    if (container._dgObserver) container._dgObserver.disconnect();
    const ready = new Set();
    let scheduled = false;
    const flush = () => {
        scheduled = false;
        const batch = [...ready].filter((el) => el.isConnected);
        ready.clear();
        if (batch.length) onFilled(batch);
    };
    const observer = new IntersectionObserver((entries) => {
        for (const e of entries) {
            if (!e.isIntersecting) continue;
            let el = e.target;
            if (el.classList.contains("dg-pending")) {
                const holder = document.createElement("div");
                holder.innerHTML = htmlFor(items[Number(el.dataset.i)]);
                const filled = holder.firstElementChild;
                filled.dataset.i = el.dataset.i;
                el.replaceWith(filled);
                el = filled;
            }
            ready.add(el);
            observer.unobserve(e.target);
        }
        if (ready.size && !scheduled) {
            // A timer, not requestAnimationFrame: WebKitGTK throttles that
            // in a window that isn't in front, which held drawing up for
            // minutes.
            scheduled = true;
            setTimeout(flush, 0);
        }
    }, { root, rootMargin: DIAGRAM_AHEAD });
    container._dgObserver = observer;
    // Measure only once the pasuq font is in: a font that loads only when
    // the first diagram shows would otherwise widen the text after its
    // brackets were drawn, leaving them short.
    diagramFontReady().then(() => {
        for (const el of container.children) observer.observe(el);
    });
    if (refill && !container._dgResize) {
        let width = container.clientWidth;
        container._dgResize = new ResizeObserver(() => {
            if (container.clientWidth === width) return;
            width = container.clientWidth;
            for (const el of container.children) container._dgObserver.observe(el);
        });
        container._dgResize.observe(container);
    }
}

// Diagrams ([{diagram, ref}]) in ``container``, drawn as they come into
// view while ``scrollRoot`` (the container itself, unless given) scrolls.
function renderDiagrams(container, items, scrollRoot) {
    lazyFill(container, items, (it) => diagramHtml(it.diagram, it.ref),
        (pesuqim) => drawUnits(pesuqim.flatMap((p) => [...p.querySelectorAll(".dg-inner")])),
        scrollRoot || container, true);
}

// The diagrams as a finished page, for saving (ankipasuk.diagram_pages):
// every pasuq drawn at ``width`` (the page's), off screen, a batch at a
// time; a unit too wide for the page gets smaller text, drawn again.
// ``options`` are drawUnits's (DIAGRAM_DEFAULTS), plus ``textSize`` (px)
// and ``bw`` (black and white). Returns the drawn HTML, which needs no
// script to show or print. Each batch is drawn on its own and taken out
// again as text, so the page never holds more than one batch: a whole
// book in one place would make every measurement lay all of it out again.
async function snapshotDiagrams(items, width, onProgress, options) {
    const o = { ...DIAGRAM_DEFAULTS, textSize: 22, bw: false, ...options };
    await diagramFontReady();
    const box = document.createElement("div");
    box.className = o.bw ? "dg-bw" : "";
    box.style.cssText = `position: absolute; left: -30000px; top: 0; width: ${width}px; background: white;`;
    document.body.appendChild(box);
    const BATCH = 50;
    const parts = [];
    try {
        for (let i = 0; i < items.length; i += BATCH) {
            box.innerHTML = items.slice(i, i + BATCH).map((it) => diagramHtml(it.diagram, it.ref)).join("");
            const inners = [...box.querySelectorAll(".dg-inner")];
            for (const inner of inners) inner.querySelector(".dg-text").style.fontSize = o.textSize + "px";
            drawUnits(inners, o);
            const wide = inners.filter((inner) => inner.offsetWidth > width);
            for (const inner of wide) {
                const size = Math.max(9, Math.floor((o.textSize * (width - 4)) / inner.offsetWidth));
                inner.querySelector(".dg-text").style.fontSize = size + "px";
            }
            if (wide.length) drawUnits(wide, o);
            bakeForPrint(box, o);
            parts.push(box.innerHTML);
            if (onProgress) onProgress(Math.min(i + BATCH, items.length), items.length);
            await new Promise((resolve) => setTimeout(resolve, 0));
        }
        return parts.join("");
    } finally {
        box.remove();
    }
}

// Drawn diagrams made to show without this page's styles or scripts: the
// SVG's colours as attributes (a PDF renderer may not apply the page's
// CSS to SVG -- WeasyPrint doesn't), each label's text as ordinary HTML
// over its box (SVG text there is laid out left to right, Hebrew
// included), and the drawing's working data dropped. Every read comes
// before any change, as in drawUnits.
function bakeForPrint(box, o) {
    const labelHeight = labelHeightFor(o);
    const shapes = [...box.querySelectorAll("svg path, svg rect")];
    const shapeValues = shapes.map((el) => {
        const cs = getComputedStyle(el);
        return [cs.fill, cs.stroke, cs.strokeWidth];
    });
    const texts = [...box.querySelectorAll("svg text")];
    const textColours = texts.map((t) => getComputedStyle(t).fill);
    const first = texts.length ? getComputedStyle(texts[0]) : null;
    const labelFont = first ? `font-family: ${first.fontFamily}; font-size: ${o.labelSize}px;` : "";
    shapes.forEach((el, i) => {
        const [fill, stroke, strokeWidth] = shapeValues[i];
        el.setAttribute("fill", fill);
        el.setAttribute("stroke", stroke);
        el.setAttribute("stroke-width", strokeWidth);
    });
    texts.forEach((t, i) => {
        const rect = t.previousElementSibling;
        const label = document.createElement("div");
        label.textContent = t.textContent;
        label.dir = "rtl";
        label.style.cssText = `position: absolute; left: ${rect.getAttribute("x")}px; top: ${rect.getAttribute("y")}px;`
            + ` width: ${rect.getAttribute("width")}px; height: ${labelHeight}px; line-height: ${labelHeight}px;`
            + ` text-align: center; white-space: nowrap; ${labelFont} color: ${textColours[i]};`;
        t.closest(".dg-inner").appendChild(label);
        t.remove();
    });
    for (const el of box.querySelectorAll("[data-boxes], [data-g], [data-wheel]")) {
        el.removeAttribute("data-boxes");
        el.removeAttribute("data-g");
        el.removeAttribute("data-wheel");
    }
}
