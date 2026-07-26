"""
Génération d'un PDF pour une prédication, une prédication à la fois.

Utilise Wand (binding Python de MagickWand/ImageMagick) plutôt que des appels
subprocess à `convert` : plus rapide (pas de nouveau processus à chaque appel),
et accès direct aux métriques réelles de police pour le positionnement par
baseline (aucune valeur approximée à la main).

Toutes les coordonnées (149.2, 278.1, 1702.4, 115.7...) sont directement en
pixels sur le canevas 1414x2000 -- aucun ratio de conversion. Les tailles de
police (13.67 / 15.01 / 13) sont utilisées telles quelles comme font_size Wand.

Fonction synchrone/bloquante (Wand/MagickWand) : à appeler via
asyncio.to_thread() depuis le bot pour ne jamais geler la boucle asyncio.

Vérifié empiriquement pendant le développement (voir tests) :
  - Drawing.text(x, y, ...) positionne bien (x, y) sur la BASELINE du texte,
    pas le haut de la boîte englobante -- confirmé par mesure de pixels.
  - Les métriques get_font_metrics().ascender / .descender donnent les
    valeurs réelles de la police (descender négatif, comme ImageMagick CLI).
  - Le format pseudo `caption:` (retour à la ligne natif ImageMagick) est
    utilisé pour le bloc de versets, avec hauteur automatique -- Wand impose
    normalement height>0 dans sa méthode .pseudo(), donc on appelle
    MagickSetSize/MagickReadImage directement (toujours via Wand, juste ses
    fonctions bas niveau) pour obtenir la hauteur=0 (auto) comme en CLI.
"""
from pathlib import Path
from typing import List, Optional
import uuid

import img2pdf
from wand.color import Color
from wand.compat import encode_filename
from wand.drawing import Drawing
from wand.font import Font
from wand.image import Image, library

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

FONT_HEADER = FONTS_DIR / "LeagueSpartan-Bold.otf"
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


def _template_dpi() -> float:
    """
    Densité réelle du template (ex: 67.32 px/cm = 171 DPI), calibrée sur le
    document Photoshop d'origine -- c'est CETTE densité qui donne 1pt = la
    bonne taille en px pour les valeurs (13.67, 15.01, 13...) telles que
    dessinées dans Photoshop, pas 72 DPI.
    """
    with Image(filename=str(TEMPLATE_PATH)) as probe:
        x_dpi, y_dpi = probe.resolution
        units = probe.units
    if units == "pixelspercentimeter":
        return x_dpi * 2.54
    return x_dpi  # déjà en pixelsperinch


TEMPLATE_DPI = _template_dpi()


# ---------------------------------------------------------------------------
# Métriques de police (valeurs réelles via Wand, aucune approximation)
# ---------------------------------------------------------------------------
def _font_metrics(font_path: Path, pointsize: float):
    """Retourne le FontMetrics réel (ascender/descender/...) pour une police et une taille données."""
    with Image(width=10, height=10) as probe:
        with Drawing() as draw:
            draw.font = str(font_path)
            draw.font_size = pointsize
            # Levier réel pour Drawing.text()/get_font_metrics() : font_resolution.
            # Image.resolution n'a AUCUN effet sur ce chemin de rendu (vérifié empiriquement) --
            # c'est différent du chemin `caption:` plus bas, qui lui utilise Image.resolution.
            draw.font_resolution = (TEMPLATE_DPI, TEMPLATE_DPI)
            return draw.get_font_metrics(probe, "Ag", multiline=False)


def _font_ascent(font_path: Path, pointsize: float) -> float:
    return _font_metrics(font_path, pointsize).ascender


def _line_height(font_path: Path, pointsize: float) -> float:
    m = _font_metrics(font_path, pointsize)
    return m.ascender - m.descender  # descender est négatif


def _caption_height(text: str, font_path: Path, pointsize: float, width: float) -> float:
    """
    Hauteur totale (px) qu'occuperait ce texte en bloc `caption:` à cette largeur
    (retour à la ligne et espacement des \\n\\n gérés nativement par ImageMagick).
    Hauteur automatique (0) : Wand.Image.pseudo() interdit height=0, donc appel
    direct des fonctions MagickWand sous-jacentes (toujours via Wand).
    """
    img = Image()
    try:
        img.resolution = (TEMPLATE_DPI, TEMPLATE_DPI)
        img.font = Font(path=str(font_path), size=pointsize)
        library.MagickSetSize(img.wand, int(width), 0)
        r = library.MagickReadImage(img.wand, encode_filename(f"caption:{text}"))
        if not r:
            img.raise_exception()
        return float(img.height)
    finally:
        img.close()


# ---------------------------------------------------------------------------
# Composition sur le canevas
# ---------------------------------------------------------------------------
def _annotate_centered(canvas: Image, text: str, font_path: Path, pointsize: float, color: str, baseline_y: float):
    with Drawing() as draw:
        draw.font = str(font_path)
        draw.font_size = pointsize
        draw.font_resolution = (TEMPLATE_DPI, TEMPLATE_DPI)
        draw.fill_color = Color(color)
        draw.text_alignment = "center"
        draw.text(int(round(canvas.width / 2)), int(round(baseline_y)), text)
        draw.draw(canvas)


def _composite_caption_block(canvas: Image, text: str, font_path: Path, pointsize: float, color: str,
                              x: float, top_y: float, width: float):
    """Compose un bloc caption: (retour à la ligne + espacement \\n\\n natifs) à la position donnée."""
    block = Image()
    try:
        block.resolution = (TEMPLATE_DPI, TEMPLATE_DPI)
        block.font = Font(path=str(font_path), size=pointsize, color=Color(color))
        library.MagickSetSize(block.wand, int(width), 0)
        r = library.MagickReadImage(block.wand, encode_filename(f"caption:{text}"))
        if not r:
            block.raise_exception()
        canvas.composite(block, left=int(round(x)), top=int(round(top_y)))
    finally:
        block.close()


# ---------------------------------------------------------------------------
# Pagination : chaque verset est mesuré INDIVIDUELLEMENT (jamais plusieurs
# versets concaténés dans un seul appel ImageMagick -- un texte cumulé trop
# long déclenche une limite interne de sécurité d'ImageMagick, indépendante
# de notre largeur de colonne). Un verset n'est jamais coupré au milieu.
# Une page ne commence jamais par une ligne vide.
# ---------------------------------------------------------------------------
def _verse_line(v: "official_db.Verse") -> str:
    return f"{v.number} {v.content}"


def _verse_height(verse: "official_db.Verse", box_width: float) -> float:
    return _caption_height(_verse_line(verse), FONT_BODY, SIZE_BODY, box_width)


def _layout_verses(verses: List["official_db.Verse"], verses_top_page1: float, verses_top_continuation: float,
                    box_width: float, body_line_height: float, max_y: float):
    """
    Retourne une liste de pages ; chaque page est une liste de (verset, top_y)
    prêts à être dessinés individuellement (top_y = haut du bloc caption pour
    ce verset, pas sa baseline -- déjà cohérent avec ce que _render_page attend).
    """
    pages = []
    current: list = []
    y_top = verses_top_page1

    for verse in verses:
        gap = body_line_height if current else 0.0
        h = _verse_height(verse, box_width)
        candidate_top = y_top + gap
        candidate_bottom = candidate_top + h

        if current and candidate_bottom > max_y:
            pages.append(current)
            current = []
            y_top = verses_top_continuation
            candidate_top = y_top
            candidate_bottom = candidate_top + h

        current.append((verse, candidate_top))
        y_top = candidate_bottom

    if current:
        pages.append(current)

    return pages


# ---------------------------------------------------------------------------
# Rendu d'une page
# ---------------------------------------------------------------------------
def _render_page(sermon, content_language: str, verses_with_positions, is_first_page: bool,
                  page_index: int, work_dir: Path,
                  date_str: Optional[str] = None, date_baseline: Optional[float] = None) -> Path:
    page_path = work_dir / f"page_{page_index}.png"

    with Image(filename=str(TEMPLATE_PATH)) as canvas:
        # Densité alignée avec les blocs caption: composités plus bas (versets),
        # qui utilisent aussi TEMPLATE_DPI -- évite tout écart d'échelle au composite().
        # (Sans effet sur Drawing.text() ci-dessous, qui utilise font_resolution séparément.)
        canvas.resolution = (TEMPLATE_DPI, TEMPLATE_DPI)
        canvas.units = "pixelsperinch"
        # Entête, répétée sur TOUTES les pages
        _annotate_centered(canvas, HEADER_TEXTS[content_language], FONT_HEADER, SIZE_HEADER, COLOR_HEADER, HEADER_BASELINE_Y)

        if is_first_page:
            title_text = f"Kacou {sermon.number} : {sermon.title}"
            _annotate_centered(canvas, title_text, FONT_TITLE, SIZE_TITLE, COLOR_TITLE, CONTENT_START_Y)
            _annotate_centered(canvas, date_str, FONT_BODY, SIZE_BODY, COLOR_BODY, date_baseline)

        for verse, top_y in verses_with_positions:
            _composite_caption_block(canvas, _verse_line(verse), FONT_BODY, SIZE_BODY, COLOR_BODY,
                                      VERSE_X_START, top_y, VERSE_BOX_WIDTH)

        canvas.save(filename=str(page_path))

    return page_path


def _format_date(publication_date: str) -> str:
    """publication_date est déjà une chaîne lisible fournie par la DB officielle
    (ex: 'Dim. 15 Mars 2026'), pas un format ISO -- on l'utilise telle quelle,
    sans tenter de la re-parser/reformater (ça faisait planter la génération)."""
    return publication_date


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

        verses_top_continuation = CONTENT_START_Y - body_ascent

        pages = _layout_verses(
            verses, verses_top_page1, verses_top_continuation,
            VERSE_BOX_WIDTH, body_line_height, CONTENT_MAX_Y,
        )

        date_str = _format_date(sermon.publication_date)

        page_paths = []
        for i, page_verses_positions in enumerate(pages):
            is_first = (i == 0)
            page_path = _render_page(
                sermon, content_language, page_verses_positions, is_first, i, work_dir,
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
