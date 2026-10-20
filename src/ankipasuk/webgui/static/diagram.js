// =============================================================
//  Pasuq diagrams, after Joshua Jacobson's: each mafsiq's bracket
//  spans the text it closes, labelled with its rank and Hebrew name;
//  rank 1 on top, down to rank 4 just above the words. Shared by the
//  main window and the statistics window. The data comes from
//  ankipasuk.diagram.pasuq_diagram; this measures where each word
//  landed and draws the brackets as SVG over the text.
// =============================================================
const DIAGRAM_ROW = 13;  // px per bracket row
const DIAGRAM_PAD = 3;
const SVG_NS = "http://www.w3.org/2000/svg";

function diagramEscape(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
}

// One pasuq: its units (the atnaḥ half and the sof pasuq half) side by
// side, wrapping onto a new line when they don't fit.
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

function drawUnit(inner) {
    const boxes = JSON.parse(inner.dataset.boxes);
    const text = inner.querySelector(".dg-text");
    const svg = inner.querySelector("svg");
    svg.innerHTML = "";
    const base = text.getBoundingClientRect();
    const groups = {};
    for (const span of text.querySelectorAll(".dg-word")) {
        const r = span.getBoundingClientRect();
        const g = groups[span.dataset.g];
        groups[span.dataset.g] = g ? { l: Math.min(g.l, r.left), r: Math.max(g.r, r.right) } : { l: r.left, r: r.right };
    }
    const height = Math.max(...boxes.map((b) => b.h)) * DIAGRAM_ROW + DIAGRAM_PAD;
    text.style.marginTop = height + "px";
    svg.setAttribute("width", text.offsetWidth);
    svg.setAttribute("height", height);
    // Tallest first, so a lower bracket's label is drawn over the lines above it.
    for (const b of [...boxes].sort((a, c) => c.h - a.h)) {
        const right = groups[b.from].r - base.left - 1;
        const left = groups[b.to].l - base.left + 1;
        const y = height - b.h * DIAGRAM_ROW + 6;
        const g = document.createElementNS(SVG_NS, "g");
        g.setAttribute("class", `dg-r${b.rank}` + (b.grey ? " dg-grey" : ""));
        const path = document.createElementNS(SVG_NS, "path");
        path.setAttribute("class", "dg-line");
        path.setAttribute("d", `M${left},${height} V${y} H${right} V${height}`);
        g.appendChild(path);
        const label = document.createElementNS(SVG_NS, "g");
        label.setAttribute("class", "dg-label");
        const t = document.createElementNS(SVG_NS, "text");
        t.textContent = `${b.rank} ${b.name}`;
        label.appendChild(t);
        g.appendChild(label);
        svg.appendChild(g);
        const w = t.getComputedTextLength() + 5;
        const cx = (left + right) / 2;
        t.setAttribute("x", cx);
        t.setAttribute("y", y + 3.2);
        t.setAttribute("text-anchor", "middle");
        const rect = document.createElementNS(SVG_NS, "rect");
        rect.setAttribute("x", cx - w / 2);
        rect.setAttribute("y", y - 5.5);
        rect.setAttribute("width", w);
        rect.setAttribute("height", 11);
        rect.setAttribute("rx", 2);
        label.insertBefore(rect, t);
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

function drawDiagrams(container) {
    for (const inner of container.querySelectorAll(".dg-inner")) drawUnit(inner);
    for (const unit of container.querySelectorAll(".dg-unit")) {
        unit.classList.toggle("dg-scrolls", unit.scrollWidth > unit.clientWidth + 1);
        wheelAlong(unit);
    }
}

// Fill ``container`` with diagrams ([{diagram, ref}]) and keep them drawn
// as it resizes (the units may wrap differently).
function renderDiagrams(container, items) {
    container.innerHTML = items.map((it) => diagramHtml(it.diagram, it.ref)).join("");
    document.fonts.ready.then(() => drawDiagrams(container));
    if (!container.dataset.observed) {
        container.dataset.observed = "1";
        let width = container.clientWidth;
        new ResizeObserver(() => {
            if (container.clientWidth !== width) {
                width = container.clientWidth;
                drawDiagrams(container);
            }
        }).observe(container);
    }
}

// The small list view: each group with its rank and ta'am.
function groupsHtml(items) {
    return items.map((it) => {
        const rows = it.diagram.groups.map((g) =>
            `<li><span class="dg-glabel">${g.rank ? `${g.rank} ${diagramEscape(g.name)}` : ""}</span> `
            + `<span class="dg-gtext">${diagramEscape(g.text)}</span></li>`).join("");
        return (it.ref ? `<div class="dg-ref">${diagramEscape(it.ref)}</div>` : "") + `<ol class="dg-groups" dir="rtl">${rows}</ol>`;
    }).join("");
}
