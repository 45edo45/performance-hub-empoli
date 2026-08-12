import sqlite3

old = sqlite3.connect("database/football_backup_old.db")
new = sqlite3.connect("database/football.db")

old_cursor = old.cursor()
new_cursor = new.cursor()

old_cursor.execute("""
SELECT 
    data,
    md,
    tipo,
    avversario,
    luogo,
    note
FROM sedute
""")

sedute = old_cursor.fetchall()

print("Sedute trovate:", len(sedute))

for s in sedute:
    new_cursor.execute("""
    INSERT INTO sedute
    (
        data,
        md,
        tipo,
        avversario,
        luogo,
        note
    )
    VALUES (?, ?, ?, ?, ?, ?)
    """, s)

new.commit()

print("Sedute importate")

old.close()
new.close()
