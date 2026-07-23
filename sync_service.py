"""
Orchestration complète du cycle de synchronisation :
  1. Synchronise les DB officielles (db_sync)
  2. Pour chaque langue dont la DB a changé, compare les sermons avec l'état local
  3. Télécharge + compresse + publie/édite les prédications concernées dans le canal
"""
import asyncio
import logging

from telegram import Bot, InputMediaAudio
from telegram.error import NetworkError, TimedOut

import audio_processing
import config
import db_sync
import official_db
import state_db

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
RETRY_DELAYS_SECONDS = (10, 30)  # attente avant la 2e et la 3e tentative


async def _with_retries(coro_fn, *, label: str):
    """Exécute coro_fn() en retentant sur TimedOut/NetworkError avec backoff.
    Relance la dernière exception si toutes les tentatives échouent."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return await coro_fn()
        except (TimedOut, NetworkError) as exc:
            if attempt == MAX_ATTEMPTS:
                logger.error("%s : échec définitif après %s tentatives (%s)", label, MAX_ATTEMPTS, exc)
                raise
            delay = RETRY_DELAYS_SECONDS[attempt - 1]
            logger.warning(
                "%s : tentative %s/%s échouée (%s), nouvel essai dans %ss...",
                label, attempt, MAX_ATTEMPTS, exc, delay,
            )
            await asyncio.sleep(delay)


def format_date(source_updated_at: str) -> str:
    """Convertit 'AAAA-MM-JJ HH:MM:SS' (format DB) en 'JJ.MM.AAAA'."""
    from datetime import datetime
    dt = datetime.strptime(source_updated_at.split(" ")[0], "%Y-%m-%d")
    return dt.strftime("%d.%m.%Y")


def build_caption(number: int, title: str, language: str, updated_at: str) -> str:
    """Format acté : Kacou {number} : {titre} WhatsApp {emoji langue} ({date de mise à jour})"""
    emoji = config.LANGUAGE_EMOJIS[language]
    date_str = format_date(updated_at)
    return f"Kacou {number} : {title} WhatsApp {emoji} ({date_str})"


async def _publish_new(bot: Bot, language: str, sermon) -> int:
    """Télécharge, compresse et publie une nouvelle prédication. Retourne le message_id."""
    compressed_path = await asyncio.to_thread(
        audio_processing.process_sermon_audio,
        audio_url=sermon.audio,
        audio_name=sermon.audio_name,
        title=sermon.title,
        number=sermon.number,
        language=language,
        publication_date=sermon.publication_date,
    )
    try:
        channel_id = config.CHANNEL_IDS[language]
        caption = build_caption(sermon.number, sermon.title, language, sermon.updated_at)

        async def _do_send():
            with open(compressed_path, "rb") as f:
                return await bot.send_audio(
                    chat_id=channel_id,
                    audio=f,
                    caption=caption,
                    title=sermon.title,
                    filename=sermon.audio_name,
                )

        message = await _with_retries(_do_send, label=f"[{language}] publication Kacou {sermon.number}")
        return message.message_id
    finally:
        audio_processing.cleanup(compressed_path)


async def _edit_existing(bot: Bot, language: str, sermon, message_id: int):
    """Télécharge, compresse et remplace le média d'un message existant."""
    compressed_path = await asyncio.to_thread(
        audio_processing.process_sermon_audio,
        audio_url=sermon.audio,
        audio_name=sermon.audio_name,
        title=sermon.title,
        number=sermon.number,
        language=language,
        publication_date=sermon.publication_date,
    )
    try:
        channel_id = config.CHANNEL_IDS[language]
        caption = build_caption(sermon.number, sermon.title, language, sermon.updated_at)

        async def _do_edit():
            with open(compressed_path, "rb") as f:
                media = InputMediaAudio(
                    media=f,
                    caption=caption,
                    title=sermon.title,
                    filename=sermon.audio_name,
                )
                await bot.edit_message_media(chat_id=channel_id, message_id=message_id, media=media)

        await _with_retries(_do_edit, label=f"[{language}] édition Kacou {sermon.number}")
    finally:
        audio_processing.cleanup(compressed_path)


async def sync_language(bot: Bot, language: str):
    """Compare les sermons d'une langue avec l'état local et publie/édite ce qui est nécessaire."""
    db_path = db_sync.lang_db_path(language)
    sermons = official_db.get_all_sermons(db_path)
    published_map = state_db.get_all_published(language)

    for sermon in sermons:
        existing = published_map.get(sermon.number)

        if existing is None or not existing.message_id:
            if existing is not None:
                logger.warning(
                    "[%s] Kacou %s : entrée existante sans message_id valide (%r), republication complète.",
                    language, sermon.number, existing.message_id,
                )
            else:
                logger.info("[%s] Kacou %s : nouvelle prédication, publication...", language, sermon.number)
            try:
                message_id = await _publish_new(bot, language, sermon)
                state_db.upsert_published(language, sermon.number, sermon.updated_at, message_id)
            except Exception:
                logger.exception("[%s] Échec de publication pour Kacou %s", language, sermon.number)

        elif existing.source_updated_at != sermon.updated_at:
            logger.info("[%s] Kacou %s : mise à jour détectée, édition...", language, sermon.number)
            try:
                await _edit_existing(bot, language, sermon, existing.message_id)
                state_db.upsert_published(language, sermon.number, sermon.updated_at, existing.message_id)
            except Exception:
                logger.exception("[%s] Échec d'édition pour Kacou %s", language, sermon.number)

        # sinon : rien à jour, on passe au suivant


async def run_full_sync(bot: Bot):
    """Point d'entrée appelé périodiquement (JobQueue) ou manuellement."""
    logger.info("=== Début du cycle de synchronisation ===")
    try:
        changed_langs = await asyncio.to_thread(db_sync.sync_official_databases)
    except Exception:
        logger.exception("Échec de la synchronisation des DB officielles, cycle annulé.")
        return

    if changed_langs:
        logger.info("Langues avec DB officielle changée : %s", changed_langs)
    else:
        logger.info("Aucune langue modifiée dans les DB officielles.")

    # sync_language tourne sur TOUTES les langues à chaque cycle, pas seulement changed_langs :
    # changed_langs ne dit que si la DB officielle a bougé, pas si tout ce qu'elle contient a été
    # effectivement publié. Sans ça, une prédication interrompue (coupure réseau, crash...) reste
    # bloquée indéfiniment tant que le serveur officiel ne change rien d'autre pour cette langue.
    for language in config.LANGUAGES:
        await sync_language(bot, language)

    logger.info("=== Fin du cycle de synchronisation ===")
