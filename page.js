// SPDX-License-Identifier: GPL-3.0-or-later
// Explorateur d'API — outil Bobi.Tools (runtime=inprocess + backend.py). L'UI envoie la
// requête au backend via ctx.api("request", …) ; le backend la rejoue côté serveur et
// renvoie status/headers/body. L'historique est persisté via ctx.store.
window.BTTools = window.BTTools || {};
window.BTTools.api_explorer = (function () {
    let EL = null, CTX = null, history = [];
    const esc = (s) => String(s == null ? "" : s)
        .replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    const $ = (sel) => EL.querySelector(sel);

    async function loadHistory() {
        try { history = await CTX.store.list(); } catch (e) { history = []; }
        renderHistory();
    }
    function renderHistory() {
        const ul = $("#api-hist");
        if (!history.length) { ul.innerHTML = '<li class="meta">—</li>'; return; }
        ul.innerHTML = history.slice().reverse().map((h) =>
            '<li class="h" data-id="' + h.id + '">' + esc((h.value || {}).method || "GET") + " " + esc(h.name) + "</li>"
        ).join("");
        ul.querySelectorAll(".h").forEach((li) => li.onclick = () => {
            const h = history.find((x) => x.id === Number(li.dataset.id));
            if (!h) return;
            const v = h.value || {};
            $("#api-method").value = v.method || "GET";
            $("#api-url").value = h.name;
            $("#api-headers").value = v.headers || "";
            $("#api-body").value = v.body || "";
        });
    }

    async function send() {
        const url = $("#api-url").value.trim();
        if (!url) { CTX.toast("Saisissez une URL.", "warning"); return; }
        const method = $("#api-method").value;
        let headers = {};
        const rawHeaders = $("#api-headers").value.trim();
        if (rawHeaders) {
            try { headers = JSON.parse(rawHeaders); }
            catch (e) { CTX.toast("En-têtes JSON invalides.", "error"); return; }
        }
        const body = $("#api-body").value;
        const resp = $("#api-resp");
        resp.innerHTML = '<div class="meta">Envoi…</div>';
        $("#api-send").disabled = true;
        try {
            const r = await CTX.api("request", { body: { method, url, headers, body } });
            renderResp(r);
            // Persiste dans l'historique (nom = URL, valeur = paramètres rejouables).
            await CTX.store.create(url, { method, headers: rawHeaders, body });
            loadHistory();
        } catch (e) {
            resp.innerHTML = '<div style="color:var(--status-stopped-fg)">Erreur : ' + esc(e.message) + "</div>";
        } finally { $("#api-send").disabled = false; }
    }

    function renderResp(r) {
        const ok = r.status >= 200 && r.status < 400;
        const hdrs = Object.entries(r.headers || {}).map(([k, v]) => k + ": " + v).join("\n");
        $("#api-resp").innerHTML =
            '<div class="api-status">' +
            '<span class="code ' + (ok ? "ok" : "ko") + '">' + esc(r.status) + " " + esc(r.reason || "") + "</span>" +
            '<span class="ms">' + esc(r.elapsed_ms) + " ms</span></div>" +
            "<pre>" + esc(hdrs) + "\n\n" + esc(r.body || "") + "</pre>";
    }

    function mount(el, ctx) {
        EL = el; CTX = ctx;
        $("#api-send").onclick = send;
        $("#api-url").addEventListener("keydown", (e) => { if (e.key === "Enter") send(); });
        loadHistory();
    }
    function unmount() { EL = null; CTX = null; }

    return { mount, unmount };
})();
