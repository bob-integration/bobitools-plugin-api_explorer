# Explorateur d'API — plugin Bobi.Tools

Un client HTTP dans le navigateur pour [Bobi.Tools](https://github.com/bob-integration/bobitools) :
on compose une requête, elle part **du serveur**, et on lit la réponse. C'est aussi
l'exemple de référence d'un outil **in-process** avec `backend.py`.

## Ce que fait l'outil

- Compose une requête : méthode (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS), URL,
  en-têtes, corps.
- L'envoie depuis le serveur : pas de CORS, et les équipements du réseau local sont joignables.
- Affiche statut, durée, en-têtes et corps de la réponse (tronqué au-delà de 200 Ko).
- Garde un **historique** de requêtes, propre à chaque utilisateur.

## Pour les développeurs

[`backend.py`](backend.py) est court et commenté : c'est le point de départ pour écrire un
outil in-process. Le contrat tient en une fonction :

```python
def api(path, method, payload, ctx):   # -> data | (status, data)
```

`path` est le chemin après `/api/tools/api_explorer/`, `payload` le corps JSON (ou la query
d'un GET), et `ctx` donne l'utilisateur, un stockage propre à l'outil (`store`), les réglages
(`setting`), le journal d'audit (`audit`) et le dossier du plugin (`tool_dir`). On y voit aussi
comment cloisonner des données par utilisateur et masquer un secret avant de l'enregistrer.

## Prérequis

- Aucun : l'outil tourne dans Bobi.Tools.

## Installation

Dans Bobi.Tools : **Réglages → Outils → Catalogue**, bouton « Installer ». Ou, sur une machine
neuve, en une ligne :

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/bob-integration/bobitools/main/get.sh) --outils api_explorer
```

## Sécurité

- Les requêtes partent du serveur. Sont refusées : la boucle locale (l'application et ses
  conteneurs), les adresses link-local (dont les métadonnées cloud), multicast et réservées ;
  les redirections ne sont pas suivies. Les adresses privées restent autorisées.
- Chaque requête est inscrite au journal d'audit (méthode et URL).
- Dans l'historique, la valeur des en-têtes d'authentification (`Authorization`, `Cookie`,
  jetons…) est masquée : il faut la retaper pour rejouer la requête.

## In English

A server-side HTTP client for Bobi.Tools: method, URL, headers and body, response with
status, timing and headers, and a per-user history with authentication headers masked.
Loopback, link-local and reserved targets are refused and redirects are not followed.
`backend.py` is the reference example of an in-process tool (`api(path, method, payload, ctx)`).

## Licence

GPL-3.0-or-later — © 2026 BOBI SAS. Voir [LICENSE](LICENSE).
