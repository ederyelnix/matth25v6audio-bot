import sqlite3

DB_PATH = r"C:\Users\Gammie\Documents\Logiciels\logiciel\Ressources\matth25v6_fr.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("Exemples de publication_date (5 premiers sermons) :")
cur.execute("SELECT number, publication_date FROM sermons ORDER BY number ASC LIMIT 5")
for number, pub_date in cur.fetchall():
    print(f"  Kacou {number} -> {pub_date!r}")

conn.close()
