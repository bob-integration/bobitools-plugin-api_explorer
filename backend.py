# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BOBI SAS, France
# Auteur : Cyril Mazouer, pour le compte de BOBI SAS
# Distribué sous licence GNU GPL v3 (ou ultérieure) ; voir le fichier LICENSE.

"""
Backend in-process de l'outil « Explorateur d'API ».

Contrat d'un backend Bobi.Tools (runtime=inprocess) :

    def api(path, method, payload, ctx) -> data | (status, data)

- `path`    : segment(s) après /api/tools/<type>/ (ici : "request")
- `method`  : verbe HTTP de l'appel entrant
- `payload` : corps JSON (POST/PUT) ou query (GET), déjà parsé en dict
- `ctx`     : { user, store, setting, audit, tool_dir }
    - ctx["store"]  : stockage générique scopé à l'outil (list/get/create/update/delete)
    - ctx["setting"](clé) : réglage (clé spécifique outil `api_explorer__clé`, sinon globale)
    - ctx["audit"](action, detail) : journalise dans le journal d'audit
    - ctx["tool_dir"] : dossier du plugin sur disque

La requête HTTP part **du serveur** : ni CORS, ni exposition de secrets au navigateur.
"""
import time
import requests

_ALLOWED = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}
_MAX_BODY = 200_000   # tronque les réponses énormes pour ne pas gonfler l'UI


def api(path, method, payload, ctx):
    if path == "request" and method == "POST":
        return _do_request(payload, ctx)
    return 404, {"error": "route inconnue"}


def _do_request(payload, ctx):
    url = (payload.get("url") or "").strip()
    if not url.startswith(("http://", "https://")):
        return 400, {"error": "URL http(s) requise"}
    verb = (payload.get("method") or "GET").upper()
    if verb not in _ALLOWED:
        return 400, {"error": f"méthode non autorisée : {verb}"}
    headers = payload.get("headers") if isinstance(payload.get("headers"), dict) else {}
    body = payload.get("body")

    ctx["audit"](verb, url)   # qui a tapé quelle URL → journal d'audit
    t0 = time.time()
    try:
        r = requests.request(verb, url, headers=headers,
                             data=body if isinstance(body, str) and body else None,
                             timeout=20, allow_redirects=True)
    except requests.RequestException as e:
        return 502, {"error": str(e)}
    elapsed = int((time.time() - t0) * 1000)

    text = r.text or ""
    truncated = len(text) > _MAX_BODY
    if truncated:
        text = text[:_MAX_BODY] + "\n…(réponse tronquée)"
    return 200, {
        "status": r.status_code,
        "reason": r.reason,
        "elapsed_ms": elapsed,
        "headers": dict(r.headers),
        "body": text,
        "truncated": truncated,
    }
