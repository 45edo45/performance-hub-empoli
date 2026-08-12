import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "database" / "football.db"


def main() -> None:
    conn = sqlite3.connect(DATABASE_PATH)

    try:
        conn.execute("PRAGMA foreign_keys = ON")

        conn.executescript("""
        CREATE TABLE IF NOT EXISTS tipi_test (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            categoria TEXT NOT NULL,
            unita_misura TEXT NOT NULL,
            migliore_se_alto INTEGER NOT NULL DEFAULT 1,
            descrizione TEXT
        );

        CREATE TABLE IF NOT EXISTS sessioni_test (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            stagione_id INTEGER NOT NULL,
            categoria TEXT,
            descrizione TEXT,
            note TEXT,

            FOREIGN KEY (stagione_id)
                REFERENCES stagioni(id)
        );

        CREATE TABLE IF NOT EXISTS risultati_test (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sessione_test_id INTEGER NOT NULL,
            giocatore_id INTEGER NOT NULL,
            tipo_test_id INTEGER NOT NULL,
            valore REAL,
            valore_secondario REAL,
            valido INTEGER NOT NULL DEFAULT 1,
            note TEXT,

            FOREIGN KEY (sessione_test_id)
                REFERENCES sessioni_test(id)
                ON DELETE CASCADE,

            FOREIGN KEY (giocatore_id)
                REFERENCES giocatori(id),

            FOREIGN KEY (tipo_test_id)
                REFERENCES tipi_test(id),

            UNIQUE (
                sessione_test_id,
                giocatore_id,
                tipo_test_id
            )
        );
        """)

        conn.commit()

        righe = conn.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name IN (
                  'tipi_test',
                  'sessioni_test',
                  'risultati_test'
              )
            ORDER BY name
        """).fetchall()

        print("Tabelle trovate:")

        for riga in righe:
            print("-", riga[0])

    except sqlite3.Error as errore:
        conn.rollback()
        print(f"Errore SQLite: {errore}")
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()