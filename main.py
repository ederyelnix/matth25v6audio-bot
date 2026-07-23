import logging

from telegram.ext import Application
from telegram.request import HTTPXRequest

import config
import state_db
from bot import register_handlers
from sync_service import run_full_sync

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def scheduled_sync(context):
    await run_full_sync(context.bot)


def main():
    if not config.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN manquant, à renseigner dans le fichier .env")

    state_db.init_db()

    request = HTTPXRequest(
        connection_pool_size=8,  # évite la contention avec getUpdates (long-polling) qui partage sinon la même connexion
        connect_timeout=30,
        read_timeout=300,
        write_timeout=300,        # ignoré pour les requêtes avec fichier (send_audio, edit_message_media) : voir media_write_timeout
        media_write_timeout=300,  # c'est CE paramètre qui régit réellement l'upload audio, pas write_timeout (défaut PTB : 20s, bien trop court)
        pool_timeout=30,
    )
    get_updates_request = HTTPXRequest(
        connection_pool_size=1,
        connect_timeout=30,
        read_timeout=30,
        pool_timeout=30,
    )
    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .request(request)
        .get_updates_request(get_updates_request)
        .build()
    )
    register_handlers(app)

    app.job_queue.run_repeating(
        scheduled_sync,
        interval=config.SYNC_INTERVAL_SECONDS,
        first=10,  # premier cycle 10s après le démarrage
    )

    logger.info("Bot démarré, cycle de sync toutes les %s secondes.", config.SYNC_INTERVAL_SECONDS)
    app.run_polling()


if __name__ == "__main__":
    main()