import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "database" / "football.db"


def colonna_esiste(
    conn: sqlite3.Connection,
    tabella: str,
    colonna: str,
) -> bool:
    righe = conn.execute(
        f"PRAGMA table_info({tabella})"
    ).fetchall()

    colonne = [riga[1] for riga in righe]

    return colonna in colonne


def aggiungi_colonna_se_manca(
    conn: sqlite3.Connection,
    tabella: str,
    colonna: str,
    definizione: str,
) -> None:
    if not colonna_esiste(
        conn,
        tabella,
        colonna,
    ):
        conn.execute(
            f"""
            ALTER TABLE {tabella}
            ADD COLUMN {colonna} {definizione}
            """
        )

        print(
            f"Aggiunta colonna: "
            f"{tabella}.{colonna}"
        )

    else:
        print(
            f"Colonna già presente: "
            f"{tabella}.{colonna}"
        )


def main() -> None:
    conn = sqlite3.connect(DATABASE_PATH)

    try:
        conn.execute("PRAGMA foreign_keys = ON")

        # Campi aggiuntivi per i risultati test
        aggiungi_colonna_se_manca(
            conn,
            "risultati_test",
            "lato",
            "TEXT DEFAULT 'BILATERALE'",
        )

        aggiungi_colonna_se_manca(
            conn,
            "risultati_test",
            "percentile",
            "REAL",
        )

        aggiungi_colonna_se_manca(
            conn,
            "risultati_test",
            "tentativo",
            "INTEGER DEFAULT 1",
        )

        # Dati corporei storicizzati
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dati_corporei (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                giocatore_id INTEGER NOT NULL,
                stagione_id INTEGER NOT NULL,
                data TEXT NOT NULL,
                peso_kg REAL,
                altezza_cm REAL,
                massa_grassa_percentuale REAL,
                note TEXT,

                FOREIGN KEY (giocatore_id)
                    REFERENCES giocatori(id),

                FOREIGN KEY (stagione_id)
                    REFERENCES stagioni(id),

                UNIQUE (
                    giocatore_id,
                    data
                )
            )
        """)

        conn.commit()

        print("")
        print("Aggiornamento completato.")
        print("")

        colonne_risultati = conn.execute(
            "PRAGMA table_info(risultati_test)"
        ).fetchall()

        print("Colonne risultati_test:")

        for colonna in colonne_risultati:
            print(
                "-",
                colonna[1],
                colonna[2],
            )

        print("")

        tabelle = conn.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'dati_corporei'
        """).fetchall()

        if tabelle:
            print(
                "Tabella dati_corporei presente."
            )

    except sqlite3.Error as errore:
        conn.rollback()

        print(
            f"Errore SQLite: {errore}"
        )

        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()