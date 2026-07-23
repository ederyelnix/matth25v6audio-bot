"""
Traductions des textes de l'interface du bot.
Chaque texte visible par l'utilisateur doit passer par ici, jamais en dur
dans bot.py, pour que tout s'adapte à la langue UI choisie au /start.
"""

TEXTS = {
    "choose_ui_language": {
        "fr": "Bonjour ! Choisissez la langue de l'interface :",
        "en": "Welcome! Choose the interface language:",
        "pt": "Bem-vindo! Escolha o idioma da interface:",
        "es": "¡Bienvenido! Elige el idioma de la interfaz:",
    },
    "main_menu_title": {
        "fr": "Menu principal",
        "en": "Main menu",
        "pt": "Menu principal",
        "es": "Menú principal",
    },
    "btn_sermons": {
        "fr": "📖 Voir les prédications",
        "en": "📖 View the sermons",
        "pt": "📖 Ver as pregações",
        "es": "📖 Ver las predicaciones",
    },
    "choose_content_language": {
        "fr": "Dans quelle langue souhaitez-vous consulter les prédications ?",
        "en": "In which language would you like to view the sermons?",
        "pt": "Em que idioma deseja consultar as pregações?",
        "es": "¿En qué idioma desea consultar las predicaciones?",
    },
    "choose_sermons": {
        "fr": "Sélectionnez les prédications souhaitées, puis validez :",
        "en": "Select the sermons you want, then confirm:",
        "pt": "Selecione as pregações desejadas e confirme:",
        "es": "Seleccione las predicaciones deseadas y confirme:",
    },
    "btn_validate": {
        "fr": "✅ Valider ma sélection",
        "en": "✅ Confirm my selection",
        "pt": "✅ Confirmar minha seleção",
        "es": "✅ Confirmar mi selección",
    },
    "btn_prev": {
        "fr": "◀ Précédent",
        "en": "◀ Previous",
        "pt": "◀ Anterior",
        "es": "◀ Anterior",
    },
    "btn_next": {
        "fr": "Suivant ▶",
        "en": "Next ▶",
        "pt": "Próximo ▶",
        "es": "Siguiente ▶",
    },
    "btn_back": {
        "fr": "🔙 Retour",
        "en": "🔙 Back",
        "pt": "🔙 Voltar",
        "es": "🔙 Volver",
    },
    "no_selection": {
        "fr": "Vous n'avez sélectionné aucune prédication.",
        "en": "You haven't selected any sermon.",
        "pt": "Você não selecionou nenhuma pregação.",
        "es": "No ha seleccionado ninguna predicación.",
    },
    "sending_sermons": {
        "fr": "Envoi de {count} prédication(s) en cours...",
        "en": "Sending {count} sermon(s)...",
        "pt": "Enviando {count} pregação(ões)...",
        "es": "Enviando {count} predicación(es)...",
    },
    "sermon_not_available": {
        "fr": "Kacou {number} n'est pas encore disponible, désolé.",
        "en": "Kacou {number} is not available yet, sorry.",
        "pt": "Kacou {number} ainda não está disponível, desculpe.",
        "es": "Kacou {number} aún no está disponible, lo sentimos.",
    },
    "done": {
        "fr": "Terminé !",
        "en": "Done!",
        "pt": "Concluído!",
        "es": "¡Listo!",
    },
    "btn_new_request": {
        "fr": "🔄 Nouvelle demande",
        "en": "🔄 New request",
        "pt": "🔄 Novo pedido",
        "es": "🔄 Nueva solicitud",
    },
    "btn_change_language": {
        "fr": "🌐 Changer de langue",
        "en": "🌐 Change language",
        "pt": "🌐 Mudar idioma",
        "es": "🌐 Cambiar idioma",
    },
}


def t(key: str, ui_language: str, **kwargs) -> str:
    entry = TEXTS.get(key, {})
    text = entry.get(ui_language) or entry.get("en") or key
    if kwargs:
        text = text.format(**kwargs)
    return text
