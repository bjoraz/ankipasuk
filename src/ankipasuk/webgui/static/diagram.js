// =============================================================
//  Pasuq diagrams, after Joshua Jacobson's: each mafsiq's bracket
//  spans the text it closes, labelled with its rank and Hebrew name;
//  rank 1 on top, down to rank 4 just above the words. Shared by the
//  main window and the statistics window. The data comes from
//  ankipasuk.diagram.pasuq_diagram; this measures where each word
//  landed and draws the brackets as SVG over the text.
// =============================================================
const DIAGRAM_ROW = 15;  // px per bracket row
const DIAGRAM_PAD = 3;
const LABEL_HEIGHT = 13;
const SVG_NS = "http://www.w3.org/2000/svg";
// How far ahead of the visible part to draw, so scrolling doesn't show
// undrawn pesuqim.
const DIAGRAM_AHEAD = "800px 0px";

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

function paintUnit(inner, m) {
    const boxes = JSON.parse(inner.dataset.boxes);
    const text = inner.querySelector(".dg-text");
    const svg = inner.querySelector("svg");
    svg.innerHTML = "";
    const height = Math.max(...boxes.map((b) => b.h)) * DIAGRAM_ROW + DIAGRAM_PAD;
    text.style.marginTop = height + "px";
    svg.setAttribute("width", m.width);
    svg.setAttribute("height", height);
    const labels = [];
    // Tallest first, so a lower bracket's label is drawn over the lines above it.
    for (const b of [...boxes].sort((a, c) => c.h - a.h)) {
        const right = m.groups[b.from].r - 1;
        const left = m.groups[b.to].l + 1;
        const y = height - b.h * DIAGRAM_ROW + 7;
        const g = document.createElementNS(SVG_NS, "g");
        g.setAttribute("class", `dg-r${b.rank}` + (b.grey ? " dg-grey" : ""));
        const path = document.createElementNS(SVG_NS, "path");
        path.setAttribute("class", "dg-line");
        path.setAttribute("d", `M${left},${height} V${y} H${right} V${height}`);
        g.appendChild(path);
        const label = document.createElementNS(SVG_NS, "g");
        label.setAttribute("class", "dg-label");
        const rect = document.createElementNS(SVG_NS, "rect");
        const t = document.createElementNS(SVG_NS, "text");
        t.textContent = `${b.rank} ${b.name}`;
        const cx = (left + right) / 2;
        t.setAttribute("x", cx);
        t.setAttribute("y", y + 3.8);
        t.setAttribute("text-anchor", "middle");
        label.appendChild(rect);
        label.appendChild(t);
        g.appendChild(label);
        svg.appendChild(g);
        labels.push({ rect, t, cx, y });
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
function labelWidth(text) {
    if (!labelCanvas) {
        labelCanvas = document.createElement("canvas").getContext("2d");
        const sample = document.createElementNS(SVG_NS, "svg");
        sample.innerHTML = '<g class="dg-label"><text>א</text></g>';
        document.body.appendChild(sample);
        const style = getComputedStyle(sample.querySelector("text"));
        labelCanvas.font = `${style.fontSize} ${style.fontFamily}`;
        sample.remove();
    }
    return labelCanvas.measureText(text).width;
}

function drawUnits(inners) {
    const measured = inners.map(measureUnit);
    const labels = inners.flatMap((inner, i) => paintUnit(inner, measured[i]));
    const widths = labels.map((l) => labelWidth(l.t.textContent) + 6);
    labels.forEach((l, i) => {
        l.rect.setAttribute("x", l.cx - widths[i] / 2);
        l.rect.setAttribute("y", l.y - LABEL_HEIGHT / 2);
        l.rect.setAttribute("width", widths[i]);
        l.rect.setAttribute("height", LABEL_HEIGHT);
        l.rect.setAttribute("rx", 2);
    });
    for (const inner of inners) {
        const unit = inner.parentElement;
        unit.classList.toggle("dg-scrolls", unit.scrollWidth > unit.clientWidth + 1);
        wheelAlong(unit);
    }
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
    document.fonts.ready.then(() => {
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
