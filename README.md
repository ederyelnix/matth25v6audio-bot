# Bot Telegram — Matthieu 25:6 (FR/EN/PT/ES)

## Installation

```bash
pip install -r requirements.txt
cp .env.example .env
```

Puis remplir `.env` :
- `BOT_TOKEN` : token du bot (via @BotFather)
- `CHANNEL_ID_FR/EN/PT/ES` : ID numérique de chaque canal (le bot doit être admin dessus)
- `API_INITIAL_EN/PT/ES` : **à vérifier**, seule la valeur `fr-fr` est confirmée (vue dans le code C++ existant). Les valeurs par défaut (`en-en`, `pt-pt`, `es-es`) sont une supposition à valider auprès de l'API avant le premier lancement.

## Étape unique avant le premier lancement : import de l'historique du canal FR

Le canal FR contient déjà 179 prédications (Kacou 100 manquant). Pour ne pas les republier en double :

```bash
python import_channel_history.py chemin/vers/result.json --language fr
```

Ce fichier `result.json` s'obtient via Telegram Desktop : clic droit sur le canal FR → Exporter l'historique du chat → décocher tout sauf le format JSON (aucun fichier audio n'est téléchargé, uniquement les métadonnées).

Ce script ne concerne QUE le canal FR. EN/PT/ES n'existent pas encore : rien à importer pour eux, le bot partira de zéro.

## Lancement

```bash
python main.py
```

Le premier cycle de sync se déclenche 10 secondes après le démarrage, puis toutes les `SYNC_INTERVAL_SECONDS` (6h par défaut, réglable dans `.env`).

## Ce qui n'a pas encore été testé en conditions réelles

Faute d'accès à un vrai bot Telegram (token) et aux vraies URLs de l'API pendant la conception :
- Le téléchargement réel depuis `api.philippekacou.org` (le format de réponse JSON est reproduit d'après le code C++, mais pas rejoué en vrai)
- L'envoi et l'édition de messages audio dans un vrai canal Telegram (`send_audio` / `edit_message_media`)
- Les valeurs `API_INITIAL_EN/PT/ES`

Tout le reste (compression ffmpeg, structure de la DB locale, import de l'historique FR, logique de comparaison `updated_at`) a été testé avec de vraies données pendant la conception.

## Structure des fichiers

| Fichier | Rôle |
|---|---|
| `config.py` | Configuration centrale (chemins, tokens, canaux) |
| `db_downloader.py` | Téléchargement des DB officielles via l'API |
| `official_db.py` | Lecture seule des DB officielles (common.db, matth25v6_XX.db) |
| `db_sync.py` | Cycle de rotation common.db/old.db et détection des langues changées |
| `state_db.py` | DB locale du bot (users, published_sermons) |
| `import_channel_history.py` | Script d'import ponctuel de l'historique du canal FR |
| `audio_processing.py` | Téléchargement + compression ffmpeg (MP3 32kbps mono) |
| `i18n.py` | Traductions des textes de l'interface (FR/EN/PT/ES) |
| `sync_service.py` | Orchestration : sync DB → publication/édition dans les canaux |
| `bot.py` | Interaction utilisateur (/start, menus, grille, forward) |
| `main.py` | Point d'entrée |
