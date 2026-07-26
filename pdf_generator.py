"""
Génération d'un PDF pour une prédication, une prédication à la fois.

Même logique que le système de lettres de motivation (Bewerbungsschreiben) :
overlay de texte sur une image de base via ImageMagick, puis assemblage des
pages en PDF via img2pdf.

Toutes les coordonnées (149.2, 278.1, 1702.4, 115.7...) sont directement en
pixels sur le canevas 1414x2000 -- aucun ratio de conversion. Les tailles de
police (13.67 / 15.01 / 13) sont utilisées telles quelles comme -pointsize
ImageMagick.

Fonction synchrone/bloquante (subprocess ImageMagick) : à appeler via
asyncio.to_thread() depuis le bot pour ne jamais geler la boucle asyncio.

IMPORTANT : le positionnement vertical précis (baseline -> haut du bloc via
l'ascendant réel de la police, extrait des métriques ImageMagick) n'a pas pu
être testé ici avec les polices réelles (elles ne sont installées que sur
ta machine). La technique utilisée (-debug annotate pour lire l'ascendant
exact) est la méthode standard ImageMagick pour ce genre de positionnement,
mais un léger ajustement visuel (quelques px) peut être nécessaire une fois
testé chez toi -- les constantes sont toutes regroupées en haut de ce fichier.
"""
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import List, Optional

import img2pdf

import official_db

# ---------------------------------------------------------------------------
# Chemins des assets
# ---------------------------------------------------------------------------
_BASE_DIR = Path(__file__).parent
ASSETS_DIR = _BASE_DIR / "assets"
FONTS_DIR = _BASE_DIR / "fonts"

TEMPLATE_PATH = ASSETS_DIR / "kacou_template.png"
CANVAS_WIDTH = 1414
CANVAS_HEIGHT = 2000

FONT_HEADER = FONTS_DIR / "LeagueSpartan-Bold.ttf"
FONT_TITLE = FONTS_DIR / "Montserrat-SemiBold.ttf"
FONT_BODY = FONTS_DIR / "JosefinSans-Light.ttf"

COLOR_HEADER = "#d5bdaf"
COLOR_TITLE = "#1800ad"
COLOR_BODY = "#1f2122"

SIZE_HEADER = 13.67
SIZE_TITLE = 15.01
SIZE_BODY = 13.0

# Positions en px, directement sur le canevas 1414x2000 (baselines)
HEADER_BASELINE_Y = 149.2
CONTENT_START_Y = 278.1     # baseline de "Kacou N : titre" (page 1) / du 1er verset (pages suivantes)
CONTENT_MAX_Y = 1702.4      # dernière baseline utilisable avant de passer à la page suivante

VERSE_X_START = 115.7
VERSE_X_END = CANVAS_WIDTH - VERSE_X_START  # 1298.3
VERSE_BOX_WIDTH = VERSE_X_END - VERSE_X_START

# Traduction naturelle de l'entête, répétée sur toutes les pages (langue de contenu)
HEADER_TEXTS = {
    "fr": "LIVRE DU PROPHÈTE KACOU PHILIPPE",
    "en": "BOOK OF THE PROPHET KACOU PHILIPPE",
    "pt": "LIVRO DO PROFETA KACOU PHILIPPE",
    "es": "LIBRO DEL PROFETA KACOU PHILIPPE",
}


class PdfGenerationError(Exception):
    pass


# ---------------------------------------------------------------------------
# Métriques de police (ImageMagick -debug annotate donne l'ascendant/descendant
# EXACT de la police à une taille donnée -- pas d'approximation).
# ---------------------------------------------------------------------------
def _font_metrics(font_path: Path, pointsize: float) -> dict:
    result = subprocess.run(
        [
            "convert", "-debug", "annotate", "xc:",
            "-font", str(font_path), "-pointsize", str(pointsize),
            "-annotate", "+0+0", "Ag",
            "null:",
        ],
        capture_output=True, text=True,
    )
    output = result.stdout + result.stderr
    for line in output.splitlines():
        if "Metrics" in line and "ascent" in line:
            tokens = line.replace(":", " ").split()
            values = {}
            for i, tok in enumerate(tokens):
                if tok in ("ascent", "descent"):
                    values[tok] = float(tokens[i + 1])
            if "ascent" in values and "descent" in values:
                return values
    raise PdfGenerationError(f"Impossible de lire les métriques de {font_path} @ {pointsize}pt")


def _font_ascent(font_path: Path, pointsize: float) -> float:
    return _font_metrics(font_path, pointsize)["ascent"]


def _line_height(font_path: Path, pointsize: float) -> float:
    m = _font_metrics(font_path, pointsize)
    return m["ascent"] - m["descent"]


def _caption_height(text: str, font_path: Path, pointsize: float, width: float) -> float:
    """Hauteur totale (px) qu'occuperait ce texte en caption: à cette largeur
    (retour à la ligne et espacement des \\n\\n gérés nativement par ImageMagick)."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp:
        subprocess.run(
            [
                "convert", "-size", f"{int(width)}x",
                "-font", str(font_path), "-pointsize", str(pointsize),
                f"caption:{text}",
                tmp.name,
            ],
            check=True, capture_output=True,
        )
        out = subprocess.run(["identify", "-format", "%h", tmp.name], capture_output=True, text=True, check=True)
        return float(out.stdout.strip())


# ---------------------------------------------------------------------------
# Composition sur le canevas
# ---------------------------------------------------------------------------
def _annotate_centered(canvas_path: Path, text: str, font_path: Path, pointsize: float, color: str, baseline_y: float):
    ascent = _font_ascent(font_path, pointsize)
    top_y = baseline_y - ascent
    subprocess.run(
        [
            "convert", str(canvas_path),
            "-font", str(font_path), "-pointsize", str(pointsize), "-fill", color,
            "-gravity", "North",
            "-annotate", f"+0+{top_y:.2f}", text,
            str(canvas_path),
        ],
        check=True, capture_output=True,
    )


def _composite_caption_block(canvas_path: Path, text: str, font_path: Path, pointsize: float, color: str,
                              x: float, top_y: float, width: float):
    """Compose un bloc caption: (gère lui-même retour à la ligne + espacement des \\n\\n) à la position donnée."""
    subprocess.run(
        [
            "convert", str(canvas_path),
            "(", "-size", f"{int(width)}x",
                 "-font", str(font_path), "-pointsize", str(pointsize), "-fill", color,
                 f"caption:{text}",
            ")",
            "-geometry", f"+{int(round(x))}+{int(round(top_y))}",
            "-compose", "over", "-composite",
            str(canvas_path),
        ],
        check=True, capture_output=True,
    )


# ---------------------------------------------------------------------------
# Pagination : versets = unité atomique, jamais coupés au milieu. Une page ne
# commence jamais par une ligne vide (pas de \n\n en tête de page suivante).
# ---------------------------------------------------------------------------
def _verse_line(v: "official_db.Verse") -> str:
    return f"{v.number} {v.content}"


def _fit_page(verses: List["official_db.Verse"], budget_height: float, box_width: float):
    current = []
    for i, verse in enumerate(verses):
        candidate = current + [verse]
        text = "\n\n".join(_verse_line(v) for v in candidate)
        height = _caption_height(text, FONT_BODY, SIZE_BODY, box_width)
        if height <= budget_height or not current:
            current = candidate
        else:
            return current, verses[i:]
    return current, []


def _paginate(verses: List["official_db.Verse"], budget_page1: float, budget_continuation: float, box_width: float):
    pages = []
    remaining = list(verses)
    budget = budget_page1
    while remaining:
        page_verses, remaining = _fit_page(remaining, budget, box_width)
        pages.append(page_verses)
        budget = budget_continuation
    return pages


# ---------------------------------------------------------------------------
# Rendu d'une page
# ---------------------------------------------------------------------------
def _render_page(sermon, content_language: str, verses_on_page, is_first_page: bool,
                  page_index: int, work_dir: Path, verses_top_y: float,
                  date_str: Optional[str] = None, date_baseline: Optional[float] = None) -> Path:
    page_path = work_dir / f"page_{page_index}.png"
    subprocess.run(["cp", str(TEMPLATE_PATH), str(page_path)], check=True)

    # Entête, répétée sur TOUTES les pages
    _annotate_centered(page_path, HEADER_TEXTS[content_language], FONT_HEADER, SIZE_HEADER, COLOR_HEADER, HEADER_BASELINE_Y)

    if is_first_page:
        title_text = f"Kacou {sermon.number} : {sermon.title}"
        _annotate_centered(page_path, title_text, FONT_TITLE, SIZE_TITLE, COLOR_TITLE, CONTENT_START_Y)
        _annotate_centered(page_path, date_str, FONT_BODY, SIZE_BODY, COLOR_BODY, date_baseline)

    verse_text = "\n\n".join(_verse_line(v) for v in verses_on_page)
    _composite_caption_block(page_path, verse_text, FONT_BODY, SIZE_BODY, COLOR_BODY,
                              VERSE_X_START, verses_top_y, VERSE_BOX_WIDTH)

    return page_path


def _format_date(publication_date: str) -> str:
    """Même convention que sync_service.format_date : 'AAAA-MM-JJ ...' -> 'JJ.MM.AAAA'."""
    from datetime import datetime
    dt = datetime.strptime(publication_date.split(" ")[0].split("T")[0], "%Y-%m-%d")
    return dt.strftime("%d.%m.%Y")


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------
def generate_sermon_pdf(sermon, content_language: str, verses: List["official_db.Verse"], output_dir: Path) -> Path:
    """
    Génère le PDF complet d'une prédication (toutes ses pages) et retourne le
    chemin du fichier final, unique (contient un uuid), pour éviter toute
    collision si plusieurs utilisateurs génèrent un PDF en même temps.
    Fonction bloquante : à appeler via asyncio.to_thread().
    """
    if not verses:
        raise PdfGenerationError(f"Aucun verset trouvé pour Kacou {sermon.number} ({content_language}).")

    output_dir.mkdir(parents=True, exist_ok=True)
    request_id = uuid.uuid4().hex
    work_dir = output_dir / f"pdf_work_{request_id}"
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        title_line_height = _line_height(FONT_TITLE, SIZE_TITLE)
        body_line_height = _line_height(FONT_BODY, SIZE_BODY)
        body_ascent = _font_ascent(FONT_BODY, SIZE_BODY)

        date_baseline = CONTENT_START_Y + title_line_height  # ligne naturelle suivante
        # + une ligne vide (\n\n) avant le premier verset
        verses_first_baseline_page1 = date_baseline + body_line_height + body_line_height
        verses_top_page1 = verses_first_baseline_page1 - body_ascent
        budget_page1 = CONTENT_MAX_Y - verses_top_page1

        verses_top_continuation = CONTENT_START_Y - body_ascent
        budget_continuation = CONTENT_MAX_Y - verses_top_continuation

        pages_of_verses = _paginate(verses, budget_page1, budget_continuation, VERSE_BOX_WIDTH)

        date_str = _format_date(sermon.publication_date)

        page_paths = []
        for i, page_verses in enumerate(pages_of_verses):
            is_first = (i == 0)
            top_y = verses_top_page1 if is_first else verses_top_continuation
            page_path = _render_page(
                sermon, content_language, page_verses, is_first, i, work_dir, top_y,
                date_str=date_str if is_first else None,
                date_baseline=date_baseline if is_first else None,
            )
            page_paths.append(page_path)

        pdf_path = output_dir / f"Kacou_{sermon.number}_{content_language.upper()}_{request_id}.pdf"
        with open(pdf_path, "wb") as f:
            f.write(img2pdf.convert([str(p) for p in page_paths]))

        return pdf_path
    finally:
        for p in work_dir.glob("*"):
            p.unlink(missing_ok=True)
        work_dir.rmdir()
