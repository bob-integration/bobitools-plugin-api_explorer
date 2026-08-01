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
import ipaddress
import json
import socket
import time
from urllib.parse import urlparse

import requests

_ALLOWED = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}
_MAX_BODY = 200_000   # tronque les réponses énormes pour ne pas gonfler l'UI
# En-têtes porteurs d'identifiants : leur VALEUR ne doit jamais entrer dans l'historique.
_ENTETES_SECRETS = ("authorization", "cookie", "token", "api-key", "apikey",
                    "secret", "password", "x-auth")


def _is_blocked_ip(ip):
    """Bloque les cibles dangereuses d'une SSRF : boucle locale (l'app + les ports
    dynamiques des conteneurs Docker), link-local / métadonnées cloud (169.254.169.254),
    et l'adresse « non spécifiée ». Le RFC1918 reste autorisé : explorer les équipements
    du LAN est la vocation de l'outil."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True   # non résoluble en IP → on refuse par prudence
    return (addr.is_loopback or addr.is_link_local
            or addr.is_multicast or addr.is_unspecified or addr.is_reserved)


def _resolve_is_safe(host):
    """Résout `host` et refuse si UNE des adresses tombe dans une plage bloquée
    (protège aussi du DNS-rebinding vers loopback/link-local)."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False, "hôte non résoluble"
    for info in infos:
        ip = info[4][0]
        if _is_blocked_ip(ip):
            return False, f"cible interdite ({ip})"
    return True, None


def _scope(ctx):
    """Cloisonne l'historique par utilisateur.

    La table `plugin_store` n'a PAS de colonne propriétaire : tout ce qui est rangé sous le
    même scope est relu par quiconque a accès à l'outil. L'historique était écrit sous le
    scope vide depuis le navigateur, donc les requêtes de chacun — en-têtes et corps tapés à
    la main — étaient lisibles par tous les autres. Le scope `u<id>` rend chaque historique
    privé, car `plugin_store_list` filtre sur (type, scope)."""
    u = ctx["user"] or {}
    return "u%s" % (u.get("id") or u.get("username") or "?")


def _redact_headers(raw):
    """Masque la VALEUR des en-têtes d'authentification avant rangement.

    Le nom de l'en-tête est conservé : rejouer une requête reste possible, il ne reste qu'à
    retaper le jeton. Ce qui est écrit ici survit à l'écran — la base est recopiée chaque
    nuit par la sauvegarde SQLite —, donc un « Authorization: Basic … » enregistré tel quel
    est un identifiant qui traîne pendant des mois dans les archives."""
    # Un DICT est accepté en plus de la chaîne, et c'est ce que le front envoie désormais.
    # La raison n'est pas cosmétique : le dispatch du cœur journalise la charge utile après
    # `_redact`, qui masque par NOM DE CLÉ. Un objet {"Authorization": "Basic …"} y est donc
    # masqué, alors qu'une CHAÎNE JSON de moins de 200 caractères traverse intacte et écrit
    # le jeton en clair dans la table d'audit — recopiée chaque nuit par la sauvegarde.
    # Masquer ici sans envoyer un dict revenait à déplacer le secret, pas à le supprimer.
    if isinstance(raw, dict):
        d = raw
    elif isinstance(raw, str) and raw.strip():
        try:
            d = json.loads(raw)
        except ValueError:
            return ""   # illisible : on préfère ne rien garder que du texte brut non inspecté
    else:
        return ""
    if not isinstance(d, dict):
        return ""
    return json.dumps({k: ("…" if any(s in str(k).lower() for s in _ENTETES_SECRETS) else v)
                       for k, v in d.items()}, ensure_ascii=False)


def _history_add(payload, ctx):
    url = (payload.get("url") or "").strip()
    if not url:
        return 400, {"error": "URL requise"}
    sid = ctx["store"].create(url, {"method": (payload.get("method") or "GET"),
                                    "headers": _redact_headers(payload.get("headers")),
                                    "body": payload.get("body") or ""},
                              scope=_scope(ctx))
    return 200, {"id": sid}


def api(path, method, payload, ctx):
    if path == "request" and method == "POST":
        return _do_request(payload, ctx)
    # L'historique passe par le backend et NON par la route générique /store : lui seul
    # connaît l'utilisateur courant, donc lui seul peut cloisonner et masquer (cf. _scope).
    if path == "history" and method == "GET":
        return 200, ctx["store"].list(scope=_scope(ctx))
    if path == "history" and method == "POST":
        return _history_add(payload, ctx)
    return 404, {"error": "route inconnue"}


def _do_request(payload, ctx):
    url = (payload.get("url") or "").strip()
    if not url.startswith(("http://", "https://")):
        return 400, {"error": "URL http(s) requise"}
    host = (urlparse(url).hostname or "").strip()
    if not host:
        return 400, {"error": "URL sans hôte"}
    ok, why = _resolve_is_safe(host)
    if not ok:
        return 400, {"error": f"URL refusée : {why}"}
    verb = (payload.get("method") or "GET").upper()
    if verb not in _ALLOWED:
        return 400, {"error": f"méthode non autorisée : {verb}"}
    headers = payload.get("headers") if isinstance(payload.get("headers"), dict) else {}
    body = payload.get("body")

    ctx["audit"](verb, url)   # qui a tapé quelle URL → journal d'audit
    t0 = time.time()
    try:
        # allow_redirects=False : un 3xx vers une cible interne contournerait la garde
        # SSRF (la redirection n'est pas re-validée). Le 3xx + Location est renvoyé tel quel.
        r = requests.request(verb, url, headers=headers,
                             data=body if isinstance(body, str) and body else None,
                             timeout=20, allow_redirects=False)
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
