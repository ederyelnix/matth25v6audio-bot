"""
Script à lancer UNE SEULE FOIS pour amorcer published_sermons avec l'historique
déjà présent dans le canal FR (celui qui existe déjà, contrairement à EN/PT/ES).

Usage :
    python import_channel_history.py chemin/vers/result.json

Règles actées avec l'utilisateur :
  - Le pattern de légende n'est pas uniforme dans le temps -> regex large "Kacou[_\\s]?(\\d+)"
  - En cas de plusieurs messages pour le même numéro -> on garde le plus récent
    (edited_unixtime si présent, sinon date_unixtime)
  - source_updated_at reste NULL : le premier cycle de sync retraitera tout
    naturellement comme "à mettre à jour" (voir state_db.import_raw_entry)
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone

import state_db

CAPTION_PATTERN = re.compile(r"Kacou[_\s]?(\d+)")


def extract_text(message: dict) -> str:
    text = message.get("text")
    if isinstance(text, list):
        return "".join(part if isinstance(part, str) else part.get("text", "") for part in text)
    return text or ""


def message_sort_key(message: dict) -> int:
    """Le plus récent = edited_unixtime s'il existe, sinon date_unixtime."""
    if message.get("edited_unixtime"):
        return int(message["edited_unixtime"])
    return int(message.get("date_unixtime", 0))


def main():
    parser = argparse.ArgumentParser(description="Import de l'historique du canal FR dans bot_state.db")
    parser.add_argument("json_path", help="Chemin vers result.json exporté depuis Telegram Desktop")
    parser.add_argument("--language", default="fr", help="Code langue à associer (défaut: fr)")
    args = parser.parse_args()

    with open(args.json_path, encoding="utf-8") as f:
        data = json.load(f)

    messages = [
        m for m in data["messages"]
        if m.get("type") == "message" and m.get("media_type") == "audio_file"
    ]

    by_number = {}
    unmatched = []
    for m in messages:
        text = extract_text(m)
        match = CAPTION_PATTERN.search(text)
        if not match:
            unmatched.append((m["id"], text))
            continue
        number = int(match.group(1))
        by_number.setdefault(number, []).append(m)

    if unmatched:
        print(f"ATTENTION : {len(unmatched)} message(s) sans numéro reconnu, ignorés :")
        for mid, text in unmatched:
            print(f"  id={mid} texte={text!r}")

    state_db.init_db()

    imported = 0
    for number, msgs in sorted(by_number.items()):
        chosen = max(msgs, key=message_sort_key)
        if len(msgs) > 1:
            print(f"Kacou {number} : {len(msgs)} messages trouvés, on garde id={chosen['id']}")

        date_unixtime = int(chosen.get("date_unixtime", 0))
        published_at = datetime.fromtimestamp(date_unixtime, tz=timezone.utc).isoformat()

        state_db.import_raw_entry(
            language=args.language,
            number=number,
            message_id=chosen["id"],
            published_at=published_at,
        )
        imported += 1

    print(f"\nImport terminé : {imported} prédications enregistrées pour la langue '{args.language}'.")
    print("source_updated_at est NULL pour toutes -> le premier cycle de sync les retraitera comme 'à mettre à jour'.")


if __name__ == "__main__":
    sys.exit(main())
