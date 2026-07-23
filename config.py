"""
Configuration centrale du bot.
Tout ce qui dépend de l'environnement (dev sur ton PC, puis serveur plus tard)
passe par le fichier .env, rien n'est codé en dur ici.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Dossiers
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent

# Dossier où sont stockées les DB officielles (common.db + matth25v6_XX.db)
DB_DIR = Path(os.getenv("DB_DIR") or (BASE_DIR / "data" / "official_db"))

# Dossier de travail temporaire (téléchargement + compression, nettoyé après usage)
TMP_DIR = Path(os.getenv("TMP_DIR") or (BASE_DIR / "data" / "tmp"))

# DB locale du bot (suivi des publications + utilisateurs)
STATE_DB_PATH = Path(os.getenv("STATE_DB_PATH") or (BASE_DIR / "data" / "bot_state.db"))

DB_DIR.mkdir(parents=True, exist_ok=True)
TMP_DIR.mkdir(parents=True, exist_ok=True)
STATE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "")  # À renseigner dans .env

# Un canal par langue. À renseigner dans .env (ID numérique du canal, ex: -1001234567890)
CHANNEL_IDS = {
    "fr": os.getenv("CHANNEL_ID_FR", ""),
    "en": os.getenv("CHANNEL_ID_EN", ""),
    "pt": os.getenv("CHANNEL_ID_PT", ""),
    "es": os.getenv("CHANNEL_ID_ES", ""),
}

# ---------------------------------------------------------------------------
# API philippekacou.org
# ---------------------------------------------------------------------------
API_BASE_URL = os.getenv("API_BASE_URL") or "https://api.philippekacou.org/api"

# Valeur du paramètre "initial" attendu par l'API pour chaque langue/DB.
# Vu dans le code C++ : "common" pour common.db, et un code type "fr-fr" pour
# les langues (dont on extrait la lettre après le tiret). Les valeurs pour
# en/pt/es ne sont pas encore confirmées : à vérifier/corriger dans le .env.
API_INITIALS = {
    "common": os.getenv("API_INITIAL_COMMON") or "common",
    "fr": os.getenv("API_INITIAL_FR") or "fr-fr",
    "en": os.getenv("API_INITIAL_EN") or "en-en",
    "pt": os.getenv("API_INITIAL_PT") or "pt-pt",
    "es": os.getenv("API_INITIAL_ES") or "es-es",
}

LANGUAGES = ["fr", "en", "pt", "es"]

LANGUAGE_EMOJIS = {
    "fr": os.getenv("EMOJI_FR", "🇫🇷"),
    "en": os.getenv("EMOJI_EN", "🇬🇧"),
    "pt": os.getenv("EMOJI_PT", "🇵🇹"),
    "es": os.getenv("EMOJI_ES", "🇪🇸"),
}

LANGUAGE_NAMES = {
    "fr": "Français",
    "en": "English",
    "pt": "Português",
    "es": "Español",
}

# ---------------------------------------------------------------------------
# Compression audio
# ---------------------------------------------------------------------------
AUDIO_BITRATE = os.getenv("AUDIO_BITRATE", "32k")  # acté avec l'utilisateur
AUDIO_CHANNELS = "1"  # mono, acté

# Métadonnées ID3 par langue, répliquant sermon_artist_for_lang / sermon_album_for_lang
# du code C++ existant (qui ne gérait que FR/EN ; PT/ES traduits pour ce bot).
SERMON_ARTIST = {
    "fr": "Matthieu 25v6",
    "en": "Matthew 25v6",
    "pt": "Mateus 25v6",
    "es": "Mateo 25v6",
}
SERMON_ALBUM = {
    "fr": "Le Message de Matthieu 25v6 en audio",
    "en": "The Message of Matthew 25v6 in Audio",
    "pt": "A Mensagem de Mateus 25v6 em áudio",
    "es": "El Mensaje de Mateo 25v6 en audio",
}

# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------
SYNC_INTERVAL_SECONDS = int(os.getenv("SYNC_INTERVAL_SECONDS") or "600")  # 10 min par défaut (vérification légère, plus besoin de 6h)

# Grille de sélection des prédications
SERMONS_PER_ROW = 5
SERMONS_ROWS_PER_PAGE = 6
SERMONS_PER_PAGE = SERMONS_PER_ROW * SERMONS_ROWS_PER_PAGE
