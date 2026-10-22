"use strict";

// pywebview's bridge, for the app served to a browser (ankipasuk --serve,
// see webgui/serve.py). The server loads this into every page before the
// page's own scripts; the desktop window never loads it.
//
// window.pywebview.api.<method>(...args) POSTs to /api/<session>/<method>
// and resolves with the bridge method's result, as pywebview's does; once
// the page has a session, pywebviewready fires. The main page asks for a
// new session; a page opened over it (Statistics, Anki tools) is given
// its own in the URL.
(() => {
    const opened = new URLSearchParams(location.search).get("session");
    let session = opened;

    async function post(path, body) {
        const response = await fetch(path, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: body === undefined ? "" : JSON.stringify(body),
        });
        return response.json();
    }

    async function call(name, args) {
        const answer = await post(`/api/${session}/${name}`, args);
        if (answer.error !== undefined) throw new Error(answer.error);
        if (answer.saved && answer.saved.length) offerDownloads(answer.saved);
        for (const page of answer.opened || []) openOver(page);
        return answer.result;
    }

    window.pywebview = {
        api: new Proxy({}, { get: (_, name) => (...args) => call(name, args) }),
    };

    // Python's window.evaluate_js: the scripts it queued, run as they come.
    async function poll() {
        for (;;) {
            let answer;
            try {
                answer = await post(`/api/${session}/_poll`);
            } catch (e) {
                await new Promise((resolve) => setTimeout(resolve, 2000)); // the server is away
                continue;
            }
            if (answer.error !== undefined) return; // the session ended
            for (const script of answer.scripts) {
                try {
                    (0, eval)(script); // in the global scope, where the page's functions are
                } catch (e) {
                    console.error(e);
                }
            }
        }
    }

    // A page that would be a window of its own on the desktop, over this one.
    function openOver(page) {
        const overlay = document.createElement("div");
        overlay.style.cssText =
            "position:fixed;inset:0;z-index:2147483647;display:flex;flex-direction:column;" +
            "background:Canvas;color:CanvasText;";
        const bar = document.createElement("div");
        bar.style.cssText =
            "display:flex;align-items:center;justify-content:space-between;gap:12px;" +
            "padding:8px 12px;border-bottom:1px solid GrayText;font:600 15px system-ui,sans-serif;";
        const title = document.createElement("span");
        title.textContent = page.title;
        const close = document.createElement("button");
        close.type = "button";
        close.textContent = "Close";
        close.style.cssText = "font:inherit;padding:4px 14px;";
        close.addEventListener("click", () => overlay.remove()); // the frame's pagehide ends its session
        bar.append(title, close);
        const frame = document.createElement("iframe");
        frame.src = page.url;
        frame.style.cssText = "flex:1;border:0;width:100%;";
        overlay.append(bar, frame);
        document.body.append(overlay);
    }

    // What a call saved to the exports folder, as links to download it too.
    function offerDownloads(names) {
        const box = document.createElement("div");
        box.style.cssText =
            "position:fixed;left:12px;bottom:12px;z-index:2147483647;max-width:calc(100% - 24px);" +
            "display:flex;flex-wrap:wrap;align-items:center;gap:10px;padding:10px 12px;" +
            "background:Canvas;color:CanvasText;border:1px solid GrayText;border-radius:8px;" +
            "box-shadow:0 2px 10px rgba(0,0,0,.25);font:14px system-ui,sans-serif;";
        for (const name of names) {
            const link = document.createElement("a");
            link.href = "/exports/" + encodeURIComponent(name);
            link.download = name;
            link.textContent = "Download " + name;
            box.append(link);
        }
        const dismiss = document.createElement("button");
        dismiss.type = "button";
        dismiss.textContent = "×";
        dismiss.setAttribute("aria-label", "Dismiss");
        dismiss.style.cssText = "font:inherit;padding:0 8px;";
        dismiss.addEventListener("click", () => box.remove());
        box.append(dismiss);
        document.body.append(box);
    }

    // Leaving the page ends its session (and a page opened over another,
    // its window's closed event); coming back to it from the browser's
    // page cache starts it afresh.
    window.addEventListener("pagehide", () => {
        if (session) navigator.sendBeacon(`/api/${session}/_close`);
    });
    window.addEventListener("pageshow", (e) => {
        if (e.persisted) location.reload();
    });

    const domReady = new Promise((resolve) => {
        if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", resolve);
        else resolve();
    });
    const sessionReady = opened ? Promise.resolve() : post("/api/new").then((a) => { session = a.session; });
    Promise.all([domReady, sessionReady]).then(
        () => {
            poll();
            window.dispatchEvent(new Event("pywebviewready"));
        },
        (e) => alert("Couldn't reach AnkiPasuk: " + e),
    );
})();
