"""
Téléchargement des DB officielles depuis l'API philippekacou.org.
Réplique exactement la logique du code C++ fourni (telecharger_base_donnees) :
  1. GET {API_BASE_URL}/{initial}/download-url -> JSON {"download_url": "..."}
  2. Téléchargement du fichier à cette URL
"""
import logging
import requests

import config

logger = logging.getLogger(__name__)


def _db_filename(language_or_common: str) -> str:
    """Nom de fichier local pour une DB donnée ('common' ou un code langue fr/en/pt/es)."""
    if language_or_common == "common":
        return "common.db"
    return f"matth25v6_{language_or_common}.db"


def fetch_all_updates() -> dict:
    """
    Interroge GET {API_BASE_URL}/en-en/langue-releases/all-new-updates?langs[]=X
    UNE FOIS PAR LANGUE (appel séparé, un seul langs[] par requête -- pas de lien
    général avec plusieurs langs[] regroupés, qui ne renvoyait pas correctement
    tout le monde).
    Le préfixe 'en-en' dans l'URL est FIXE (propre à cet endpoint), peu importe
    la langue demandée dans langs[] -- ce n'est pas API_INITIALS["common"].
    Retourne un dict fusionné : {"common": "...", "fr-fr": "...", ...}
    (clés = valeurs API_INITIALS, pas nos codes langue internes).
    """
    ALL_UPDATES_PREFIX = "en-en"
    langs_requested = [config.API_INITIALS["common"]] + [config.API_INITIALS[lang] for lang in config.LANGUAGES]
    url = f"{config.API_BASE_URL}/{ALL_UPDATES_PREFIX}/langue-releases/all-new-updates"

    result = {}
    for code in langs_requested:
        resp = requests.get(url, params=[("langs[]", code)], timeout=30)
        resp.raise_for_status()
        for entry in resp.json():
            result[entry["langue"]] = entry["updated_at"]
    return result


def fetch_download_url(initial: str) -> str:
    """Appelle l'API pour obtenir l'URL de téléchargement réelle du fichier .db."""
    url = f"{config.API_BASE_URL}/{initial}/download-url"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    download_url = data.get("download_url")
    if not download_url:
        raise ValueError(f"Réponse API sans 'download_url' pour initial={initial!r} : {data}")
    return download_url


def download_database(language_or_common: str) -> "Path":
    """
    Télécharge la DB ('common' ou un code langue) et la place dans config.DB_DIR.
    Retourne le chemin du fichier téléchargé.
    """
    initial = config.API_INITIALS[language_or_common]
    filename = _db_filename(language_or_common)
    dest_path = config.DB_DIR / filename

    logger.info("Récupération de l'URL de téléchargement pour %s (initial=%s)", filename, initial)
    download_url = fetch_download_url(initial)

    logger.info("Téléchargement de %s...", filename)
    resp = requests.get(download_url, timeout=120, stream=True)
    resp.raise_for_status()

    tmp_path = dest_path.with_suffix(dest_path.suffix + ".part")
    with open(tmp_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 256):
            f.write(chunk)
    tmp_path.replace(dest_path)

    logger.info("DB téléchargée : %s", dest_path)
    return dest_path
