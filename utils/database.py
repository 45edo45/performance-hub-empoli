import os
import re
import sqlite3
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# PERCORSO DB LOCALE (usato solo in modalità SQLite)
# ─────────────────────────────────────────────────────────────
_BASE_DIR = Path(__file__).resolve().parent.parent
_DB_DIR   = _BASE_DIR / "database"
_DB_DIR.mkdir(exist_ok=True)
DB_PATH   = str(_DB_DIR / "football.db")

# ─────────────────────────────────────────────────────────────
# LAYER DI COMPATIBILITÀ SQLite ↔ PostgreSQL
#
# Se la variabile d'ambiente DATABASE_URL è impostata
# (Supabase/Streamlit Cloud) usa PostgreSQL.
# Altrimenti usa SQLite locale — comportamento invariato.
# ─────────────────────────────────────────────────────────────
# Legge DATABASE_URL al momento della connessione (lazy),
# quando Streamlit è già inizializzato.
def _load_db_url() -> str:
    # 1. Variabile d'ambiente (funziona sempre, utile per test locali)
    url = os.environ.get("DATABASE_URL", "")
    if url:
        return url
    # 2. st.secrets (Streamlit Cloud)
    try:
        import streamlit as st
        url = st.secrets["DATABASE_URL"]
        if url:
            return str(url).strip()
    except Exception:
        pass
    return ""


class _Row:
    """
    Riga risultato PostgreSQL compatibile con sqlite3.Row.
    - row['col']  → accesso per nome
    - row[0]      → accesso per indice
    - iter(row)   → itera sui VALORI (non sulle chiavi)
      così pd.DataFrame(rows, columns=[...]) usa la posizione, non i nomi,
      esattamente come fa sqlite3.Row.
    """
    __slots__ = ("_keys", "_vals")

    def __init__(self, mapping):
        self._keys = list(mapping.keys())
        self._vals = list(mapping.values())

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._vals[key]
        try:
            return self._vals[self._keys.index(key)]
        except ValueError:
            raise KeyError(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __iter__(self):
        return iter(self._vals)

    def __len__(self):
        return len(self._vals)

    def keys(self):
        return self._keys

    def values(self):
        return self._vals

    def items(self):
        return zip(self._keys, self._vals)


class _Cursor:
    """Cursore unificato: gestisce differenze di placeholder, DDL e lastrowid."""

    def __init__(self, raw_cur, is_pg: bool):
        self._c = raw_cur
        self._pg = is_pg
        self.lastrowid = None
        self.rowcount = 0

    @property
    def description(self):
        return self._c.description

    # ------------------------------------------------------------------
    # Adattamento SQL: converte SQLite → PostgreSQL dove necessario
    # ------------------------------------------------------------------
    def _adapt(self, sql: str, is_insert_ignore: bool = False) -> str:
        if not self._pg:
            return sql

        # Placeholder: ? → %s
        sql = sql.replace("?", "%s")

        # DDL: AUTOINCREMENT → SERIAL
        sql = re.sub(
            r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
            "SERIAL PRIMARY KEY",
            sql, flags=re.IGNORECASE,
        )

        # PRAGMA table_info → information_schema
        m = re.match(r"\s*PRAGMA\s+table_info\((\w+)\)", sql, re.IGNORECASE)
        if m:
            tbl = m.group(1).lower()
            return (
                "SELECT ordinal_position-1 AS cid, column_name AS name, "
                "data_type AS type, 0 AS notnull, column_default AS dflt_value, "
                "CASE WHEN column_name='id' THEN 1 ELSE 0 END AS pk "
                f"FROM information_schema.columns WHERE table_name='{tbl}' "
                "ORDER BY ordinal_position"
            )

        # GROUP_CONCAT → STRING_AGG (PostgreSQL)
        # [\w.]+ cattura sia "colonna" che "tabella.colonna"
        # re.DOTALL permette che il match attraversi newline (query multi-riga)
        sql = re.sub(
            r"GROUP_CONCAT\(\s*([\w.]+)\s*,\s*'([^']*)'\s*\)",
            lambda m: f"STRING_AGG({m.group(1)}::TEXT, '{m.group(2)}')",
            sql, flags=re.IGNORECASE | re.DOTALL,
        )
        sql = re.sub(
            r"GROUP_CONCAT\(\s*([\w.]+)\s*\)",
            lambda m: f"STRING_AGG({m.group(1)}::TEXT, ',')",
            sql, flags=re.IGNORECASE | re.DOTALL,
        )

        # INSERT OR IGNORE → INSERT … ON CONFLICT DO NOTHING
        if is_insert_ignore or re.search(r"INSERT\s+OR\s+IGNORE", sql, re.IGNORECASE):
            sql = re.sub(
                r"INSERT\s+OR\s+IGNORE\s+INTO", "INSERT INTO",
                sql, flags=re.IGNORECASE,
            )
            sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"

        return sql

    # ------------------------------------------------------------------
    def execute(self, sql: str, params=()):
        is_ignore = bool(re.search(r"INSERT\s+OR\s+IGNORE", sql, re.IGNORECASE))
        adapted = self._adapt(sql, is_ignore)

        if self._pg:
            is_insert = bool(re.match(r"\s*INSERT\b", adapted, re.IGNORECASE))
            has_conflict = "ON CONFLICT" in adapted.upper()
            has_returning = "RETURNING" in adapted.upper()

            # Aggiungi RETURNING id ai normali INSERT per catturare lastrowid
            if is_insert and not has_conflict and not has_returning:
                adapted = adapted.rstrip().rstrip(";") + " RETURNING id"

            self._c.execute(adapted, params or None)
            self.rowcount = self._c.rowcount

            if is_insert and not has_conflict and not has_returning:
                row = self._c.fetchone()
                self.lastrowid = (
                    row.get("id") if isinstance(row, dict) else (row[0] if row else None)
                )
        else:
            self._c.execute(adapted, params)
            self.rowcount = self._c.rowcount
            self.lastrowid = self._c.lastrowid

        return self

    def executescript(self, sql: str):
        """Esegue uno script SQL multi-statement (CREATE TABLE, INSERT, …)."""
        if self._pg:
            for stmt in sql.split(";"):
                stmt = stmt.strip()
                if not stmt or stmt.startswith("--"):
                    continue
                is_ignore = bool(re.search(r"INSERT\s+OR\s+IGNORE", stmt, re.IGNORECASE))
                adapted = self._adapt(stmt, is_ignore)
                try:
                    self._c.execute(adapted)
                except Exception as exc:
                    print(f"[db-init] {exc}")
        else:
            # sqlite3.Cursor non ha executescript: lo chiamiamo sulla conn
            self._c.connection.executescript(sql)

    def fetchall(self):
        rows = self._c.fetchall()
        if self._pg:
            return [_Row(r) for r in rows]
        # SQLite: restituiamo sqlite3.Row originali.
        # Supportano sia row[0] (indice int), row['col'] (str),
        # dict(row) e pd.DataFrame(rows, columns=[...]) come sequenze.
        return rows

    def fetchone(self):
        row = self._c.fetchone()
        if row is None:
            return None
        if self._pg:
            return _Row(row)
        return row  # sqlite3.Row — supporta int e str indexing


class _Conn:
    """Connessione unificata: SQLite in locale, PostgreSQL su Supabase/cloud."""

    def __init__(self):
        db_url = _load_db_url()
        is_pg  = bool(re.search(r"postgres", db_url, re.IGNORECASE))

        if is_pg:
            import psycopg2
            import psycopg2.extras
            self._raw = psycopg2.connect(db_url)
            self._pg = True
            self._cur_factory = psycopg2.extras.RealDictCursor
        else:
            self._raw = sqlite3.connect(DB_PATH)
            self._raw.row_factory = sqlite3.Row
            self._pg = False
            self._cur_factory = None
        # Attributo stub per compatibilità con codice che fa conn.row_factory = …
        self.row_factory = None

    def cursor(self):
        if self._pg:
            return _Cursor(self._raw.cursor(cursor_factory=self._cur_factory), is_pg=True)
        return _Cursor(self._raw.cursor(), is_pg=False)

    def execute(self, sql: str, params=()):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def executescript(self, sql: str):
        cur = self.cursor()
        cur.executescript(sql)
        if self._pg:
            self._raw.commit()

    def commit(self):
        self._raw.commit()

    def rollback(self):
        self._raw.rollback()

    def close(self):
        try:
            self._raw.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


# ==========================
# CONNESSIONE DATABASE
# ==========================

def get_connection():
    return _Conn()



# ==========================
# CREAZIONE DATABASE
# ==========================

def create_database():

    conn = get_connection()
    cursor = conn.cursor()


    # ==========================
    # STAGIONI
    # ==========================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stagioni (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        nome TEXT,

        attiva INTEGER DEFAULT 0

    )
    """)



    # ==========================
    # GIOCATORI
    # ==========================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS giocatori (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        nome TEXT,

        cognome TEXT,

        ruolo TEXT,

        anno INTEGER,

        maglia INTEGER,

        note TEXT

    )
    """)



    # ==========================
    # SEDUTE
    # ==========================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sedute (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        data TEXT,

        md TEXT,

        tipo TEXT,

        avversario TEXT,

        luogo TEXT,

        stagione_id INTEGER,

        note TEXT

    )
    """)



    # ==========================
    # GPS
    # ==========================

    # ==========================
    # CARDIO (FirstBeat)
    # ==========================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cardio (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        seduta_id INTEGER NOT NULL,
        giocatore_id INTEGER NOT NULL,
        fc_media REAL,
        fc_media_pct REAL,
        fc_max REAL,
        fc_max_pct REAL,
        trimp REAL,
        trimp_min REAL,
        te_aerobico REAL,
        te_anaerobico REAL,
        epoc REAL,
        calorie REAL,
        vo2_medio REAL,
        vo2_picco REAL,
        hr_z_recupero REAL,
        hr_z1 REAL,
        hr_z2 REAL,
        hr_z3 REAL,
        hr_z4 REAL,
        hrr_30 REAL,
        hrr_60 REAL,
        hrr_120 REAL,
        valido INTEGER DEFAULT 1,
        escluso_motivo TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gps (

        id INTEGER PRIMARY KEY AUTOINCREMENT,


        seduta_id INTEGER,

        giocatore_id INTEGER,


        durata REAL,

        distanza REAL,

        meters_min REAL,


        max_speed REAL,

        z2 REAL,

        z3 REAL,

        z4 REAL,


        hsr REAL,

        vhsr REAL,


        speed_events INTEGER,


        bursts INTEGER,

        brakes INTEGER,


        high_ext_work_plus REAL,

        high_ext_work_minus REAL,

        eccentric_index REAL,


        energy REAL,

        eq_distance_index REAL,

        avg_metabolic_power REAL,

        met_power_events INTEGER,

        mpe_rec_avg_time REAL,

        mpe_rec_avg_power REAL,


        hr_z2 REAL,

        hr_z3 REAL,


        hsr_min REAL,

        sprint_min REAL,

        accel_min REAL,

        decel_min REAL,


        valido INTEGER DEFAULT 1,

        escluso_motivo TEXT,

        nota_analista TEXT

    )
    """)



    # ==========================
    # LOG IMPORT
    # ==========================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS import_log (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        data_import TEXT,

        nome_file TEXT,

        seduta_id INTEGER,

        record_importati INTEGER,

        errori TEXT,

        note TEXT

    )
    """)



    conn.commit()
    conn.close()



# ==========================
# GIOCATORI
# ==========================

def get_players():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM giocatori
        ORDER BY cognome, nome
    """)

    rows = cursor.fetchall()
    conn.close()

    return rows



def add_player(nome, cognome, ruolo, anno, maglia, note):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO giocatori (
            nome,
            cognome,
            ruolo,
            anno,
            maglia,
            note
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        nome,
        cognome,
        ruolo,
        anno,
        maglia,
        note
    ))

    giocatore_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return giocatore_id



# ==========================
# SEDUTE
# ==========================

def get_sessions():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            data,
            md,
            tipo,
            avversario,
            luogo,
            note,
            stagione_id,
            fase_stagione,
            momento_giornata
        FROM sedute
        ORDER BY data DESC, id DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    return rows



def add_session(
    data,
    md,
    tipo,
    avversario,
    luogo,
    stagione_id,
    fase_stagione,
    momento_giornata,
    note
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO sedute (
            data,
            md,
            tipo,
            avversario,
            luogo,
            stagione_id,
            fase_stagione,
            momento_giornata,
            note
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data,
        md,
        tipo,
        avversario,
        luogo,
        stagione_id,
        fase_stagione,
        momento_giornata,
        note
    ))

    conn.commit()
    conn.close()


# ==========================
# GPS
# ==========================

def get_player_id(cognome, iniziale):

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute("""
    SELECT id
    FROM giocatori
    WHERE UPPER(cognome) = UPPER(?)
    AND UPPER(substr(nome,1,1)) = UPPER(?)

    """,
    (
        cognome,
        iniziale
    ))


    row = cursor.fetchone()


    conn.close()


    if row:

        return row[0]


    return None



# ==========================
# CONTROLLO DATI GPS
# ==========================

def count_gps_by_session(seduta_id):

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute("""
    SELECT COUNT(*)
    FROM gps
    WHERE seduta_id = ?

    """,
    (seduta_id,))


    result = cursor.fetchone()[0]


    conn.close()


    return result



# ==========================
# INSERIMENTO GPS COMPLETO
# ==========================

def add_gps(

    seduta_id,

    giocatore_id,

    durata,

    distanza,

    meters_min,

    max_speed,

    z2,

    z3,

    z4,

    hsr,

    vhsr,

    speed_events,

    bursts,

    brakes,

    high_ext_work_plus,

    high_ext_work_minus,

    eccentric_index,

    energy,

    eq_distance_index,

    avg_metabolic_power,

    met_power_events,

    mpe_rec_avg_time,

    mpe_rec_avg_power,

    hr_z2,

    hr_z3,

    hsr_min,

    sprint_min,

    accel_min,

    decel_min,

    valido=1,

    escluso_motivo=None,

    nota_analista=None

):

    conn = get_connection()

    cursor = conn.cursor()


    cursor.execute("""

    INSERT INTO gps (

        seduta_id,

        giocatore_id,

        durata,

        distanza,

        meters_min,

        max_speed,

        z2,

        z3,

        z4,

        hsr,

        vhsr,

        speed_events,

        bursts,

        brakes,

        high_ext_work_plus,

        high_ext_work_minus,

        eccentric_index,

        energy,

        eq_distance_index,

        avg_metabolic_power,

        met_power_events,

        mpe_rec_avg_time,

        mpe_rec_avg_power,

        hr_z2,

        hr_z3,

        hsr_min,

        sprint_min,

        accel_min,

        decel_min,

        valido,

        escluso_motivo,

        nota_analista

    )


    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)

    """,

    (

        seduta_id,

        giocatore_id,

        durata,

        distanza,

        meters_min,

        max_speed,

        z2,

        z3,

        z4,

        hsr,

        vhsr,

        speed_events,

        bursts,

        brakes,

        high_ext_work_plus,

        high_ext_work_minus,

        eccentric_index,

        energy,

        eq_distance_index,

        avg_metabolic_power,

        met_power_events,

        mpe_rec_avg_time,

        mpe_rec_avg_power,

        hr_z2,

        hr_z3,

        hsr_min,

        sprint_min,

        accel_min,

        decel_min,

        valido,

        escluso_motivo,

        nota_analista

    ))


    conn.commit()

    conn.close()



# ==========================
# ELIMINA GPS DI UNA SEDUTA
# ==========================

def delete_gps_by_session(seduta_id):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM gps
        WHERE seduta_id = ?
    """, (seduta_id,))


    conn.commit()

    conn.close()



# ==========================
# IMPORT GIOCATORI CSV
# ==========================

def import_players_csv(path):

    import pandas as pd


    df = pd.read_csv(path)


    conn = get_connection()

    cursor = conn.cursor()


    for _, row in df.iterrows():

        cursor.execute("""
        INSERT INTO giocatori
        (
            nome,
            cognome,
            ruolo,
            anno_nascita,
            maglia,
            note
        )

        VALUES (?, ?, ?, ?, ?, ?)

        """,
        (
            row.get("Nome"),
            row.get("Cognome"),
            row.get("Ruolo"),
            row.get("Anno_nascita"),
            row.get("Numero_maglia"),
            row.get("Note")
        ))


    conn.commit()

    conn.close()

def get_gps_by_session(seduta_id):
    conn = get_connection()
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            gps.*,
            giocatori.nome,
            giocatori.cognome
        FROM gps
        LEFT JOIN giocatori
            ON gps.giocatore_id = giocatori.id
        WHERE gps.seduta_id = ?
        ORDER BY giocatori.cognome, giocatori.nome
    """, (seduta_id,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]

def get_players_by_season(stagione_id):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            giocatori.id,
            giocatori.nome,
            giocatori.cognome,
            rose_stagionali.numero_maglia,
            rose_stagionali.ruolo,
            rose_stagionali.attivo
        FROM rose_stagionali
        JOIN giocatori
            ON rose_stagionali.giocatore_id = giocatori.id
        WHERE rose_stagionali.stagione_id = ?
        ORDER BY giocatori.cognome, giocatori.nome
        """,
        (stagione_id,),
    )

    rows = cursor.fetchall()
    conn.close()

    return [
        dict(row)
        for row in rows
    ]

def get_seasons():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, nome, attiva
        FROM stagioni
        ORDER BY nome DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]

def add_player_to_season(
    giocatore_id,
    stagione_id,
    numero_maglia=None,
    ruolo=None,
    attivo=1
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO rose_stagionali (
            giocatore_id,
            stagione_id,
            numero_maglia,
            ruolo,
            attivo
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        giocatore_id,
        stagione_id,
        numero_maglia,
        ruolo,
        attivo
    ))

    conn.commit()
    conn.close()

def update_player_season_status(
    giocatore_id,
    stagione_id,
    attivo
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE rose_stagionali
        SET attivo = ?
        WHERE giocatore_id = ?
        AND stagione_id = ?
    """, (
        int(attivo),
        giocatore_id,
        stagione_id
    ))

    conn.commit()
    conn.close()

def update_player_season_data(
    giocatore_id,
    stagione_id,
    numero_maglia,
    ruolo
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE rose_stagionali
        SET
            numero_maglia = ?,
            ruolo = ?
        WHERE giocatore_id = ?
        AND stagione_id = ?
    """, (
        numero_maglia,
        ruolo,
        giocatore_id,
        stagione_id
    ))

    conn.commit()
    conn.close()

def remove_player_from_season(
    giocatore_id,
    stagione_id
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM rose_stagionali
        WHERE giocatore_id = ?
          AND stagione_id = ?
    """, (
        giocatore_id,
        stagione_id
    ))

    conn.commit()
    conn.close()

def get_all_players():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            nome,
            cognome,
            ruolo,
            anno,
            maglia,
            note
        FROM giocatori
        ORDER BY cognome, nome
    """)

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_active_season_id():
    """Restituisce l'id della stagione attiva, o None se non esiste."""
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM stagioni WHERE attiva = 1 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row[0] if row else None


def get_active_season_players():
    """
    Restituisce i giocatori attivi nella stagione corrente (stagioni.attiva=1,
    rose_stagionali.attivo=1). Se non c'è una stagione attiva, torna vuoto.
    """
    stagione_id = get_active_season_id()
    if stagione_id is None:
        return []
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT
            giocatori.id,
            giocatori.nome,
            giocatori.cognome,
            rose_stagionali.numero_maglia AS maglia,
            rose_stagionali.ruolo,
            rose_stagionali.attivo
        FROM rose_stagionali
        JOIN giocatori ON rose_stagionali.giocatore_id = giocatori.id
        WHERE rose_stagionali.stagione_id = ?
          AND rose_stagionali.attivo = 1
        ORDER BY giocatori.cognome, giocatori.nome
    """, (stagione_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_session(seduta_id):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            DELETE FROM gps
            WHERE seduta_id = ?
            """,
            (seduta_id,)
        )

        cursor.execute(
            """
            DELETE FROM sedute
            WHERE id = ?
            """,
            (seduta_id,)
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_test_types():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            nome,
            categoria,
            unita_misura,
            migliore_se_alto,
            descrizione
        FROM tipi_test
        ORDER BY categoria, nome
    """)

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def add_test_type(
    nome,
    categoria,
    unita_misura,
    migliore_se_alto,
    descrizione=None
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO tipi_test (
            nome,
            categoria,
            unita_misura,
            migliore_se_alto,
            descrizione
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        nome,
        categoria,
        unita_misura,
        int(migliore_se_alto),
        descrizione
    ))

    tipo_test_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return tipo_test_id


def add_test_session(
    data,
    stagione_id,
    categoria,
    descrizione,
    note=None
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO sessioni_test (
            data,
            stagione_id,
            categoria,
            descrizione,
            note
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        data,
        stagione_id,
        categoria,
        descrizione,
        note
    ))

    sessione_test_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return sessione_test_id


def get_test_sessions(stagione_id):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            data,
            categoria,
            descrizione,
            note
        FROM sessioni_test
        WHERE stagione_id = ?
        ORDER BY data DESC, id DESC
    """, (stagione_id,))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def save_test_result(
    sessione_test_id,
    giocatore_id,
    tipo_test_id,
    valore,
    lato="BILATERALE",
    tentativo=1,
    percentile=None,
    valore_secondario=None,
    valido=1,
    note=None,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO risultati_test (
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT (
            sessione_test_id,
            giocatore_id,
            tipo_test_id,
            lato,
            tentativo
        )

        DO UPDATE SET
            valore = excluded.valore,
            valore_secondario = excluded.valore_secondario,
            percentile = excluded.percentile,
            valido = excluded.valido,
            note = excluded.note
    """, (
        sessione_test_id,
        giocatore_id,
        tipo_test_id,
        lato,
        tentativo,
        valore,
        valore_secondario,
        percentile,
        int(valido),
        note,
    ))

    conn.commit()
    conn.close()


def get_test_results_by_session(
    sessione_test_id
):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            risultati_test.id,
            risultati_test.sessione_test_id,
            risultati_test.giocatore_id,
            risultati_test.tipo_test_id,

            giocatori.nome,
            giocatori.cognome,

            tipi_test.nome AS test,
            tipi_test.categoria,
            tipi_test.unita_misura,
            tipi_test.migliore_se_alto,

            risultati_test.lato,
            risultati_test.tentativo,
            risultati_test.valore,
            risultati_test.valore_secondario,
            risultati_test.percentile,
            risultati_test.valido,
            risultati_test.note

        FROM risultati_test

        JOIN giocatori
            ON risultati_test.giocatore_id
            = giocatori.id

        JOIN tipi_test
            ON risultati_test.tipo_test_id
            = tipi_test.id

        WHERE risultati_test.sessione_test_id = ?

        ORDER BY
            giocatori.cognome,
            giocatori.nome,
            tipi_test.nome,
            risultati_test.lato,
            risultati_test.tentativo
    """, (
        sessione_test_id,
    ))

    rows = cursor.fetchall()
    conn.close()

    return [
        dict(row)
        for row in rows
    ]


def get_player_test_history(
    giocatore_id,
    tipo_test_id,
):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            risultati_test.id,
            risultati_test.sessione_test_id,
            risultati_test.giocatore_id,
            risultati_test.tipo_test_id,
            risultati_test.lato,
            risultati_test.tentativo,
            risultati_test.valore,
            risultati_test.percentile,
            risultati_test.valido,
            risultati_test.note,

            sessioni_test.data,
            sessioni_test.categoria AS categoria_sessione,
            sessioni_test.descrizione AS sessione,

            tipi_test.nome AS test,
            tipi_test.categoria,
            tipi_test.unita_misura,
            tipi_test.migliore_se_alto

        FROM risultati_test

        JOIN sessioni_test
            ON risultati_test.sessione_test_id = sessioni_test.id

        JOIN tipi_test
            ON risultati_test.tipo_test_id = tipi_test.id

        WHERE risultati_test.giocatore_id = ?
          AND risultati_test.tipo_test_id = ?
          AND risultati_test.valido = 1
          AND risultati_test.valore IS NOT NULL

        ORDER BY
            sessioni_test.data DESC,
            risultati_test.sessione_test_id DESC,
            risultati_test.lato,
            risultati_test.tentativo
    """, (
        giocatore_id,
        tipo_test_id,
    ))

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def update_test_type(
    tipo_test_id,
    nome,
    categoria,
    unita_misura,
    migliore_se_alto,
    descrizione=None,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE tipi_test
        SET
            nome = ?,
            categoria = ?,
            unita_misura = ?,
            migliore_se_alto = ?,
            descrizione = ?
        WHERE id = ?
        """,
        (
            nome,
            categoria,
            unita_misura,
            int(migliore_se_alto),
            descrizione,
            tipo_test_id,
        ),
    )

    conn.commit()
    conn.close()


def delete_test_type(tipo_test_id):
    conn = get_connection()
    cursor = conn.cursor()

    risultati_collegati = cursor.execute(
        """
        SELECT COUNT(*)
        FROM risultati_test
        WHERE tipo_test_id = ?
        """,
        (tipo_test_id,),
    ).fetchone()[0]

    if risultati_collegati > 0:
        conn.close()

        raise ValueError(
            "Non puoi eliminare questo test perché contiene "
            "risultati già registrati."
        )

    cursor.execute(
        """
        DELETE FROM tipi_test
        WHERE id = ?
        """,
        (tipo_test_id,),
    )

    conn.commit()
    conn.close()


def update_test_session(
    sessione_test_id,
    data,
    categoria,
    descrizione,
    note=None,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE sessioni_test
        SET
            data = ?,
            categoria = ?,
            descrizione = ?,
            note = ?
        WHERE id = ?
        """,
        (
            data,
            categoria,
            descrizione,
            note,
            sessione_test_id,
        ),
    )

    conn.commit()
    conn.close()


def delete_test_session(sessione_test_id):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            DELETE FROM risultati_test
            WHERE sessione_test_id = ?
            """,
            (sessione_test_id,),
        )

        cursor.execute(
            """
            DELETE FROM sessioni_test
            WHERE id = ?
            """,
            (sessione_test_id,),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def update_test_result(
    risultato_id,
    valore,
    lato,
    tentativo,
    percentile=None,
    valido=1,
    note=None,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE risultati_test
        SET
            valore = ?,
            lato = ?,
            tentativo = ?,
            percentile = ?,
            valido = ?,
            note = ?
        WHERE id = ?
        """,
        (
            valore,
            lato,
            tentativo,
            percentile,
            int(valido),
            note,
            risultato_id,
        ),
    )

    conn.commit()
    conn.close()


def delete_test_result(risultato_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM risultati_test
        WHERE id = ?
        """,
        (risultato_id,),
    )

    conn.commit()
    conn.close()


def get_test_result_by_id(risultato_id):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            risultati_test.id,
            risultati_test.sessione_test_id,
            risultati_test.giocatore_id,
            risultati_test.tipo_test_id,
            risultati_test.valore,
            risultati_test.lato,
            risultati_test.tentativo,
            risultati_test.percentile,
            risultati_test.valido,
            risultati_test.note,
            giocatori.nome,
            giocatori.cognome,
            tipi_test.nome AS test,
            tipi_test.unita_misura,
            sessioni_test.data
        FROM risultati_test
        JOIN giocatori
            ON risultati_test.giocatore_id = giocatori.id
        JOIN tipi_test
            ON risultati_test.tipo_test_id = tipi_test.id
        JOIN sessioni_test
            ON risultati_test.sessione_test_id = sessioni_test.id
        WHERE risultati_test.id = ?
        """,
        (risultato_id,),
    )

    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


def save_body_data(
    giocatore_id,
    stagione_id,
    data,
    peso_kg=None,
    altezza_cm=None,
    massa_grassa_percentuale=None,
    note=None,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO dati_corporei (
            giocatore_id,
            stagione_id,
            data,
            peso_kg,
            altezza_cm,
            massa_grassa_percentuale,
            note
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT (giocatore_id, data)
        DO UPDATE SET
            stagione_id = excluded.stagione_id,
            peso_kg = excluded.peso_kg,
            altezza_cm = excluded.altezza_cm,
            massa_grassa_percentuale =
                excluded.massa_grassa_percentuale,
            note = excluded.note
        """,
        (
            giocatore_id,
            stagione_id,
            data,
            peso_kg,
            altezza_cm,
            massa_grassa_percentuale,
            note,
        ),
    )

    conn.commit()
    conn.close()


def get_body_data_by_season(stagione_id):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            dati_corporei.id,
            dati_corporei.giocatore_id,
            dati_corporei.stagione_id,
            dati_corporei.data,
            dati_corporei.peso_kg,
            dati_corporei.altezza_cm,
            dati_corporei.massa_grassa_percentuale,
            dati_corporei.note,
            giocatori.nome,
            giocatori.cognome
        FROM dati_corporei
        JOIN giocatori
            ON dati_corporei.giocatore_id = giocatori.id
        WHERE dati_corporei.stagione_id = ?
        ORDER BY
            dati_corporei.data DESC,
            giocatori.cognome,
            giocatori.nome
        """,
        (stagione_id,),
    )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def update_body_data(
    dato_corporeo_id,
    data,
    peso_kg=None,
    altezza_cm=None,
    massa_grassa_percentuale=None,
    note=None,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE dati_corporei
        SET
            data = ?,
            peso_kg = ?,
            altezza_cm = ?,
            massa_grassa_percentuale = ?,
            note = ?
        WHERE id = ?
        """,
        (
            data,
            peso_kg,
            altezza_cm,
            massa_grassa_percentuale,
            note,
            dato_corporeo_id,
        ),
    )

    conn.commit()
    conn.close()


def delete_body_data(dato_corporeo_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM dati_corporei
        WHERE id = ?
        """,
        (dato_corporeo_id,),
    )

    conn.commit()
    conn.close()


def get_latest_body_weight(
    giocatore_id,
    data_riferimento=None,
):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if data_riferimento:
        cursor.execute(
            """
            SELECT
                id,
                data,
                peso_kg
            FROM dati_corporei
            WHERE giocatore_id = ?
              AND peso_kg IS NOT NULL
              AND peso_kg > 0
              AND data <= ?
            ORDER BY data DESC, id DESC
            LIMIT 1
            """,
            (
                giocatore_id,
                data_riferimento,
            ),
        )

    else:
        cursor.execute(
            """
            SELECT
                id,
                data,
                peso_kg
            FROM dati_corporei
            WHERE giocatore_id = ?
              AND peso_kg IS NOT NULL
              AND peso_kg > 0
            ORDER BY data DESC, id DESC
            LIMIT 1
            """,
            (giocatore_id,),
        )

    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


def get_player_cpet_profile(
    giocatore_id,
    data_riferimento=None,
):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    nomi_test = [
        "VO2max relativo",
        "VO2max assoluto",
        "Velocità massima CPET",
        "FC massima CPET",
        "Velocità soglia anaerobica",
        "FC soglia anaerobica",
    ]

    placeholders = ",".join(
        ["?"] * len(nomi_test)
    )

    parametri = [
        giocatore_id,
        *nomi_test,
    ]

    filtro_data = ""

    if data_riferimento:
        filtro_data = """
            AND sessioni_test.data <= ?
        """

        parametri.append(
            data_riferimento
        )

    cursor.execute(
        f"""
        SELECT
            risultati_test.id,
            risultati_test.giocatore_id,
            risultati_test.tipo_test_id,
            risultati_test.valore,
            risultati_test.percentile,
            risultati_test.note,

            tipi_test.nome AS test,
            tipi_test.unita_misura,

            sessioni_test.id AS sessione_test_id,
            sessioni_test.data,
            sessioni_test.descrizione AS sessione

        FROM risultati_test

        JOIN tipi_test
            ON risultati_test.tipo_test_id
            = tipi_test.id

        JOIN sessioni_test
            ON risultati_test.sessione_test_id
            = sessioni_test.id

        WHERE risultati_test.giocatore_id = ?
          AND tipi_test.nome IN (
              {placeholders}
          )
          AND risultati_test.valido = 1
          AND risultati_test.valore IS NOT NULL
          {filtro_data}

        ORDER BY
            sessioni_test.data DESC,
            risultati_test.sessione_test_id DESC,
            risultati_test.id DESC
        """,
        tuple(parametri),
    )

    rows = cursor.fetchall()
    conn.close()

    profilo = {}

    for row in rows:
        dato = dict(row)
        nome_test = dato["test"]

        # Mantiene soltanto il risultato più recente
        # per ciascun parametro CPET.
        if nome_test not in profilo:
            profilo[nome_test] = dato

    return profilo


def get_player_gps_history(
    giocatore_id,
    data_fine=None,
    giorni=28,
):
    conn = get_connection()

    query = """
        SELECT
            g.*,
            s.data AS data_seduta,
            s.md,
            s.tipo,
            s.avversario
        FROM gps g
        JOIN sedute s
            ON s.id = g.seduta_id
        WHERE g.giocatore_id = ?
          AND COALESCE(g.valido, 1) = 1
    """

    parametri = [int(giocatore_id)]

    if data_fine:
        query += """
            AND date(s.data) <= date(?)
            AND date(s.data) >= date(?, ?)
        """

        parametri.extend(
            [
                str(data_fine),
                str(data_fine),
                f"-{int(giorni)} days",
            ]
        )

    query += """
        ORDER BY date(s.data) DESC, g.id DESC
    """

    righe = conn.execute(
        query,
        parametri,
    ).fetchall()

    conn.close()

    return [
        dict(riga)
        for riga in righe
    ]


def find_test_session_duplicate(
    data,
    stagione_id,
    categoria,
    descrizione=None,
):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
        SELECT
            id,
            data,
            stagione_id,
            categoria,
            descrizione,
            note
        FROM sessioni_test
        WHERE data = ?
          AND stagione_id = ?
          AND categoria = ?
    """

    parametri = [
        str(data),
        int(stagione_id),
        str(categoria),
    ]

    if descrizione:
        query += """
          AND TRIM(LOWER(descrizione))
              = TRIM(LOWER(?))
        """

        parametri.append(
            str(descrizione)
        )

    query += """
        ORDER BY id DESC
        LIMIT 1
    """

    riga = cursor.execute(
        query,
        parametri,
    ).fetchone()

    conn.close()

    return (
        dict(riga)
        if riga
        else None
    )


def init_training_report_tables():
    """
    Crea le tabelle necessarie per:
    - allenamenti;
    - esercitazioni;
    - ripetizioni;
    - partite;
    - metriche GPS individuali.
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS macro_tipologie_esercitazioni (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            attiva INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS obiettivi_attivita (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            attivo INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS catalogo_esercitazioni (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            macro_tipologia_id INTEGER,
            obiettivo_principale_id INTEGER,
            descrizione TEXT,
            attiva INTEGER NOT NULL DEFAULT 1,

            UNIQUE (
                nome,
                macro_tipologia_id,
                obiettivo_principale_id
            ),

            FOREIGN KEY (
                macro_tipologia_id
            ) REFERENCES macro_tipologie_esercitazioni(id),

            FOREIGN KEY (
                obiettivo_principale_id
            ) REFERENCES obiettivi_attivita(id)
        );

                CREATE TABLE IF NOT EXISTS tag_esercitazioni (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            nome TEXT NOT NULL UNIQUE,

            descrizione TEXT,

            attivo INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS catalogo_esercitazioni_tag (
            esercitazione_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,

            PRIMARY KEY (
                esercitazione_id,
                tag_id
            ),

            FOREIGN KEY (
                esercitazione_id
            ) REFERENCES catalogo_esercitazioni(id)
                ON DELETE CASCADE,

            FOREIGN KEY (
                tag_id
            ) REFERENCES tag_esercitazioni(id)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS
            idx_catalogo_esercitazioni_tag_esercitazione
        ON catalogo_esercitazioni_tag (
            esercitazione_id
        );

        CREATE INDEX IF NOT EXISTS
            idx_catalogo_esercitazioni_tag_tag
        ON catalogo_esercitazioni_tag (
            tag_id
        );

        CREATE TABLE IF NOT EXISTS attivita_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            stagione_id INTEGER NOT NULL,
            data_attivita TEXT NOT NULL,

            tipo_attivita TEXT NOT NULL,

            nome TEXT,
            descrizione TEXT,

            attivita_padre_id INTEGER,
            esercitazione_catalogo_id INTEGER,

            macro_tipologia_id INTEGER,
            obiettivo_id INTEGER,

            numero_ripetizione INTEGER,

            durata_minuti REAL,
            fase_stagione TEXT,

            categoria_squadra TEXT,

            file_origine TEXT,
            hash_file TEXT,

            data_importazione TEXT NOT NULL
                DEFAULT CURRENT_TIMESTAMP,

            valida INTEGER NOT NULL DEFAULT 1,

            note TEXT,

            FOREIGN KEY (
                stagione_id
            ) REFERENCES stagioni(id),

            FOREIGN KEY (
                attivita_padre_id
            ) REFERENCES attivita_performance(id),

            FOREIGN KEY (
                esercitazione_catalogo_id
            ) REFERENCES catalogo_esercitazioni(id),

            FOREIGN KEY (
                macro_tipologia_id
            ) REFERENCES macro_tipologie_esercitazioni(id),

            FOREIGN KEY (
                obiettivo_id
            ) REFERENCES obiettivi_attivita(id)
        );

        CREATE TABLE IF NOT EXISTS metriche_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            codice TEXT NOT NULL UNIQUE,
            nome TEXT NOT NULL,
            unita TEXT,

            categoria TEXT,
            descrizione TEXT,

            direzione_migliore TEXT
                DEFAULT 'ALTO',

            attiva INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS risultati_attivita_atleta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            attivita_id INTEGER NOT NULL,
            giocatore_id INTEGER NOT NULL,

            partecipazione_minuti REAL,
            percentuale_partecipazione REAL,

            valido INTEGER NOT NULL DEFAULT 1,
            note TEXT,

            UNIQUE (
                attivita_id,
                giocatore_id
            ),

            FOREIGN KEY (
                attivita_id
            ) REFERENCES attivita_performance(id)
                ON DELETE CASCADE,

            FOREIGN KEY (
                giocatore_id
            ) REFERENCES giocatori(id)
        );

        CREATE TABLE IF NOT EXISTS valori_metriche_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            risultato_attivita_id INTEGER NOT NULL,
            metrica_id INTEGER NOT NULL,

            valore REAL,
            valore_testuale TEXT,

            valido INTEGER NOT NULL DEFAULT 1,
            note TEXT,

            UNIQUE (
                risultato_attivita_id,
                metrica_id
            ),

            FOREIGN KEY (
                risultato_attivita_id
            ) REFERENCES risultati_attivita_atleta(id)
                ON DELETE CASCADE,

            FOREIGN KEY (
                metrica_id
            ) REFERENCES metriche_performance(id)
        );

        CREATE INDEX IF NOT EXISTS
            idx_attivita_performance_data
        ON attivita_performance (
            data_attivita
        );

        CREATE INDEX IF NOT EXISTS
            idx_attivita_performance_tipo
        ON attivita_performance (
            tipo_attivita
        );

        CREATE INDEX IF NOT EXISTS
            idx_attivita_performance_padre
        ON attivita_performance (
            attivita_padre_id
        );

        CREATE INDEX IF NOT EXISTS
            idx_risultati_attivita_giocatore
        ON risultati_attivita_atleta (
            giocatore_id
        );

        CREATE INDEX IF NOT EXISTS
            idx_valori_metriche_metrica
        ON valori_metriche_performance (
            metrica_id
        );
        """
    )

    macro_tipologie = [
        "Tecnica situazionale",
        "Gioco di posizione",
        "Fase di non possesso",
        "Sviluppi offensivi",
        "Gioco situazionale",
        "Calci da fermo",
        "Lavoro fisico",
    ]

    for nome in macro_tipologie:
        cursor.execute(
            """
            INSERT OR IGNORE INTO
                macro_tipologie_esercitazioni (
                    nome
                )
            VALUES (?)
            """,
            (nome,),
        )

    obiettivi = [
        "Aerobico",
        "Anaerobico",
        "Forza",
        "Velocità",
        "Potenza",
        "Tecnico",
        "Tattico",
        "Recupero",
        "Prevenzione",
        "Rientro in campo",
    ]

    for nome in obiettivi:
        cursor.execute(
            """
            INSERT OR IGNORE INTO
                obiettivi_attivita (
                    nome
                )
            VALUES (?)
            """,
            (nome,),
        )

        tag_iniziali = [
        "Possesso",
        "Non possesso",
        "Transizione offensiva",
        "Transizione difensiva",
        "Alta intensità",
        "Media intensità",
        "Bassa intensità",
        "Small sided game",
        "Large sided game",
        "Campo ridotto",
        "Campo intero",
        "Superiorità numerica",
        "Inferiorità numerica",
        "Parità numerica",
        "Jolly",
        "Pressing",
        "Finalizzazione",
        "Costruzione dal basso",
        "Prevenzione",
        "Recupero",
    ]

    for nome in tag_iniziali:
        cursor.execute(
            """
            INSERT OR IGNORE INTO tag_esercitazioni (
                nome
            )
            VALUES (?)
            """,
            (nome,),
        )

    metriche_base = [
        (
            "duration",
            "Durata",
            "min",
            "Volume",
        ),
        (
            "total_distance",
            "Distanza totale",
            "m",
            "Volume",
        ),
        (
            "distance_per_minute",
            "Metri al minuto",
            "m/min",
            "Intensità",
        ),
        (
            "hsr_distance",
            "Distanza alta intensità",
            "m",
            "Alta intensità",
        ),
        (
            "sprint_distance",
            "Distanza sprint",
            "m",
            "Velocità",
        ),
        (
            "sprint_count",
            "Numero sprint",
            "n",
            "Velocità",
        ),
        (
            "max_speed",
            "Velocità massima",
            "km/h",
            "Velocità",
        ),
        (
            "acceleration_count",
            "Accelerazioni",
            "n",
            "Accelerazioni",
        ),
        (
            "deceleration_count",
            "Decelerazioni",
            "n",
            "Decelerazioni",
        ),
        (
            "player_load",
            "Player Load",
            "AU",
            "Carico",
        ),
        (
            "metabolic_power",
            "Potenza metabolica",
            "W/kg",
            "Carico",
        ),
    ]

    for (
        codice,
        nome,
        unita,
        categoria,
    ) in metriche_base:
        cursor.execute(
            """
            INSERT OR IGNORE INTO
                metriche_performance (
                    codice,
                    nome,
                    unita,
                    categoria
                )
            VALUES (?, ?, ?, ?)
            """,
            (
                codice,
                nome,
                unita,
                categoria,
            ),
        )

    cursor.execute("PRAGMA table_info(attivita_performance)")
    colonne_attivita = {
        riga[1] for riga in cursor.fetchall()
    }

    if "numero_serie" not in colonne_attivita:
        cursor.execute(
            """
            ALTER TABLE attivita_performance
            ADD COLUMN numero_serie INTEGER
            """
        )

    if "numero_ripetizione" not in colonne_attivita:
        cursor.execute(
            """
            ALTER TABLE attivita_performance
            ADD COLUMN numero_ripetizione INTEGER
            """
        )

    conn.commit()

    conn.commit()
    conn.close()


def get_training_macro_types():
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT
            id,
            nome,
            attiva
        FROM macro_tipologie_esercitazioni
        WHERE attiva = 1
        ORDER BY nome
        """
    ).fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


def get_training_objectives():
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT
            id,
            nome,
            attivo
        FROM obiettivi_attivita
        WHERE attivo = 1
        ORDER BY nome
        """
    ).fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


def get_performance_metrics():
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT
            id,
            codice,
            nome,
            unita,
            categoria,
            direzione_migliore
        FROM metriche_performance
        WHERE attiva = 1
        ORDER BY categoria, nome
        """
    ).fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


# noqa: cache-bust
def get_sessions_data_status(stagione_id=None):
    """
    Restituisce le sedute con il conteggio di record GPS e Cardio già presenti.
    Se stagione_id è None, filtra automaticamente sulla stagione attiva.
    Se non c'è nessuna stagione attiva, restituisce tutte le sedute.
    """
    if stagione_id is None:
        stagione_id = get_active_season_id()

    conn = get_connection()
    conn.row_factory = sqlite3.Row

    if stagione_id is not None:
        rows = conn.execute("""
            SELECT
                s.id,
                s.data,
                s.tipo,
                s.md,
                s.avversario,
                COALESCE(g.n_gps, 0)    AS n_gps,
                COALESCE(c.n_cardio, 0) AS n_cardio
            FROM sedute s
            LEFT JOIN (
                SELECT seduta_id, COUNT(*) AS n_gps FROM gps GROUP BY seduta_id
            ) g ON g.seduta_id = s.id
            LEFT JOIN (
                SELECT seduta_id, COUNT(*) AS n_cardio FROM cardio GROUP BY seduta_id
            ) c ON c.seduta_id = s.id
            WHERE s.stagione_id = ?
            ORDER BY s.data DESC, s.id DESC
        """, (stagione_id,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT
                s.id,
                s.data,
                s.tipo,
                s.md,
                s.avversario,
                COALESCE(g.n_gps, 0)    AS n_gps,
                COALESCE(c.n_cardio, 0) AS n_cardio
            FROM sedute s
            LEFT JOIN (
                SELECT seduta_id, COUNT(*) AS n_gps FROM gps GROUP BY seduta_id
            ) g ON g.seduta_id = s.id
            LEFT JOIN (
                SELECT seduta_id, COUNT(*) AS n_cardio FROM cardio GROUP BY seduta_id
            ) c ON c.seduta_id = s.id
            ORDER BY s.data DESC, s.id DESC
        """).fetchall()

    conn.close()
    return [dict(r) for r in rows]


def ensure_cardio_table():
    """Migrazione: crea tabella cardio se non esiste (DB già inizializzati)."""
    conn = get_connection()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS cardio (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        seduta_id INTEGER NOT NULL,
        giocatore_id INTEGER NOT NULL,
        fc_media REAL, fc_media_pct REAL, fc_max REAL, fc_max_pct REAL,
        trimp REAL, trimp_min REAL, te_aerobico REAL, te_anaerobico REAL,
        epoc REAL, calorie REAL, vo2_medio REAL, vo2_picco REAL,
        hr_z_recupero REAL, hr_z1 REAL, hr_z2 REAL, hr_z3 REAL, hr_z4 REAL,
        hrr_30 REAL, hrr_60 REAL, hrr_120 REAL,
        valido INTEGER DEFAULT 1, escluso_motivo TEXT
    )
    """)
    conn.commit()
    # Migrazione colonne HRR su DB già esistenti
    for col in ["hrr_30", "hrr_60", "hrr_120"]:
        try:
            conn.execute(f"ALTER TABLE cardio ADD COLUMN {col} REAL")
            conn.commit()
        except Exception:
            pass  # colonna già presente
    # Vincolo unicità: un solo record cardio per atleta per seduta
    try:
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_cardio_unique
            ON cardio (seduta_id, giocatore_id)
        """)
        conn.commit()
    except Exception:
        pass
    conn.close()


def add_cardio(
    seduta_id, giocatore_id,
    fc_media=None, fc_media_pct=None, fc_max=None, fc_max_pct=None,
    trimp=None, trimp_min=None, te_aerobico=None, te_anaerobico=None,
    epoc=None, calorie=None, vo2_medio=None, vo2_picco=None,
    hr_z_recupero=None, hr_z1=None, hr_z2=None, hr_z3=None, hr_z4=None,
    hrr_30=None, hrr_60=None, hrr_120=None,
    valido=1, escluso_motivo=None,
):
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO cardio (
            seduta_id, giocatore_id,
            fc_media, fc_media_pct, fc_max, fc_max_pct,
            trimp, trimp_min, te_aerobico, te_anaerobico,
            epoc, calorie, vo2_medio, vo2_picco,
            hr_z_recupero, hr_z1, hr_z2, hr_z3, hr_z4,
            hrr_30, hrr_60, hrr_120,
            valido, escluso_motivo
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        seduta_id, giocatore_id,
        fc_media, fc_media_pct, fc_max, fc_max_pct,
        trimp, trimp_min, te_aerobico, te_anaerobico,
        epoc, calorie, vo2_medio, vo2_picco,
        hr_z_recupero, hr_z1, hr_z2, hr_z3, hr_z4,
        hrr_30, hrr_60, hrr_120,
        valido, escluso_motivo,
    ))
    conn.commit()
    conn.close()


def count_cardio_by_session(seduta_id):
    conn = get_connection()
    result = conn.execute(
        "SELECT COUNT(*) FROM cardio WHERE seduta_id = ?", (seduta_id,)
    ).fetchone()[0]
    conn.close()
    return result


def delete_cardio_by_session(seduta_id):
    conn = get_connection()
    conn.execute("DELETE FROM cardio WHERE seduta_id = ?", (seduta_id,))
    conn.commit()
    conn.close()


def get_gps_storico(
    giocatore_ids=None,
    seduta_ids=None,
    data_da=None,
    data_a=None,
):
    """
    Restituisce tutti i record GPS (+ cardio via LEFT JOIN) con data seduta e nome giocatore.
    Filtri opzionali: lista giocatore_ids, lista seduta_ids, range date.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    filtri = ["COALESCE(gps.valido, 1) = 1"]
    params = []

    if giocatore_ids:
        placeholders = ",".join(["?"] * len(giocatore_ids))
        filtri.append(f"gps.giocatore_id IN ({placeholders})")
        params.extend(giocatore_ids)

    if seduta_ids:
        placeholders = ",".join(["?"] * len(seduta_ids))
        filtri.append(f"gps.seduta_id IN ({placeholders})")
        params.extend(seduta_ids)

    if data_da:
        filtri.append("date(sedute.data) >= date(?)")
        params.append(str(data_da))

    if data_a:
        filtri.append("date(sedute.data) <= date(?)")
        params.append(str(data_a))

    where = " AND ".join(filtri)

    cursor.execute(f"""
        SELECT
            gps.id,
            gps.seduta_id,
            gps.giocatore_id,
            gps.durata,
            gps.distanza,
            gps.meters_min,
            gps.max_speed,
            gps.z2,
            gps.z3,
            gps.z4,
            gps.hsr,
            gps.vhsr,
            gps.speed_events,
            gps.bursts,
            gps.brakes,
            -- Cardio FirstBeat (NULL se non importato)
            c.fc_media,
            c.fc_media_pct,
            c.fc_max,
            c.fc_max_pct,
            c.trimp,
            c.trimp_min,
            c.te_aerobico,
            c.te_anaerobico,
            c.epoc,
            c.calorie,
            c.vo2_medio,
            c.vo2_picco,
            c.hr_z_recupero,
            c.hr_z1,
            c.hr_z2,
            c.hr_z3,
            c.hr_z4,
            c.hrr_30,
            c.hrr_60,
            c.hrr_120,
            sedute.data    AS data_seduta,
            sedute.tipo    AS tipo_seduta,
            sedute.md,
            giocatori.nome,
            giocatori.cognome
        FROM gps
        LEFT JOIN cardio c
            ON c.seduta_id = gps.seduta_id
           AND c.giocatore_id = gps.giocatore_id
        JOIN sedute    ON gps.seduta_id    = sedute.id
        JOIN giocatori ON gps.giocatore_id = giocatori.id
        WHERE {where}
        ORDER BY date(sedute.data), giocatori.cognome, giocatori.nome
    """, params)

    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_gps_mean_by_session():
    """Media squadra per seduta (giocatori validi) con dati cardio aggregati."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            sedute.id               AS seduta_id,
            sedute.data             AS data_seduta,
            sedute.tipo             AS tipo_seduta,
            sedute.md,
            COUNT(gps.id)           AS n_giocatori,
            ROUND(AVG(gps.durata),1)       AS durata,
            ROUND(AVG(gps.distanza),0)     AS distanza,
            ROUND(AVG(gps.max_speed),2)    AS max_speed,
            ROUND(AVG(gps.z2),0)           AS z2,
            ROUND(AVG(gps.z3),0)           AS z3,
            ROUND(AVG(gps.z4),0)           AS z4,
            ROUND(AVG(gps.speed_events),1) AS speed_events,
            ROUND(AVG(gps.bursts),1)       AS bursts,
            ROUND(AVG(gps.brakes),1)       AS brakes,
            ROUND(AVG(gps.meters_min),2)   AS meters_min,
            -- Cardio medie
            ROUND(AVG(c.fc_media),1)       AS fc_media,
            ROUND(AVG(c.fc_media_pct),1)   AS fc_media_pct,
            ROUND(AVG(c.fc_max),1)         AS fc_max,
            ROUND(AVG(c.trimp),1)          AS trimp,
            ROUND(AVG(c.trimp_min),3)      AS trimp_min,
            ROUND(AVG(c.te_aerobico),2)    AS te_aerobico,
            ROUND(AVG(c.te_anaerobico),2)  AS te_anaerobico,
            ROUND(AVG(c.epoc),1)           AS epoc,
            ROUND(AVG(c.calorie),0)        AS calorie,
            ROUND(AVG(c.vo2_medio),1)      AS vo2_medio,
            ROUND(AVG(c.vo2_picco),1)      AS vo2_picco,
            ROUND(AVG(c.hr_z_recupero),1)  AS hr_z_recupero,
            ROUND(AVG(c.hr_z1),1)          AS hr_z1,
            ROUND(AVG(c.hr_z2),1)          AS hr_z2,
            ROUND(AVG(c.hr_z3),1)          AS hr_z3,
            ROUND(AVG(c.hr_z4),1)          AS hr_z4,
            ROUND(AVG(c.hrr_30),1)         AS hrr_30,
            ROUND(AVG(c.hrr_60),1)         AS hrr_60,
            ROUND(AVG(c.hrr_120),1)        AS hrr_120
        FROM gps
        LEFT JOIN cardio c
            ON c.seduta_id = gps.seduta_id
           AND c.giocatore_id = gps.giocatore_id
        JOIN sedute ON gps.seduta_id = sedute.id
        WHERE COALESCE(gps.valido, 1) = 1
        GROUP BY sedute.id
        ORDER BY date(sedute.data)
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    create_database()
    init_training_report_tables()

    print("Database inizializzato correttamente.")