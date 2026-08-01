// SPDX-License-Identifier: GPL-3.0-or-later
// Explorateur d'API — outil Bobi.Tools (runtime=inprocess + backend.py). L'UI envoie la
// requête au backend via ctx.api("request", …) ; le backend la rejoue côté serveur et
// renvoie status/headers/body. L'historique passe lui aussi par le backend (route
// "history") : la route générique /store range tout sous un scope commun et n'aurait donc
// pas cloisonné les requêtes — en-têtes compris — entre les utilisateurs de l'outil.
window.BTTools = window.BTTools || {};
window.BTTools.api_explorer = (function () {
    let EL = null, CTX = null, history = [];
    const esc = (s) => String(s == null ? "" : s)
        .replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    const $ = (sel) => EL.querySelector(sel);

    async function loadHistory() {
        try { history = await CTX.api("history"); } catch (e) { history = []; }
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
            // Persiste dans l'historique (nom = URL, valeur = paramètres rejouables) :
            // le backend range sous le scope de l'utilisateur et masque les en-têtes
            // d'authentification — leur valeur ne revient donc pas dans le champ.
            // `headers` ANALYSÉ, pas la chaîne brute : le dispatch journalise la charge utile
            // et son masquage opère par nom de clé — une chaîne JSON passerait en clair dans
            // l'audit, avec le jeton dedans.
            await CTX.api("history", { body: { url, method, headers, body } });
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
