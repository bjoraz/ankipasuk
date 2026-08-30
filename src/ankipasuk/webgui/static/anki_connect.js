"use strict";

function api() {
    return window.pywebview.api;
}

function getUrl() {
    return document.getElementById("url").value.trim() || "http://127.0.0.1:8765";
}

// Called from Python (via window.evaluate_js) to stream log lines in
// real time while a background operation runs.
function appendLog(tabId, msg) {
    const pane = document.getElementById("log-" + tabId);
    pane.textContent += msg + "\n";
    pane.scrollTop = pane.scrollHeight;
}

// Called from Python when a background operation finishes (success or
// error -- errors are already logged via appendLog before this fires).
function operationDone(tabId) {
    const btn = document.getElementById("run-" + tabId);
    btn.disabled = false;
    btn.textContent = "Run";
}

function startRun(tabId) {
    const btn = document.getElementById("run-" + tabId);
    btn.disabled = true;
    btn.textContent = "Running...";
    document.getElementById("log-" + tabId).textContent = "";
}

function switchTab(tabId) {
    for (const btn of document.querySelectorAll(".tab-btn")) {
        btn.classList.toggle("active", btn.dataset.tab === tabId);
    }
    for (const panel of document.querySelectorAll(".tab-panel")) {
        panel.classList.toggle("active", panel.dataset.panel === tabId);
    }
}

window.addEventListener("pywebviewready", async () => {
    document.getElementById("url").value = await api().get_default_url();

    for (const btn of document.querySelectorAll(".tab-btn")) {
        btn.addEventListener("click", () => switchTab(btn.dataset.tab));
    }
    switchTab("conn");

    document.getElementById("run-conn").addEventListener("click", () => {
        startRun("conn");
        api().check_connection(getUrl());
    });

    document.getElementById("run-stems").addEventListener("click", () => {
        const deck = document.getElementById("stems-deck").value.trim();
        if (!deck) { alert("Enter a deck name."); return; }
        const dryRun = document.getElementById("stems-dry-run").checked;
        startRun("stems");
        api().initialize_stems(getUrl(), deck, dryRun);
    });

    document.getElementById("run-sched").addEventListener("click", () => {
        const deck = document.getElementById("sched-deck").value.trim();
        if (!deck) { alert("Enter a deck name."); return; }
        const interval = parseInt(document.getElementById("sched-interval").value, 10);
        if (!Number.isInteger(interval)) { alert("Promotion interval must be a whole number."); return; }
        const dryRun = document.getElementById("sched-dry-run").checked;
        startRun("sched");
        api().sync_scheduling(getUrl(), deck, interval, dryRun);
    });

    document.getElementById("run-tag").addEventListener("click", () => {
        const deck = document.getElementById("tag-deck").value.trim();
        if (!deck) { alert("Enter a deck name."); return; }
        const dryRun = document.getElementById("tag-dry-run").checked;
        startRun("tag");
        api().tag_deck(getUrl(), deck, dryRun);
    });
});
