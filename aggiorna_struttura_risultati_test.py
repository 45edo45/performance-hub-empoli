import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "database" / "football.db"


def colonna_esiste(
    conn: sqlite3.Connection,
    tabella: str,
    colonna: str,
) -> bool:
    colonne = conn.execute(
        f"PRAGMA table_info({tabella})"
    ).fetchall()

    return colonna in [
        riga[1] for riga in colonne
    ]


def main() -> None:
    conn = sqlite3.connect(DATABASE_PATH)

    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("BEGIN")

        # Controlla che la tabella esista
        tabella_esistente = conn.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'risultati_test'
        """).fetchone()

        if not tabella_esistente:
            raise RuntimeError(
                "La tabella risultati_test non esiste."
            )

        ha_lato = colonna_esiste(
            conn,
            "risultati_test",
            "lato",
        )

        ha_percentile = colonna_esiste(
            conn,
            "risultati_test",
            "percentile",
        )

        ha_tentativo = colonna_esiste(
            conn,
            "risultati_test",
            "tentativo",
        )

        conn.execute("""
            CREATE TABLE risultati_test_nuova (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sessione_test_id INTEGER NOT NULL,
                giocatore_id INTEGER NOT NULL,
                tipo_test_id INTEGER NOT NULL,
                lato TEXT NOT NULL DEFAULT 'BILATERALE',
                tentativo INTEGER NOT NULL DEFAULT 1,
                valore REAL,
                valore_secondario REAL,
                percentile REAL,
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
                    tipo_test_id,
                    lato,
                    tentativo
                )
            )
        """)

        lato_sql = (
            "COALESCE(lato, 'BILATERALE')"
            if ha_lato
            else "'BILATERALE'"
        )

        percentile_sql = (
            "percentile"
            if ha_percentile
            else "NULL"
        )

        tentativo_sql = (
            "COALESCE(tentativo, 1)"
            if ha_tentativo
            else "1"
        )

        conn.execute(f"""
            INSERT INTO risultati_test_nuova (
                id,
                sessione_test_id,
                giocatore_id,
                tipo_test_id,
                lato,
                tentativo,
                valore,
                valore_secondario,
                percentile,
                valido,
                note
            )
            SELECT
                id,
                sessione_test_id,
                giocatore_id,
                tipo_test_id,
                {lato_sql},
                {tentativo_sql},
                valore,
                valore_secondario,
                {percentile_sql},
                valido,
                note
            FROM risultati_test
        """)

        conn.execute(
            "DROP TABLE risultati_test"
        )

        conn.execute("""
            ALTER TABLE risultati_test_nuova
            RENAME TO risultati_test
        """)

        conn.commit()

        print(
            "Struttura risultati_test aggiornata correttamente."
        )

        colonne = conn.execute(
            "PRAGMA table_info(risultati_test)"
        ).fetchall()

        print("\nColonne presenti:")

        for colonna in colonne:
            print(
                f"- {colonna[1]} ({colonna[2]})"
            )

        indici = conn.execute(
            "PRAGMA index_list(risultati_test)"
        ).fetchall()

        print("\nIndici presenti:")

        for indice in indici:
            print(f"- {indice[1]}")

    except Exception as errore:
        conn.rollback()

        print(
            f"Errore durante l'aggiornamento: {errore}"
        )

        raise

    finally:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.close()


if __name__ == "__main__":
    main()