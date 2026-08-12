import json
import re
from datetime import datetime
from typing import Any


CAMPI_OXYPEAK = {
    "vo2": {
        "tipo_test": "VO2max relativo",
        "unita": "ml/kg/min",
    },
    "vam": {
        "tipo_test": "Velocità massima CPET",
        "unita": "km/h",
    },
    "fc_vam": {
        "tipo_test": "FC massima CPET",
        "unita": "bpm",
    },
    "at": {
        "tipo_test": "Velocità soglia anaerobica",
        "unita": "km/h",
    },
    "fc_at": {
        "tipo_test": "FC soglia anaerobica",
        "unita": "bpm",
    },
    "vo2_at": {
        "tipo_test": "VO2 alla soglia",
        "unita": "ml/kg/min",
    },
    "brrl_l": {
        "tipo_test": "Riserva respiratoria",
        "unita": "L/min",
    },
    "ve": {
        "tipo_test": "Ventilazione massima",
        "unita": "L/min",
    },
    "qr": {
        "tipo_test": "RER massimo",
        "unita": "indice",
    },
    "fev1_l": {
        "tipo_test": "FEV1",
        "unita": "L",
    },
    "fev1_pct": {
        "tipo_test": "FEV1 percentuale",
        "unita": "%",
    },
}


def leggi_file_html(file_bytes: bytes) -> str:
    """
    Converte il file caricato da Streamlit in testo.
    Prova prima UTF-8 e poi altri encoding comuni.
    """

    encoding_da_provare = [
        "utf-8",
        "utf-8-sig",
        "latin-1",
        "cp1252",
    ]

    for encoding in encoding_da_provare:
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue

    return file_bytes.decode(
        "utf-8",
        errors="replace",
    )


def normalizza_nome_atleta(nome: str) -> str:
    """
    Pulisce il nome estratto dal report.
    """

    nome = str(nome or "").strip()

    nome = re.sub(
        r"\s+",
        " ",
        nome,
    )

    return nome.upper()


def converti_numero(valore: Any):
    """
    Converte numeri scritti con punto o virgola.
    Restituisce None quando il valore non è disponibile.
    """

    if valore is None:
        return None

    if isinstance(
        valore,
        (int, float),
    ):
        return float(valore)

    testo = str(valore).strip()

    if testo.lower() in {
        "",
        "null",
        "none",
        "nan",
        "n/d",
        "nd",
        "-",
    }:
        return None

    testo = testo.replace(",", ".")

    try:
        return float(testo)
    except ValueError:
        return None


def estrai_blocco_array(
    testo: str,
    posizione_iniziale: int,
):
    """
    Estrae un array JavaScript completo contando
    parentesi quadre aperte e chiuse.
    """

    inizio_array = testo.find(
        "[",
        posizione_iniziale,
    )

    if inizio_array == -1:
        return None

    profondita = 0
    dentro_stringa = False
    carattere_stringa = None
    escape = False

    for indice in range(
        inizio_array,
        len(testo),
    ):
        carattere = testo[indice]

        if escape:
            escape = False
            continue

        if carattere == "\\":
            escape = True
            continue

        if dentro_stringa:
            if carattere == carattere_stringa:
                dentro_stringa = False
                carattere_stringa = None

            continue

        if carattere in {'"', "'"}:
            dentro_stringa = True
            carattere_stringa = carattere
            continue

        if carattere == "[":
            profondita += 1

        elif carattere == "]":
            profondita -= 1

            if profondita == 0:
                return testo[
                    inizio_array:indice + 1
                ]

    return None


def separa_oggetti_js(testo_array: str):
    """
    Divide un array JavaScript in singoli oggetti,
    senza eseguire JavaScript.
    """

    oggetti = []

    profondita = 0
    dentro_stringa = False
    carattere_stringa = None
    escape = False
    inizio_oggetto = None

    for indice, carattere in enumerate(
        testo_array
    ):
        if escape:
            escape = False
            continue

        if carattere == "\\":
            escape = True
            continue

        if dentro_stringa:
            if carattere == carattere_stringa:
                dentro_stringa = False
                carattere_stringa = None

            continue

        if carattere in {'"', "'"}:
            dentro_stringa = True
            carattere_stringa = carattere
            continue

        if carattere == "{":
            if profondita == 0:
                inizio_oggetto = indice

            profondita += 1

        elif carattere == "}":
            profondita -= 1

            if (
                profondita == 0
                and inizio_oggetto is not None
            ):
                oggetti.append(
                    testo_array[
                        inizio_oggetto:indice + 1
                    ]
                )

                inizio_oggetto = None

    return oggetti


def estrai_valore_stringa(
    oggetto: str,
    chiave: str,
):
    """
    Estrae una proprietà testuale da un oggetto JavaScript.
    """

    pattern = (
        rf'(?:^|[,{{])\s*'
        rf'{re.escape(chiave)}\s*:\s*'
        rf'(["\'])(.*?)\1'
    )

    corrispondenza = re.search(
        pattern,
        oggetto,
        flags=re.DOTALL,
    )

    if not corrispondenza:
        return None

    valore = corrispondenza.group(2)

    valore = valore.replace(
        r"\"",
        '"',
    )

    valore = valore.replace(
        r"\'",
        "'",
    )

    return valore.strip()


def estrai_valore_numerico(
    oggetto: str,
    chiave: str,
):
    """
    Estrae una proprietà numerica o null
    da un oggetto JavaScript.
    """

    pattern = (
        rf'(?:^|[,{{])\s*'
        rf'{re.escape(chiave)}\s*:\s*'
        rf'(-?\d+(?:\.\d+)?|null)'
    )

    corrispondenza = re.search(
        pattern,
        oggetto,
    )

    if not corrispondenza:
        return None

    return converti_numero(
        corrispondenza.group(1)
    )


def estrai_sessioni_oxypeak(
    html: str,
):
    """
    Cerca il blocco JavaScript:

        let TC = [...]

    e restituisce tutte le sessioni trovate.
    """

    marker = re.search(
        r"\blet\s+TC\s*=",
        html,
    )

    if not marker:
        marker = re.search(
            r"\bconst\s+TC\s*=",
            html,
        )

    if not marker:
        raise ValueError(
            "Il file non contiene il blocco "
            "dati OXYPEAK 'TC'."
        )

    blocco_tc = estrai_blocco_array(
        html,
        marker.end(),
    )

    if not blocco_tc:
        raise ValueError(
            "Il blocco delle sessioni OXYPEAK "
            "non è stato letto correttamente."
        )

    sessioni_grezze = separa_oggetti_js(
        blocco_tc
    )

    sessioni = []

    for sessione_grezza in sessioni_grezze:
        data_test = estrai_valore_stringa(
            sessione_grezza,
            "date",
        )

        posizione_atleti = re.search(
            r"\bathletes\s*:",
            sessione_grezza,
        )

        if not posizione_atleti:
            continue

        blocco_atleti = estrai_blocco_array(
            sessione_grezza,
            posizione_atleti.end(),
        )

        if not blocco_atleti:
            continue

        atleti_grezzi = separa_oggetti_js(
            blocco_atleti
        )

        atleti = []

        for atleta_grezzo in atleti_grezzi:
            nome = estrai_valore_stringa(
                atleta_grezzo,
                "name",
            )

            if not nome:
                continue

            atleta = {
                "nome_report": normalizza_nome_atleta(
                    nome
                ),
            }

            for chiave in CAMPI_OXYPEAK:
                atleta[chiave] = (
                    estrai_valore_numerico(
                        atleta_grezzo,
                        chiave,
                    )
                )

            atleti.append(atleta)

        if atleti:
            sessioni.append(
                {
                    "data_test": data_test,
                    "atleti": atleti,
                }
            )

    if not sessioni:
        raise ValueError(
            "Non sono state trovate sessioni "
            "OXYPEAK con dati degli atleti."
        )

    return sessioni


def data_valida(data_test: str) -> bool:
    try:
        datetime.strptime(
            str(data_test),
            "%Y-%m-%d",
        )

        return True

    except (
        TypeError,
        ValueError,
    ):
        return False


def crea_risultati_atleta(
    atleta: dict,
):
    """
    Trasforma i campi tecnici OXYPEAK
    nei test utilizzati dal database.
    """

    risultati = []

    for chiave, configurazione in (
        CAMPI_OXYPEAK.items()
    ):
        valore = atleta.get(chiave)

        if valore is None:
            continue

        risultati.append(
            {
                "codice_originale": chiave,
                "tipo_test": configurazione[
                    "tipo_test"
                ],
                "valore": valore,
                "unita": configurazione[
                    "unita"
                ],
                "lato": "BILATERALE",
                "tentativo": 1,
                "valido": 1,
            }
        )

    return risultati


def parse_oxypeak_html(
    file_bytes: bytes,
    nome_file: str = "",
):
    """
    Funzione principale richiamata da Streamlit.

    Restituisce tutte le sessioni presenti nel file,
    compresi eventuali test storici.
    """

    html = leggi_file_html(
        file_bytes
    )

    testo_controllo = html.upper()

    if (
        "OXYPEAK" not in testo_controllo
        and "FC_VAM" not in testo_controllo
        and "VO2_AT" not in testo_controllo
    ):
        raise ValueError(
            "Il file non sembra essere "
            "un report OXYPEAK compatibile."
        )

    sessioni_estratte = (
        estrai_sessioni_oxypeak(html)
    )

    sessioni_finali = []
    avvisi_generali = []

    for sessione in sessioni_estratte:
        data_test = sessione.get(
            "data_test"
        )

        avvisi_sessione = []

        if not data_valida(data_test):
            avvisi_sessione.append(
                "Data del test mancante "
                "o non riconosciuta."
            )

        atleti_finali = []

        for atleta in sessione["atleti"]:
            risultati = crea_risultati_atleta(
                atleta
            )

            if not risultati:
                continue

            avvisi_atleta = []

            if atleta.get("vo2") is not None:
                if not 20 <= atleta["vo2"] <= 90:
                    avvisi_atleta.append(
                        "VO2max relativo fuori "
                        "dall'intervallo atteso."
                    )

            if atleta.get("vam") is not None:
                if not 8 <= atleta["vam"] <= 30:
                    avvisi_atleta.append(
                        "VAM fuori "
                        "dall'intervallo atteso."
                    )

            if atleta.get("fc_vam") is not None:
                if not 80 <= atleta["fc_vam"] <= 240:
                    avvisi_atleta.append(
                        "FC massima fuori "
                        "dall'intervallo atteso."
                    )

            atleti_finali.append(
                {
                    "nome_report": atleta[
                        "nome_report"
                    ],
                    "risultati": risultati,
                    "avvisi": avvisi_atleta,
                }
            )

        if not atleti_finali:
            continue

        sessioni_finali.append(
            {
                "data_test": data_test,
                "categoria": "CPET",
                "descrizione": (
                    "Importazione automatica "
                    "report OXYPEAK"
                ),
                "atleti": atleti_finali,
                "avvisi": avvisi_sessione,
            }
        )

    if not sessioni_finali:
        raise ValueError(
            "Il report è stato riconosciuto, "
            "ma non contiene risultati importabili."
        )

    date_disponibili = [
        sessione["data_test"]
        for sessione in sessioni_finali
        if sessione.get("data_test")
    ]

    return {
        "formato": "OXYPEAK_HTML",
        "nome_file": nome_file,
        "numero_sessioni": len(
            sessioni_finali
        ),
        "date_disponibili": (
            date_disponibili
        ),
        "sessioni": sessioni_finali,
        "avvisi": avvisi_generali,
    }


def risultato_in_json(
    risultato: dict,
):
    """
    Funzione utile per testare il parser
    dal terminale.
    """

    return json.dumps(
        risultato,
        ensure_ascii=False,
        indent=2,
    )