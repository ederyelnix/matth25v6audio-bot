"""
Bot interactif côté utilisateur.
Flux acté avec l'utilisateur :
  /start -> choix langue UI -> menu principal -> choix langue de contenu
  -> grille "Kacou X" (sélection multiple, indicateur visuel) -> validation -> forward
"""
import logging
from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
import db_sync
import official_db
import state_db
from i18n import t

logger = logging.getLogger(__name__)


def _bold(text: str) -> str:
    return f"<b>{escape(text)}</b>"

# --- Callback data prefixes ---
CB_UI_LANG = "uilang"
CB_MENU_SERMONS = "menu_sermons"
CB_CONTENT_LANG = "clang"
CB_TOGGLE = "toggle"
CB_PAGE = "page"
CB_VALIDATE = "validate"
CB_BACK_MENU = "back_menu"
CB_NEW_REQUEST = "new_request"
CB_CHANGE_LANG = "change_lang"


def _selected_key(context: ContextTypes.DEFAULT_TYPE) -> set:
    return context.user_data.setdefault("selected_numbers", set())


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------
def _ui_language_markup() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"{CB_UI_LANG}:{code}")]
        for code, name in config.LANGUAGE_NAMES.items()
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        _bold(t("choose_ui_language", "en")),  # langue pas encore connue, on part de l'anglais par défaut
        reply_markup=_ui_language_markup(),
        parse_mode=ParseMode.HTML,
    )


async def on_language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/language : permet de changer la langue d'interface à tout moment."""
    await update.message.reply_text(
        _bold(t("choose_ui_language", "en")),
        reply_markup=_ui_language_markup(),
        parse_mode=ParseMode.HTML,
    )


async def on_ui_language_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ui_language = query.data.split(":", 1)[1]
    state_db.set_user_language(query.from_user.id, ui_language)
    await show_main_menu(query, ui_language)


async def show_main_menu(query, ui_language: str):
    keyboard = [
        [InlineKeyboardButton(t("btn_sermons", ui_language), callback_data=CB_MENU_SERMONS)],
        [InlineKeyboardButton(t("btn_change_language", ui_language), callback_data=CB_CHANGE_LANG)],
    ]
    await query.edit_message_text(
        t("main_menu_title", ui_language),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def on_change_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Accessible à tout moment depuis le menu principal : change la langue d'interface."""
    query = update.callback_query
    await query.answer()
    ui_language = state_db.get_user_language(query.from_user.id) or "en"
    await query.edit_message_text(
        _bold(t("choose_ui_language", ui_language)),
        reply_markup=_ui_language_markup(),
        parse_mode=ParseMode.HTML,
    )


async def on_back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ui_language = state_db.get_user_language(query.from_user.id) or "en"
    context.user_data["selected_numbers"] = set()
    await show_main_menu(query, ui_language)


# ---------------------------------------------------------------------------
# Choix de la langue de contenu
# ---------------------------------------------------------------------------
def _content_language_markup(ui_language: str) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(f"{config.LANGUAGE_EMOJIS[code]} {name}", callback_data=f"{CB_CONTENT_LANG}:{code}")]
        for code, name in config.LANGUAGE_NAMES.items()
    ]
    keyboard.append([InlineKeyboardButton(t("btn_change_language", ui_language), callback_data=CB_CHANGE_LANG)])
    keyboard.append([InlineKeyboardButton(t("btn_back", ui_language), callback_data=CB_BACK_MENU)])
    return InlineKeyboardMarkup(keyboard)


async def on_menu_sermons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ui_language = state_db.get_user_language(query.from_user.id) or "en"
    await query.edit_message_text(
        _bold(t("choose_content_language", ui_language)),
        reply_markup=_content_language_markup(ui_language),
        parse_mode=ParseMode.HTML,
    )


# ---------------------------------------------------------------------------
# Grille de sélection des prédications
# ---------------------------------------------------------------------------
def _build_sermon_grid(sermons, selected: set, page: int, ui_language: str, content_lang: str) -> InlineKeyboardMarkup:
    start = page * config.SERMONS_PER_PAGE
    end = start + config.SERMONS_PER_PAGE
    page_sermons = sermons[start:end]

    rows = []
    row = []
    for sermon in page_sermons:
        label = f"✅ Kacou {sermon.number}" if sermon.number in selected else f"Kacou {sermon.number}"
        row.append(InlineKeyboardButton(label, callback_data=f"{CB_TOGGLE}:{content_lang}:{sermon.number}:{page}"))
        if len(row) == config.SERMONS_PER_ROW:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(t("btn_prev", ui_language), callback_data=f"{CB_PAGE}:{content_lang}:{page - 1}"))
    if end < len(sermons):
        nav_row.append(InlineKeyboardButton(t("btn_next", ui_language), callback_data=f"{CB_PAGE}:{content_lang}:{page + 1}"))
    if nav_row:
        rows.append(nav_row)

    rows.append([InlineKeyboardButton(t("btn_validate", ui_language), callback_data=f"{CB_VALIDATE}:{content_lang}")])
    rows.append([InlineKeyboardButton(t("btn_back", ui_language), callback_data=CB_MENU_SERMONS)])

    return InlineKeyboardMarkup(rows)


async def render_sermon_page(update: Update, context: ContextTypes.DEFAULT_TYPE, content_lang: str, page: int):
    query = update.callback_query
    ui_language = state_db.get_user_language(query.from_user.id) or "en"
    db_path = db_sync.lang_db_path(content_lang)
    sermons = official_db.get_all_sermons(db_path)
    selected = _selected_key(context)

    markup = _build_sermon_grid(sermons, selected, page, ui_language, content_lang)
    await query.edit_message_text(_bold(t("choose_sermons", ui_language)), reply_markup=markup, parse_mode=ParseMode.HTML)


async def on_content_language_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    content_lang = query.data.split(":", 1)[1]
    context.user_data["selected_numbers"] = set()
    context.user_data["content_lang"] = content_lang
    await render_sermon_page(update, context, content_lang, page=0)


async def on_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, content_lang, page = query.data.split(":")
    await render_sermon_page(update, context, content_lang, int(page))


async def on_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, content_lang, number, page = query.data.split(":")
    number = int(number)
    selected = _selected_key(context)
    if number in selected:
        selected.discard(number)
    else:
        selected.add(number)
    await render_sermon_page(update, context, content_lang, int(page))


# ---------------------------------------------------------------------------
# Validation -> forward
# ---------------------------------------------------------------------------
async def on_validate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, content_lang = query.data.split(":")
    ui_language = state_db.get_user_language(query.from_user.id) or "en"
    selected = sorted(_selected_key(context))

    if not selected:
        await query.answer(t("no_selection", ui_language), show_alert=True)
        return

    await query.edit_message_text(t("sending_sermons", ui_language, count=len(selected)))

    channel_id = config.CHANNEL_IDS[content_lang]
    chat_id = query.message.chat_id

    for number in selected:
        published = state_db.get_published(content_lang, number)
        if not published:
            await context.bot.send_message(
                chat_id=chat_id,
                text=t("sermon_not_available", ui_language, number=number),
            )
            continue
        await context.bot.forward_message(
            chat_id=chat_id,
            from_chat_id=channel_id,
            message_id=published.message_id,
        )

    context.user_data["selected_numbers"] = set()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(t("btn_new_request", ui_language), callback_data=CB_NEW_REQUEST)]])
    await context.bot.send_message(chat_id=chat_id, text=t("done", ui_language), reply_markup=keyboard)


async def on_new_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bouton affiché après un envoi : relance directement sur la sélection de langue
    de consultation, sans repasser par /start ni par le choix de langue d'interface."""
    query = update.callback_query
    await query.answer()
    ui_language = state_db.get_user_language(query.from_user.id) or "en"
    context.user_data["selected_numbers"] = set()
    await query.edit_message_text(
        _bold(t("choose_content_language", ui_language)),
        reply_markup=_content_language_markup(ui_language),
        parse_mode=ParseMode.HTML,
    )


async def on_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """N'importe quel message texte (pas seulement /start) relance directement
    la sélection de langue de consultation, sans forcer l'utilisateur à taper /start."""
    ui_language = state_db.get_user_language(update.effective_user.id) or "en"
    context.user_data["selected_numbers"] = set()
    await update.message.reply_text(
        _bold(t("choose_content_language", ui_language)),
        reply_markup=_content_language_markup(ui_language),
        parse_mode=ParseMode.HTML,
    )


# ---------------------------------------------------------------------------
# Enregistrement des handlers
# ---------------------------------------------------------------------------
def register_handlers(app: Application):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", on_language_command))
    app.add_handler(CallbackQueryHandler(on_ui_language_chosen, pattern=f"^{CB_UI_LANG}:"))
    app.add_handler(CallbackQueryHandler(on_menu_sermons, pattern=f"^{CB_MENU_SERMONS}$"))
    app.add_handler(CallbackQueryHandler(on_back_to_menu, pattern=f"^{CB_BACK_MENU}$"))
    app.add_handler(CallbackQueryHandler(on_content_language_chosen, pattern=f"^{CB_CONTENT_LANG}:"))
    app.add_handler(CallbackQueryHandler(on_page, pattern=f"^{CB_PAGE}:"))
    app.add_handler(CallbackQueryHandler(on_toggle, pattern=f"^{CB_TOGGLE}:"))
    app.add_handler(CallbackQueryHandler(on_validate, pattern=f"^{CB_VALIDATE}:"))
    app.add_handler(CallbackQueryHandler(on_new_request, pattern=f"^{CB_NEW_REQUEST}$"))
    app.add_handler(CallbackQueryHandler(on_change_language, pattern=f"^{CB_CHANGE_LANG}$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text_message))