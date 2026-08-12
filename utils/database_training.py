import sqlite3

from utils.database import get_connection


# ==========================
# MACRO TIPOLOGIE
# ==========================

def get_macro_tipologie():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            nome,
            attiva
        FROM macro_tipologie_esercitazioni
        WHERE attiva = 1
        ORDER BY nome
        """
    )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


# ==========================
# OBIETTIVI
# ==========================

def get_obiettivi_attivita():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            nome,
            attivo
        FROM obiettivi_attivita
        WHERE attivo = 1
        ORDER BY nome
        """
    )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


# ==========================
# METRICHE PERFORMANCE
# ==========================

def get_metriche_performance():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            codice,
            nome,
            unita,
            categoria,
            descrizione,
            direzione_migliore,
            attiva
        FROM metriche_performance
        WHERE attiva = 1
        ORDER BY categoria, nome
        """
    )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_metrica_by_codice(codice):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            codice,
            nome,
            unita,
            categoria,
            descrizione,
            direzione_migliore,
            attiva
        FROM metriche_performance
        WHERE codice = ?
        LIMIT 1
        """,
        (codice,),
    )

    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


# ==========================
# CATALOGO ESERCITAZIONI
# ==========================

def get_catalogo_esercitazioni(
    solo_attive=True,
):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
        SELECT
            catalogo_esercitazioni.id,
            catalogo_esercitazioni.nome,
            catalogo_esercitazioni.macro_tipologia_id,
            catalogo_esercitazioni.obiettivo_principale_id,
            catalogo_esercitazioni.descrizione,
            catalogo_esercitazioni.attiva,

            macro_tipologie_esercitazioni.nome
                AS macro_tipologia,

            obiettivi_attivita.nome
                AS obiettivo_principale

        FROM catalogo_esercitazioni

        LEFT JOIN macro_tipologie_esercitazioni
            ON catalogo_esercitazioni.macro_tipologia_id
            = macro_tipologie_esercitazioni.id

        LEFT JOIN obiettivi_attivita
            ON catalogo_esercitazioni.obiettivo_principale_id
            = obiettivi_attivita.id
    """

    if solo_attive:
        query += """
            WHERE catalogo_esercitazioni.attiva = 1
        """

    query += """
        ORDER BY
            macro_tipologia,
            catalogo_esercitazioni.nome
    """

    cursor.execute(query)

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def add_catalogo_esercitazione(
    nome,
    macro_tipologia_id=None,
    obiettivo_principale_id=None,
    descrizione=None,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO catalogo_esercitazioni (
            nome,
            macro_tipologia_id,
            obiettivo_principale_id,
            descrizione
        )
        VALUES (?, ?, ?, ?)

        ON CONFLICT (
            nome,
            macro_tipologia_id,
            obiettivo_principale_id
        )
        DO UPDATE SET
            descrizione = excluded.descrizione,
            attiva = 1
        """,
        (
            nome,
            macro_tipologia_id,
            obiettivo_principale_id,
            descrizione,
        ),
    )

    esercitazione_id = cursor.lastrowid

    if esercitazione_id == 0:
        cursor.execute(
            """
            SELECT id
            FROM catalogo_esercitazioni
            WHERE nome = ?
              AND macro_tipologia_id IS ?
              AND obiettivo_principale_id IS ?
            LIMIT 1
            """,
            (
                nome,
                macro_tipologia_id,
                obiettivo_principale_id,
            ),
        )

        row = cursor.fetchone()

        esercitazione_id = (
            row[0]
            if row
            else None
        )

    conn.commit()
    conn.close()

    return esercitazione_id


# ==========================
# ATTIVITA PERFORMANCE
# ==========================

def add_attivita_performance(
    stagione_id,
    data_attivita,
    tipo_attivita,
    nome=None,
    descrizione=None,
    attivita_padre_id=None,
    esercitazione_catalogo_id=None,
    macro_tipologia_id=None,
    obiettivo_id=None,
    numero_ripetizione=None,
    durata_minuti=None,
    fase_stagione=None,
    categoria_squadra=None,
    file_origine=None,
    hash_file=None,
    valida=1,
    note=None,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO attivita_performance (
            stagione_id,
            data_attivita,
            tipo_attivita,
            nome,
            descrizione,
            attivita_padre_id,
            esercitazione_catalogo_id,
            macro_tipologia_id,
            obiettivo_id,
            numero_ripetizione,
            durata_minuti,
            fase_stagione,
            categoria_squadra,
            file_origine,
            hash_file,
            valida,
            note
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            stagione_id,
            data_attivita,
            tipo_attivita,
            nome,
            descrizione,
            attivita_padre_id,
            esercitazione_catalogo_id,
            macro_tipologia_id,
            obiettivo_id,
            numero_ripetizione,
            durata_minuti,
            fase_stagione,
            categoria_squadra,
            file_origine,
            hash_file,
            int(valida),
            note,
        ),
    )

    attivita_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return attivita_id


def get_attivita_performance(
    stagione_id=None,
    data_inizio=None,
    data_fine=None,
    tipo_attivita=None,
):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
        SELECT
            attivita_performance.*,

            catalogo_esercitazioni.nome
                AS esercitazione_catalogo,

            macro_tipologie_esercitazioni.nome
                AS macro_tipologia,

            obiettivi_attivita.nome
                AS obiettivo

        FROM attivita_performance

        LEFT JOIN catalogo_esercitazioni
            ON attivita_performance.esercitazione_catalogo_id
            = catalogo_esercitazioni.id

        LEFT JOIN macro_tipologie_esercitazioni
            ON attivita_performance.macro_tipologia_id
            = macro_tipologie_esercitazioni.id

        LEFT JOIN obiettivi_attivita
            ON attivita_performance.obiettivo_id
            = obiettivi_attivita.id

        WHERE attivita_performance.valida = 1
    """

    parametri = []

    if stagione_id is not None:
        query += """
            AND attivita_performance.stagione_id = ?
        """
        parametri.append(stagione_id)

    if data_inizio:
        query += """
            AND date(attivita_performance.data_attivita)
                >= date(?)
        """
        parametri.append(data_inizio)

    if data_fine:
        query += """
            AND date(attivita_performance.data_attivita)
                <= date(?)
        """
        parametri.append(data_fine)

    if tipo_attivita:
        query += """
            AND attivita_performance.tipo_attivita = ?
        """
        parametri.append(tipo_attivita)

    query += """
        ORDER BY
            date(attivita_performance.data_attivita) DESC,
            attivita_performance.id DESC
    """

    cursor.execute(
        query,
        tuple(parametri),
    )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


# ==========================
# RISULTATI ATLETA
# ==========================

def add_risultato_attivita_atleta(
    attivita_id,
    giocatore_id,
    partecipazione_minuti=None,
    percentuale_partecipazione=None,
    valido=1,
    note=None,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO risultati_attivita_atleta (
            attivita_id,
            giocatore_id,
            partecipazione_minuti,
            percentuale_partecipazione,
            valido,
            note
        )
        VALUES (?, ?, ?, ?, ?, ?)

        ON CONFLICT (
            attivita_id,
            giocatore_id
        )
        DO UPDATE SET
            partecipazione_minuti =
                excluded.partecipazione_minuti,
            percentuale_partecipazione =
                excluded.percentuale_partecipazione,
            valido = excluded.valido,
            note = excluded.note
        """,
        (
            attivita_id,
            giocatore_id,
            partecipazione_minuti,
            percentuale_partecipazione,
            int(valido),
            note,
        ),
    )

    cursor.execute(
        """
        SELECT id
        FROM risultati_attivita_atleta
        WHERE attivita_id = ?
          AND giocatore_id = ?
        LIMIT 1
        """,
        (
            attivita_id,
            giocatore_id,
        ),
    )

    row = cursor.fetchone()
    risultato_id = row[0] if row else None

    conn.commit()
    conn.close()

    return risultato_id


# ==========================
# VALORI METRICHE
# ==========================

def save_valore_metrica(
    risultato_attivita_id,
    metrica_id,
    valore=None,
    valore_testuale=None,
    valido=1,
    note=None,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO valori_metriche_performance (
            risultato_attivita_id,
            metrica_id,
            valore,
            valore_testuale,
            valido,
            note
        )
        VALUES (?, ?, ?, ?, ?, ?)

        ON CONFLICT (
            risultato_attivita_id,
            metrica_id
        )
        DO UPDATE SET
            valore = excluded.valore,
            valore_testuale = excluded.valore_testuale,
            valido = excluded.valido,
            note = excluded.note
        """,
        (
            risultato_attivita_id,
            metrica_id,
            valore,
            valore_testuale,
            int(valido),
            note,
        ),
    )


# ==========================
# TAG ESERCITAZIONI
# ==========================

def get_tag_esercitazioni(
    solo_attivi=True,
):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
        SELECT
            id,
            nome,
            descrizione,
            attivo
        FROM tag_esercitazioni
    """

    if solo_attivi:
        query += """
            WHERE attivo = 1
        """

    query += """
        ORDER BY nome
    """

    cursor.execute(query)

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def add_tag_esercitazione(
    nome,
    descrizione=None,
):
    nome = str(nome).strip()

    if not nome:
        raise ValueError(
            "Il nome del tag non può essere vuoto."
        )

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO tag_esercitazioni (
            nome,
            descrizione,
            attivo
        )
        VALUES (?, ?, 1)

        ON CONFLICT (nome)
        DO UPDATE SET
            descrizione = COALESCE(
                excluded.descrizione,
                tag_esercitazioni.descrizione
            ),
            attivo = 1
        """,
        (
            nome,
            descrizione,
        ),
    )

    cursor.execute(
        """
        SELECT id
        FROM tag_esercitazioni
        WHERE nome = ?
        LIMIT 1
        """,
        (nome,),
    )

    row = cursor.fetchone()
    tag_id = row[0] if row else None

    conn.commit()
    conn.close()

    return tag_id


def collega_tag_esercitazione(
    esercitazione_id,
    tag_id,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO
            catalogo_esercitazioni_tag (
                esercitazione_id,
                tag_id
            )
        VALUES (?, ?)
        """,
        (
            int(esercitazione_id),
            int(tag_id),
        ),
    )

    conn.commit()
    conn.close()


def scollega_tag_esercitazione(
    esercitazione_id,
    tag_id,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM catalogo_esercitazioni_tag
        WHERE esercitazione_id = ?
          AND tag_id = ?
        """,
        (
            int(esercitazione_id),
            int(tag_id),
        ),
    )

    conn.commit()
    conn.close()


def sostituisci_tag_esercitazione(
    esercitazione_id,
    tag_ids,
):
    tag_ids = {
        int(tag_id)
        for tag_id in tag_ids
        if tag_id is not None
    }

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            DELETE FROM catalogo_esercitazioni_tag
            WHERE esercitazione_id = ?
            """,
            (int(esercitazione_id),),
        )

        for tag_id in tag_ids:
            cursor.execute(
                """
                INSERT INTO catalogo_esercitazioni_tag (
                    esercitazione_id,
                    tag_id
                )
                VALUES (?, ?)
                """,
                (
                    int(esercitazione_id),
                    tag_id,
                ),
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_tag_by_esercitazione(
    esercitazione_id,
):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            tag_esercitazioni.id,
            tag_esercitazioni.nome,
            tag_esercitazioni.descrizione,
            tag_esercitazioni.attivo

        FROM catalogo_esercitazioni_tag

        JOIN tag_esercitazioni
            ON catalogo_esercitazioni_tag.tag_id
            = tag_esercitazioni.id

        WHERE catalogo_esercitazioni_tag.esercitazione_id = ?

        ORDER BY tag_esercitazioni.nome
        """,
        (int(esercitazione_id),),
    )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_catalogo_con_tag(
    solo_attive=True,
):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
        SELECT
            catalogo_esercitazioni.id,
            catalogo_esercitazioni.nome,
            catalogo_esercitazioni.descrizione,
            catalogo_esercitazioni.attiva,

            macro_tipologie_esercitazioni.nome
                AS macro_tipologia,

            obiettivi_attivita.nome
                AS obiettivo_principale,

            GROUP_CONCAT(
                tag_esercitazioni.nome,
                ', '
            ) AS tag

        FROM catalogo_esercitazioni

        LEFT JOIN macro_tipologie_esercitazioni
            ON catalogo_esercitazioni.macro_tipologia_id
            = macro_tipologie_esercitazioni.id

        LEFT JOIN obiettivi_attivita
            ON catalogo_esercitazioni.obiettivo_principale_id
            = obiettivi_attivita.id

        LEFT JOIN catalogo_esercitazioni_tag
            ON catalogo_esercitazioni.id
            = catalogo_esercitazioni_tag.esercitazione_id

        LEFT JOIN tag_esercitazioni
            ON catalogo_esercitazioni_tag.tag_id
            = tag_esercitazioni.id
    """

    parametri = []

    if solo_attive:
        query += """
            WHERE catalogo_esercitazioni.attiva = 1
        """

    query += """
        GROUP BY
            catalogo_esercitazioni.id,
            catalogo_esercitazioni.nome,
            catalogo_esercitazioni.descrizione,
            catalogo_esercitazioni.attiva,
            macro_tipologie_esercitazioni.nome,
            obiettivi_attivita.nome

        ORDER BY
            macro_tipologia,
            catalogo_esercitazioni.nome
    """

    cursor.execute(
        query,
        parametri,
    )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


# ==========================
# MODIFICA CATALOGO
# ==========================

def get_esercitazione_catalogo_by_id(esercitazione_id):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            nome,
            macro_tipologia_id,
            obiettivo_principale_id,
            descrizione,
            attiva
        FROM catalogo_esercitazioni
        WHERE id = ?
        LIMIT 1
        """,
        (int(esercitazione_id),),
    )

    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


def update_catalogo_esercitazione(
    esercitazione_id,
    nome,
    macro_tipologia_id=None,
    obiettivo_principale_id=None,
    descrizione=None,
):
    nome = str(nome).strip()

    if not nome:
        raise ValueError(
            "Il nome dell'esercitazione non può essere vuoto."
        )

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE catalogo_esercitazioni
            SET
                nome = ?,
                macro_tipologia_id = ?,
                obiettivo_principale_id = ?,
                descrizione = ?
            WHERE id = ?
            """,
            (
                nome,
                macro_tipologia_id,
                obiettivo_principale_id,
                descrizione,
                int(esercitazione_id),
            ),
        )

        if cursor.rowcount == 0:
            raise ValueError("Esercitazione non trovata.")

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def set_catalogo_esercitazione_attiva(
    esercitazione_id,
    attiva,
):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE catalogo_esercitazioni
            SET attiva = ?
            WHERE id = ?
            """,
            (
                int(bool(attiva)),
                int(esercitazione_id),
            ),
        )

        if cursor.rowcount == 0:
            raise ValueError("Esercitazione non trovata.")

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# ==========================
# STAGIONI
# ==========================

def get_stagioni_training():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM stagioni
        ORDER BY id DESC
        """
    )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


# ==========================
# FULL TRAINING
# ==========================

def add_full_training(
    stagione_id,
    data_attivita,
    nome,
    durata_minuti=None,
    fase_stagione=None,
    categoria_squadra=None,
    descrizione=None,
    note=None,
):
    return add_attivita_performance(
        stagione_id=stagione_id,
        data_attivita=data_attivita,
        tipo_attivita="FULL TRAINING",
        nome=nome,
        descrizione=descrizione,
        durata_minuti=durata_minuti,
        fase_stagione=fase_stagione,
        categoria_squadra=categoria_squadra,
        note=note,
    )


def get_full_training(
    stagione_id=None,
    data_inizio=None,
    data_fine=None,
):
    return get_attivita_performance(
        stagione_id=stagione_id,
        data_inizio=data_inizio,
        data_fine=data_fine,
        tipo_attivita="FULL TRAINING",
    )


# ==========================
# EXERCISE
# ==========================

def add_exercise_to_training(
    full_training_id,
    stagione_id,
    data_attivita,
    esercitazione_catalogo_id,
    nome,
    macro_tipologia_id=None,
    obiettivo_id=None,
    durata_minuti=None,
    descrizione=None,
    note=None,
):
    return add_attivita_performance(
        stagione_id=stagione_id,
        data_attivita=data_attivita,
        tipo_attivita="EXERCISE",
        nome=nome,
        descrizione=descrizione,
        attivita_padre_id=full_training_id,
        esercitazione_catalogo_id=(
            esercitazione_catalogo_id
        ),
        macro_tipologia_id=macro_tipologia_id,
        obiettivo_id=obiettivo_id,
        durata_minuti=durata_minuti,
        note=note,
    )


def get_exercises_by_training(full_training_id):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            attivita_performance.id,
            attivita_performance.nome,
            attivita_performance.descrizione,
            attivita_performance.durata_minuti,
            attivita_performance.data_attivita,
            attivita_performance.esercitazione_catalogo_id,

            catalogo_esercitazioni.nome
                AS esercitazione_catalogo,

            macro_tipologie_esercitazioni.nome
                AS macro_tipologia,

            obiettivi_attivita.nome
                AS obiettivo

        FROM attivita_performance

        LEFT JOIN catalogo_esercitazioni
            ON attivita_performance.esercitazione_catalogo_id
            = catalogo_esercitazioni.id

        LEFT JOIN macro_tipologie_esercitazioni
            ON attivita_performance.macro_tipologia_id
            = macro_tipologie_esercitazioni.id

        LEFT JOIN obiettivi_attivita
            ON attivita_performance.obiettivo_id
            = obiettivi_attivita.id

        WHERE attivita_performance.attivita_padre_id = ?
          AND attivita_performance.tipo_attivita = 'EXERCISE'
          AND attivita_performance.valida = 1

        ORDER BY attivita_performance.id
        """,
        (int(full_training_id),),
    )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]

# ==========================
# MODIFICA / ELIMINA EXERCISE
# ==========================

def get_exercise_by_id(exercise_id):
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            stagione_id,
            data_attivita,
            tipo_attivita,
            nome,
            descrizione,
            attivita_padre_id,
            esercitazione_catalogo_id,
            macro_tipologia_id,
            obiettivo_id,
            durata_minuti,
            note,
            valida
        FROM attivita_performance
        WHERE id = ?
          AND tipo_attivita = 'EXERCISE'
        LIMIT 1
        """,
        (int(exercise_id),),
    )

    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


def update_exercise_seduta(
    exercise_id,
    nome,
    esercitazione_catalogo_id=None,
    macro_tipologia_id=None,
    obiettivo_id=None,
    durata_minuti=None,
    descrizione=None,
    note=None,
):
    nome = str(nome).strip()

    if not nome:
        raise ValueError(
            "Il nome dell'esercitazione non può essere vuoto."
        )

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE attivita_performance
            SET
                nome = ?,
                esercitazione_catalogo_id = ?,
                macro_tipologia_id = ?,
                obiettivo_id = ?,
                durata_minuti = ?,
                descrizione = ?,
                note = ?
            WHERE id = ?
              AND tipo_attivita = 'EXERCISE'
            """,
            (
                nome,
                esercitazione_catalogo_id,
                macro_tipologia_id,
                obiettivo_id,
                durata_minuti,
                descrizione,
                note,
                int(exercise_id),
            ),
        )

        if cursor.rowcount == 0:
            raise ValueError(
                "Esercitazione della seduta non trovata."
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def elimina_exercise_seduta(exercise_id):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE attivita_performance
            SET valida = 0
            WHERE id = ?
              AND tipo_attivita = 'EXERCISE'
            """,
            (int(exercise_id),),
        )

        if cursor.rowcount == 0:
            raise ValueError(
                "Esercitazione della seduta non trovata."
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# ==========================
# PARSER NOTE GPEXE
# ==========================

def interpreta_nota_gpexe(nota):
    """
    Interpreta le note numeriche esportate da GPExe.

    Esempi:
    1  -> serie non specificata, ripetizione 1
    2  -> serie non specificata, ripetizione 2
    11 -> serie 1, ripetizione 1
    12 -> serie 1, ripetizione 2
    21 -> serie 2, ripetizione 1
    33 -> serie 3, ripetizione 3
    """

    risultato_vuoto = {
        "valida": False,
        "numero_serie": None,
        "numero_ripetizione": None,
        "codice_originale": None,
        "errore": None,
    }

    if nota is None:
        risultato_vuoto["errore"] = "Nota assente."
        return risultato_vuoto

    testo_originale = str(nota).strip()

    if not testo_originale:
        risultato_vuoto["errore"] = "Nota vuota."
        return risultato_vuoto

    testo = testo_originale.replace(",", ".")

    # Gestisce valori letti da Excel come 11.0
    try:
        valore_numerico = float(testo)

        if not valore_numerico.is_integer():
            risultato_vuoto["codice_originale"] = testo_originale
            risultato_vuoto["errore"] = (
                "La nota deve contenere un numero intero."
            )
            return risultato_vuoto

        numero = int(valore_numerico)

    except ValueError:
        risultato_vuoto["codice_originale"] = testo_originale
        risultato_vuoto["errore"] = (
            "La nota non contiene un codice numerico valido."
        )
        return risultato_vuoto

    if numero <= 0:
        risultato_vuoto["codice_originale"] = testo_originale
        risultato_vuoto["errore"] = (
            "Il codice deve essere maggiore di zero."
        )
        return risultato_vuoto

    # Codici a una cifra: 1, 2, 3...
    if numero < 10:
        return {
            "valida": True,
            "numero_serie": None,
            "numero_ripetizione": numero,
            "codice_originale": testo_originale,
            "errore": None,
        }

    # Codici a due cifre: 11, 12, 21, 22, 33...
    if numero < 100:
        numero_serie = numero // 10
        numero_ripetizione = numero % 10

        if numero_ripetizione == 0:
            return {
                "valida": False,
                "numero_serie": numero_serie,
                "numero_ripetizione": None,
                "codice_originale": testo_originale,
                "errore": (
                    "La seconda cifra deve indicare "
                    "una ripetizione da 1 a 9."
                ),
            }

        return {
            "valida": True,
            "numero_serie": numero_serie,
            "numero_ripetizione": numero_ripetizione,
            "codice_originale": testo_originale,
            "errore": None,
        }

    return {
        "valida": False,
        "numero_serie": None,
        "numero_ripetizione": None,
        "codice_originale": testo_originale,
        "errore": (
            "Per ora sono supportati codici da 1 a 99."
        ),
    }

    conn.commit()
    conn.close()