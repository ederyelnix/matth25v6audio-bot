"""
Téléchargement du fichier audio source + compression ffmpeg.
Règles actées avec l'utilisateur :
  - Format de sortie : MP3, mono, 32 kbps CBR
  - Le nom du fichier final = sermons.audio_name, tel quel (rien ajouté)
  - Le fichier original téléchargé a un nom temporaire quelconque (peu importe)
"""
import logging
import subprocess
import uuid
from pathlib import Path

import requests

import config

logger = logging.getLogger(__name__)


def download_source_audio(audio_url: str) -> Path:
    """Télécharge le fichier audio source vers un nom temporaire quelconque."""
    tmp_name = f"src_{uuid.uuid4().hex}"
    tmp_path = config.TMP_DIR / tmp_name

    resp = requests.get(audio_url, timeout=180, stream=True)
    resp.raise_for_status()
    with open(tmp_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 256):
            f.write(chunk)

    return tmp_path


def year_from_date(date_str: str) -> str:
    """
    Réplique exactement year_from_date du C++ : prend les 4 derniers caractères
    de la date (le format se termine par l'année, ex: 'Lundi 08 juillet 2002'),
    '2002' par défaut si absent/trop court.
    """
    if not date_str or len(date_str) < 4:
        return "2002"
    return date_str[-4:]


def compress_for_whatsapp(
    source_path: Path,
    audio_name: str,
    title: str = None,
    number: int = None,
    language: str = None,
    publication_date: str = None,
) -> Path:
    """
    Compresse le fichier source en MP3 32kbps mono.
    Le fichier de sortie est nommé exactement `audio_name` (celui de la DB).
    Ajoute les métadonnées ID3 (TITLE, ARTIST, ALBUM, GENRE, TRACKNUMBER, DATE, LANGUAGE),
    répliquant set_audio_tags du code C++ existant.
    La pochette embarquée dans le fichier source (le cas échéant) est copiée telle quelle,
    sans réencodage : seules les métadonnées listées ci-dessus sont modifiées, le reste
    (dont l'image) est préservé à l'identique.
    """
    output_path = config.TMP_DIR / audio_name

    cmd = [
        "ffmpeg", "-y",
        "-i", str(source_path),
        "-map", "0:a",    # piste audio
        "-map", "0:v?",   # pochette éventuelle (optionnelle, ne fait pas échouer si absente)
        "-c:v", "copy",   # image copiée telle quelle, jamais réencodée
        "-ac", config.AUDIO_CHANNELS,
        "-b:a", config.AUDIO_BITRATE,
        "-codec:a", "libmp3lame",
    ]
    if title:
        cmd += ["-metadata", f"title={title}"]
    if language:
        cmd += ["-metadata", f"artist={config.SERMON_ARTIST[language]}"]
        cmd += ["-metadata", f"album={config.SERMON_ALBUM[language]}"]
        cmd += ["-metadata", f"language={language}"]
    cmd += ["-metadata", "genre=Sermon"]
    if number is not None:
        cmd += ["-metadata", f"track={number}"]
    if publication_date:
        cmd += ["-metadata", f"date={year_from_date(publication_date)}"]

    cmd.append(str(output_path))

    logger.info("Compression ffmpeg : %s -> %s", source_path.name, output_path.name)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Échec ffmpeg pour {audio_name} :\n{result.stderr}")

    return output_path


def cleanup(*paths: Path):
    for path in paths:
        try:
            if path and path.exists():
                path.unlink()
        except OSError:
            logger.warning("Impossible de supprimer %s", path)


def process_sermon_audio(
    audio_url: str,
    audio_name: str,
    title: str = None,
    number: int = None,
    language: str = None,
    publication_date: str = None,
) -> Path:
    """Enchaîne téléchargement + compression, retourne le chemin du fichier compressé prêt à uploader."""
    source_path = download_source_audio(audio_url)
    try:
        compressed_path = compress_for_whatsapp(
            source_path, audio_name, title=title,
            number=number, language=language, publication_date=publication_date,
        )
    finally:
        cleanup(source_path)
    return compressed_path
