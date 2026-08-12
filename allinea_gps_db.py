import re
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATABASE_FILE = BASE_DIR / "database" / "football.db"
DATABASE_PY = BASE_DIR / "utils" / "database.py"


def extract_gps_columns() -> list[str]:
    source = DATABASE_PY.read_text(encoding="utf-8")

    match = re.search(
        r"INSERT\s+INTO\s+gps\s*\((.*?)\)\s*VALUES",
        source,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if not match:
        raise RuntimeError(
            "Non trovo la query 'INSERT INTO gps (...) VALUES' "
            "dentro utils/database.py."
        )

    raw_columns = match.group(1)

    columns = [
        column.strip().strip('"').strip("'").strip("`").strip("[]")
        for column in raw_columns.split(",")
        if column.strip()
    ]

    return columns


def guess_sql_type(column: str) -> str:
    text_columns = {
        "data",
        "date",
        "nome",
        "cognome",
        "athlete",
        "durata",
        "duration",
        "ruolo",
        "role",
        "tipo",
        "type",
        "note",
        "sessione",
    }

    lower_column = column.lower()

    if lower_column == "id":
        return "INTEGER"

    if lower_column.endswith("_id"):
        return "INTEGER"

    if any(word in lower_column for word in text_columns):
        return "TEXT"

    return "REAL"


def main() -> None:
    if not DATABASE_FILE.exists():
        raise FileNotFoundError(
            f"Database non trovato: {DATABASE_FILE}"
        )

    if not DATABASE_PY.exists():
        raise FileNotFoundError(
            f"File non trovato: {DATABASE_PY}"
        )

    expected_columns = extract_gps_columns()

    with sqlite3.connect(DATABASE_FILE) as conn:
        existing_rows = conn.execute(
            "PRAGMA table_info(gps)"
        ).fetchall()

        if not existing_rows:
            raise RuntimeError(
                "La tabella gps non esiste nel database."
            )

        existing_columns = {
            row[1].lower()
            for row in existing_rows
        }

        missing_columns = [
            column
            for column in expected_columns
            if column.lower() not in existing_columns
        ]

        if not missing_columns:
            print("La tabella gps è già allineata.")
            return

        print("Colonne mancanti trovate:")

        for column in missing_columns:
            sql_type = guess_sql_type(column)

            safe_column = column.replace('"', '""')

            conn.execute(
                f'ALTER TABLE gps '
                f'ADD COLUMN "{safe_column}" {sql_type}'
            )

            print(f"- {column} ({sql_type})")

        conn.commit()

    print(
        f"\nOperazione completata: "
        f"aggiunte {len(missing_columns)} colonne."
    )


if __name__ == "__main__":
    main()