# alin-monitor

Assistant personnel de veille sur les offres de logement social publiées sur
le site AL'in (Action Logement). Il surveille les nouvelles annonces, les
compare à des critères configurables, et envoie une notification Telegram
quand une offre correspond.

**alin-monitor ne soumet jamais de candidature automatiquement.** C'est un
outil de veille et de notification : la décision et l'action de candidater
restent entièrement manuelles, faites par vous, sur le site officiel.

## Installation

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install --with-deps chromium  # local uniquement, cf. Fallback ci-dessous
```

## Configuration

1. Copier `.env.example` vers `.env` et renseigner :
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (créez un bot via @BotFather)
   - `ALIN_EMAIL`, `ALIN_PASSWORD`, `ALIN_LOGIN_URL` (voir section
     [Authentification](#authentification) pour le choix de stockage du mot
     de passe et les précautions associées)
   - `CHECK_INTERVAL_SECONDS` (défaut : 180s — restez raisonnable)
   - `SCORE_THRESHOLD`, chemins de la base et du storage_state, niveau de log

2. Adapter `config/criteria.yaml` à votre recherche : villes, types de
   logement, loyer max, surface min, etc., ainsi que la pondération du
   score (`scoring.poids`) et le seuil de déclenchement
   (`scoring.score_threshold`).

## Architecture

alin-monitor est un harnais **multi-source** : chaque site surveillé vit
dans son propre paquet `app/sources/<nom_source>/`, avec la même forme
(`auth.py`, `scraper.py`, `parser.py`, éventuellement `browser.py` pour un
fallback manuel). `app/sources/base.py` définit le contrat commun (`Source`,
`SourceClient`) utilisé par `app/main.py` pour boucler sur les sources
actives (`enabled: true` dans `config/criteria.yaml`, cf. section
[Configuration](#configuration)), et centralise le rappel éthique valable
pour toute source ajoutée au projet.

Seule `app/sources/alin/` est aujourd'hui implémentée. En fonctionnement
normal, alin-monitor ne pilote **aucun navigateur** pour cette source : il
parle directement à l'API AL'in en HTTP (via `httpx`, async) :

1. `app/sources/alin/auth.py` (`AlinAuthClient`) s'authentifie par
   POST sur l'endpoint Keycloak "direct grant" d'AL'in
   (`https://api.be-ys.com/als-back/v1/accounts/authenticate`) avec l'email
   et le mot de passe, et obtient un `access_token` (valide ~900s). Le
   token est ré-authentifié proactivement (rejeu du même POST) avant
   expiration, avec une marge de sécurité — aucun endpoint de "refresh"
   distinct n'a été identifié dans le trafic observé.
2. `app/sources/alin/scraper.py` (`fetch_active_offers`) interroge
   `GET https://api.al-in.fr/api/dmo/housing_offers`, paginé, filtré sur la
   fenêtre de publication courante.
3. `app/sources/alin/parser.py` (`parse_offer`) transforme chaque offre
   brute en objet `Offer` (app/database/models.py), avec extraction
   défensive (JSON:API `attributes` ou format plat en repli).
4. `app/filters/criteria.py` et `app/filters/scoring.py` filtrent/scorent
   les offres selon `config/criteria.yaml` (critères communs, avec overrides
   optionnels par source).
5. Les nouvelles offres au-dessus du seuil de score sont notifiées via
   Telegram (`app/notifications/telegram.py`), et persistées en SQLite
   (`app/database/db.py`), avec la source d'origine (clé composite
   `(source, id)` : deux sources peuvent réutiliser le même identifiant
   externe sans collision).

### `app/sources/logement_actionlogement/` — second site Action Logement

Surveille `logement-actionlogement.fr` en **mode public sans
authentification** (autorisé par ses CGU, art. 11.16) : pas de compte, pas
de token, `app/sources/logement_actionlogement/auth.py` est un simple
passe-plat pour respecter le `Protocol SourceClient`.

1. `app/sources/logement_actionlogement/scraper.py` (`fetch_active_offers`)
   interroge `POST /api/v1/demands/public/offers-overview`, paginé. La
   recherche est géographique et **obligatoire** côté API (pas de mode
   "tout afficher" nationwide) : municipalité(s), rayon (km), loyer max,
   typologies — ces paramètres viennent de `config/criteria.yaml`
   (`sources.logement_actionlogement.search`), pas de `Criteria` (aucun
   champ commun ne correspond à un code INSEE ou un rayon).
2. `app/sources/logement_actionlogement/parser.py` (`parse_offer`)
   transforme chaque élément résumé en objet `Offer`. Seuls les champs
   exposés par le résumé liste sont peuplés (pas d'appel détail par offre,
   pour éviter les requêtes N+1) : `floor`/`has_elevator`/`parking_type`/
   `balconies` restent `None`.
3. URL de fiche individuelle confirmée par observation directe :
   `https://logement-actionlogement.fr/search/detail/<guid>`.

**Checklist pour ajouter/activer une nouvelle source** :

1. Lire les CGU du site (veille automatisée acceptable ou non, comme fait
   pour AL'in).
2. Observer légitimement son trafic réseau (onglet Network du navigateur,
   connecté à son propre compte) pour identifier auth, endpoint liste des
   offres, et structure d'une offre.
3. Remplir les stubs `auth.py`/`scraper.py`/`parser.py` du paquet
   `app/sources/<nom_source>/` sur le modèle de `app/sources/alin/`.
4. Ajouter des critères par défaut dans `config/criteria.yaml` si
   nécessaire, et passer la source à `enabled: true`.
5. Valider avec des tests unitaires du parser (sur le modèle de
   `tests/test_parser.py`) avant tout déploiement.

**Provenance de la structure de l'API** : cette structure (endpoints,
en-têtes, forme des réponses) a été identifiée par observation légitime du
trafic réseau de l'utilisateur (onglet Network de son propre navigateur),
pendant qu'il était connecté à son propre compte AL'in. Ce n'est ni de la
rétro-ingénierie d'une protection anti-bot, ni un contournement de quoi que
ce soit : la clé `x-gexrt-api-key` utilisée est d'ailleurs une valeur
**publique**, exposée à tout visiteur non authentifié via
`https://al-in.fr/info`.

**Incertitude connue** : seul l'endpoint détail
(`GET /housing_offers/<id>`) a été confirmé avec de vraies données. La
forme exacte des éléments de `data[]` retournés par l'endpoint **liste**
(`GET /housing_offers`) n'a **pas** été confirmée par observation directe
(résultats vides lors des tests). Le parsing est donc défensif : il gère à
la fois l'enveloppe JSON:API (`{"attributes": {...}}`) et un éventuel format
plat, et logue un avertissement (une seule fois) si le format plat est
utilisé — à surveiller dans les logs lors des premiers cycles réels.

**Limite connue sur le "quartier"** : l'API n'expose aucun champ "quartier"
dédié. Le champ `district`, malgré son nom, contient en réalité le nom de la
**commune** (ex: "Ivry-sur-Seine"), pas un quartier. Le filtre `quartiers`
de `config/criteria.yaml` est donc appliqué en **best-effort uniquement**,
par recherche de sous-chaîne (insensible à la casse/accents) dans l'adresse
de l'offre — ce n'est pas un filtre fiable : une offre dans le bon quartier
mais dont l'adresse ne le mentionne pas textuellement sera manquée, et
inversement une correspondance fortuite peut se produire.

## Authentification

Le mot de passe AL'in est stocké dans la variable d'environnement
`ALIN_PASSWORD` du fichier `.env` (et non saisi de manière interactive à
chaque démarrage). C'est un choix assumé : il permet au service de
redémarrer seul sur un VPS (ex: après un reboot ou un crash) sans
intervention manuelle à chaque restart.

**Compromis sécurité/disponibilité** : cela signifie que le mot de passe
est présent en clair sur le disque du serveur, dans `.env`. Pour limiter le
risque :

- Ne committez **jamais** `.env` (seul `.env.example`, avec des valeurs
  factices, doit être versionné).
- Une fois `.env` rempli avec les vraies valeurs sur le serveur, restreignez
  ses permissions : `chmod 600 .env`.
- Utilisez idéalement un utilisateur dédié (non root, sans autres services)
  pour exécuter alin-monitor sur le VPS, afin de limiter la surface
  d'exposition de ce fichier.

L'email et le mot de passe sont envoyés directement à l'API AL'in
(`app/sources/alin/auth.py`, flow httpx). Aucune étape MFA/OTP n'a été observée sur
ce flow à ce jour (c'est un flow Keycloak "direct grant" simple). Si l'API
se met à refuser l'authentification de façon inattendue (statut 4xx), le
programme ne tente **jamais** de deviner ou contourner quoi que ce soit :
après plusieurs tentatives infructueuses, il logge clairement l'échec,
envoie une alerte Telegram, puis bascule vers un fallback Playwright
(`app/sources/alin/browser.py`) qui ouvre un navigateur visible et attend une
intervention manuelle complète de votre part (y compris une éventuelle
MFA/CAPTCHA).

## Gestion des secrets avec sops + age

Par défaut, les secrets vivent en clair dans `.env` (jamais commité). Pour
éviter d'avoir un fichier de secrets en clair sur disque en continu, le
projet supporte le chiffrement via [sops](https://github.com/getsops/sops) +
[age](https://github.com/FiloSottile/age) : `.env` reste ton fichier de
travail local, `.env.enc` est sa version chiffrée, committable sans risque.

### Mise en place (une fois par machine — poste perso ET VPS)

1. Installer les outils :
   ```bash
   brew install age sops        # macOS
   # ou apt install age sops    # Debian/Ubuntu (paquets récents), sinon binaires GitHub releases
   ```
2. Générer une paire de clés `age` (à faire **une seule fois**, puis copier
   la clé privée sur chaque machine qui doit déchiffrer — jamais dans le
   repo Git) :
   ```bash
   mkdir -p ~/.config/alin-monitor
   age-keygen -o ~/.config/alin-monitor/age-key.txt
   chmod 600 ~/.config/alin-monitor/age-key.txt
   ```
3. Reporter la clé **publique** affichée (`age1...`) dans `.sops.yaml` à la
   racine du projet (déjà fait pour la clé générée lors de la mise en place
   initiale — régénère `.sops.yaml` si tu crées ta propre clé).
4. Exporter la variable d'environnement pointant vers la clé privée (à
   ajouter dans ton `.zshrc`/`.bashrc`, ou dans le service systemd sur le
   VPS) :
   ```bash
   export SOPS_AGE_KEY_FILE=~/.config/alin-monitor/age-key.txt
   ```

### Utilisation au quotidien

- Après avoir modifié `.env` : régénérer `.env.enc` avec
  `./scripts/encrypt-env.sh`, puis commit `.env.enc` (jamais `.env`).
- Pour lancer le programme en déchiffrant les secrets **à la volée** (rien
  n'est jamais écrit en clair sur disque) : `./scripts/run.sh` au lieu de
  `python -m app.main` directement. Ce script appelle
  `sops exec-env .env.enc "python -m app.main"`, qui injecte les secrets
  déchiffrés uniquement dans l'environnement du process enfant.
- **Déployer sur le VPS** : copier `age-key.txt` sur le VPS via `scp` (ou
  équivalent) dans `~/.config/alin-monitor/`, jamais via Git ; cloner le
  repo (qui contient `.env.enc`, chiffré, sans risque) ; lancer via
  `scripts/run.sh`.
- **Perte de la clé privée `age`** = perte d'accès à `.env.enc` de façon
  irréversible. Fais-en une sauvegarde hors ligne (gestionnaire de mots de
  passe, clé USB chiffrée) — ce n'est *pas* un secret à conserver uniquement
  sur une seule machine.

Ce mécanisme est optionnel : `.env` en clair (avec `chmod 600`, cf. section
précédente) reste supporté et suffisant pour un usage strictement local.

## Lancement avec Docker

```bash
docker compose up -d --build
```

Le conteneur n'a pas d'affichage graphique : Chromium n'y est pas installé,
et `ENABLE_MANUAL_FALLBACK=false` (forcé par le Dockerfile) désactive le
fallback Playwright. En cas d'échec d'authentification répété, une alerte
Telegram vous demande d'investiguer en local (`ENABLE_MANUAL_FALLBACK=true`
par défaut sur votre poste, `playwright install --with-deps chromium`
requis).

## Tests

```bash
pytest
```

## État du projet

Le flow nominal (authentification + récupération des offres + parsing +
filtrage/scoring + notification Telegram) est implémenté en httpx, à partir
d'une structure d'API identifiée par observation légitime du trafic réseau
de l'utilisateur (cf. section Architecture ci-dessus). Deux incertitudes
restent à lever à l'usage réel :

- la forme exacte de `data[]` sur l'endpoint **liste** des offres (jamais
  observée avec de vraies données à ce stade) — le parsing est défensif en
  conséquence ;
- le filtre "quartier", nécessairement best-effort en l'absence de champ
  dédié côté API.

Le fallback Playwright (`app/sources/alin/browser.py`) reste un squelette partiel
(sélecteurs de détection de session/MFA en TODO) : il n'a volontairement
pas été développé plus avant tant qu'il n'a pas été réellement nécessaire
en pratique, pour éviter de deviner des sélecteurs sur un flow qui ne s'est
jamais présenté.

## Limites et éthique

- **Aucun contournement de CAPTCHA, MFA ou protection anti-bot** n'est
  implémenté ni prévu, à aucun moment du projet.
- **Aucune candidature n'est jamais soumise automatiquement.** L'outil se
  limite à observer et notifier ; toute action de candidature reste
  manuelle, sur le site officiel.
- Si une vérification d'identité (MFA, code, CAPTCHA) est détectée ou
  suspectée (échec d'authentification inattendu), le programme ne tente
  jamais de la deviner ou de la contourner : il notifie l'utilisateur et
  bascule vers une intervention manuelle (fallback Playwright).
- La fréquence de vérification par défaut (180s) est volontairement
  conservatrice. Elle est configurable, mais il est recommandé de vérifier
  les conditions d'utilisation du site AL'in avant de la réduire.
- Le filtre "quartier" est une approximation best-effort (recherche de
  sous-chaîne dans l'adresse), pas un filtre fiable : cf. section
  Architecture.
