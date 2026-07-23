"""
Cycle de synchronisation des DB officielles.

Vérification légère via l'endpoint dédié de l'API (préfixe fixe 'en-en') :
  GET {API_BASE_URL}/en-en/langue-releases/all-new-updates?langs[]=...
qui renvoie directement la date de dernière mise à jour de 'common' et de
chaque langue, SANS jamais avoir besoin de télécharger common.db.

Le téléchargement effectif des DB de langue reste inchangé (db_downloader.download_database),
via l'endpoint {API_BASE_URL}/{initial}/download-url avec l'initial propre à chaque langue --
ces deux endpoints ne sont jamais mélangés.

Seules les DB de langue (matth25v6_XX.db) dont la date a changé -- ou dont le
fichier local est absent -- sont (re)téléchargées.
"""
import logging
from pathlib import Path

import config
import db_downloader
import state_db

logger = logging.getLogger(__name__)


def lang_db_path(lang: str) -> Path:
    return config.DB_DIR / f"matth25v6_{lang}.db"


def sync_official_databases() -> list:
    """
    Exécute un cycle complet de vérification/synchronisation des DB officielles.
    Retourne la liste des langues dont le .db a été (re)téléchargé (donc à traiter ensuite).
    """
    raw_updates = db_downloader.fetch_all_updates()  # clés = valeurs API_INITIALS ('common','fr-fr',...)

    api_key_for = {"common": config.API_INITIALS["common"]}
    api_key_for.update({lang: config.API_INITIALS[lang] for lang in config.LANGUAGES})

    known_updates = state_db.get_all_known_updates()  # clés = codes langue internes ('common','fr',...)

    changed_langs = []
    for lang in ["common"] + config.LANGUAGES:
        api_key = api_key_for[lang]
        remote_value = raw_updates.get(api_key)
        if remote_value is None:
            logger.warning(
                "Pas de updated_at renvoyé par l'API pour '%s' (clé attendue %r), ignoré ce cycle.",
                lang, api_key,
            )
            continue

        known_value = known_updates.get(lang)
        db_missing = lang != "common" and not lang_db_path(lang).exists()

        if lang != "common" and (remote_value != known_value or db_missing):
            logger.info(
                "Langue '%s' modifiée ou DB locale absente (%s -> %s), téléchargement.",
                lang, known_value, remote_value,
            )
            db_downloader.download_database(lang)
            changed_langs.append(lang)

        if remote_value != known_value:
            state_db.set_known_update(lang, remote_value)

    if not changed_langs:
        logger.info("Aucune langue modifiée (vérification légère via all-new-updates, sans téléchargement de DB).")

    return changed_langs
