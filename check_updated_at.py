import sqlite3

DB_PATH = r"C:\Users\Gammie\Documents\Logiciels\logiciel\Ressources\matth25v6_fr.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM sermons")
total = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM sermons WHERE updated_at IS NULL OR TRIM(updated_at) = ''")
vides = cur.fetchone()[0]

print(f"Total sermons : {total}")
print(f"updated_at vide/NULL : {vides}")
print(f"updated_at renseigné : {total - vides}")

if vides > 0:
    print("\nExemples de sermons SANS updated_at :")
    cur.execute("SELECT number, title FROM sermons WHERE updated_at IS NULL OR TRIM(updated_at) = '' LIMIT 10")
    for number, title in cur.fetchall():
        print(f"  Kacou {number} - {title}")

print("\nExemples de valeurs updated_at (5 premiers sermons) :")
cur.execute("SELECT number, updated_at FROM sermons ORDER BY number ASC LIMIT 5")
for number, updated_at in cur.fetchall():
    print(f"  Kacou {number} -> {updated_at!r}")

conn.close()
