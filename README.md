# Bot Telegram — Matthieu 25:6 (FR/EN/PT/ES)

Bot Telegram qui publie et met à jour automatiquement les prédications audio
de Matthieu 25:6 dans quatre canaux (un par langue), à partir des bases de
données officielles utilisées par les applications et le site web.

## Installation

```bash
pip install -r requirements.txt
cp .env.example .env
```

Puis remplir `.env` :

- `BOT_TOKEN` : token du bot (via @BotFather)
- `CHANNEL_ID_FR/EN/PT/ES` : ID numérique de chaque canal (le bot doit être admin dessus)

Les autres variables (`API_BASE_URL`, `API_INITIAL_*`, `SYNC_INTERVAL_SECONDS`,
chemins de stockage) ont des valeurs par défaut fonctionnelles et n'ont pas
besoin d'être modifiées, sauf besoin spécifique.

## Étape unique avant le premier lancement : import de l'historique du canal FR

Le canal FR contient déjà des prédications publiées manuellement avant la mise
en place du bot. Pour ne pas les republier en double :

```bash
python import_channel_history.py chemin/vers/result.json --language fr
```

`result.json` s'obtient via Telegram Desktop : clic droit sur le canal FR →
Exporter l'historique du chat → décocher tout sauf le format JSON (aucun
fichier audio n'est téléchargé, uniquement les métadonnées).

Ce script ne concerne que le canal FR. Pour EN/PT/ES, rien à importer : le
bot les publie depuis zéro.

## Lancement

```bash
python main.py
```

Le premier cycle de vérification se déclenche 10 secondes après le démarrage,
puis toutes les `SYNC_INTERVAL_SECONDS` (10 minutes par défaut). Chaque cycle
interroge l'API pour savoir si une langue a été mise à jour côté serveur ; si
oui, la base de données correspondante est retéléchargée puis les
prédications concernées sont publiées ou mises à jour dans le canal.

## Structure des fichiers

| Fichier | Rôle |
|---|---|
| `config.py` | Configuration centrale (chemins, tokens, canaux) |
| `db_downloader.py` | Téléchargement des DB officielles et vérification légère des mises à jour, via l'API |
| `official_db.py` | Lecture seule des DB officielles (matth25v6_XX.db) |
| `db_sync.py` | Détection des langues mises à jour et (re)téléchargement de leur DB |
| `state_db.py` | DB locale du bot (utilisateurs, prédications publiées, dernières dates connues) |
| `import_channel_history.py` | Script d'import ponctuel de l'historique du canal FR |
| `audio_processing.py` | Téléchargement + compression ffmpeg (MP3 32kbps mono, métadonnées ID3, pochette préservée) |
| `i18n.py` | Traductions des textes de l'interface (FR/EN/PT/ES) |
| `sync_service.py` | Orchestration : vérification des DB, publication/édition dans les canaux |
| `bot.py` | Interaction utilisateur (choix de langue, sélection des prédications, envoi) |
| `main.py` | Point d'entrée |

## Déploiement

Le bot est conçu pour tourner en continu sur un serveur (VPS). Il ne nécessite
qu'un Python 3.12+, ffmpeg installé sur le système, et les dépendances du
`requirements.txt`.
