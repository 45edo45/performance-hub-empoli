from datetime import datetime
import re

from bs4 import BeautifulSoup


def _numero(valore):
    if valore is None:
        return None

    testo = str(valore).strip().replace(",", ".")

    match = re.search(
        r"-?\d+(?:\.\d+)?",
        testo,
    )

    if not match:
        return None

    return float(match.group())


def _normalizza_data(data_testo):
    if not data_testo:
        return None

    for formato in (
        "%d/%m/%y",
        "%d/%m/%Y",
    ):
        try:
            return datetime.strptime(
                data_testo.strip(),
                formato,
            ).date().isoformat()
        except ValueError:
            continue

    return None


def _estrai_percentile(testo):
    if not testo:
        return None

    match = re.search(
        r"(\d+)\s*°",
        testo,
    )

    if not match:
        return None

    return int(match.group(1))


def _estrai_valori_cella(testo):
    if not testo:
        return []

    testo = " ".join(
        str(testo).strip().split()
    )

    if testo in {"—", "-", "--"}:
        return []

    # Estrae tutti i blocchi numerici:
    # 153.75 149.02 kg
    # 191/179 181/179 cm
    # —/263 N
    blocchi = re.findall(
        r"(?:—|-|\d+(?:[.,]\d+)?)"
        r"(?:\s*/\s*(?:—|-|\d+(?:[.,]\d+)?))?",
        testo,
    )

    blocchi_validi = []

    for blocco in blocchi:
        blocco = blocco.strip()

        if blocco in {"", "-", "—"}:
            continue

        # Evita di interpretare la freccia o altri simboli.
        if not re.search(
            r"\d",
            blocco,
        ):
            continue

        blocchi_validi.append(
            blocco
        )

    if not blocchi_validi:
        return []

    # Nelle celle comparative:
    # "153.75 149.02 kg" -> prende 149.02
    # "191/179 181/179 cm" -> prende 181/179
    #
    # Nelle celle senza confronto:
    # "329/306 N" -> prende 329/306
    blocco_corrente = blocchi_validi[-1]

    parti = re.split(
        r"\s*/\s*",
        blocco_corrente,
    )

    valori = []

    for parte in parti:
        parte = parte.strip()

        if parte in {
            "",
            "-",
            "—",
            "--",
        }:
            valori.append(None)
            continue

        valori.append(
            _numero(parte)
        )

    return valori

def _aggiungi_risultato(
    risultati,
    nome_test,
    valore,
    lato="BILATERALE",
    percentile=None,
    unita=None,
):
    if valore is None:
        return

    risultati.append(
        {
            "nome_test": nome_test,
            "valore": valore,
            "lato": lato,
            "percentile": percentile,
            "unita": unita,
        }
    )


def _normalizza_nome_test(nome_originale):
    nome = " ".join(
        nome_originale.lower().split()
    )

    mappa = {
        "1 rm": (
            "Squat 1RM",
            "kg",
        ),
        "1 rm / peso": (
            "Squat 1RM / peso",
            "xKg",
        ),
        "nordic dx/sx": (
            "Nordic Hamstring",
            "N",
        ),
        "squeeze sfigmomanometro": (
            "Squeeze Test",
            "mmHg",
        ),
        "cmj altezza": (
            "CMJ",
            "cm",
        ),
        "drop jump altezza": (
            "Drop Jump",
            "cm",
        ),
        "single leg hop dx/sx": (
            "Single Hop",
            "cm",
        ),
        "single leg drop jump dx/sx": (
            "Single Drop Jump",
            "cm",
        ),
        "single leg cmj dx/sx": (
            "CMJ monopodalico",
            "cm",
        ),
        "single leg hop somma": (
            "Single Hop Somma",
            "cm",
        ),
        "rsi drop jump": (
            "RSI Drop Jump",
            None,
        ),
        "rsi single leg drop jump dx/sx": (
            "Single RSI",
            None,
        ),
        "knee to wall dx/sx": (
            "Knee to Wall",
            "cm",
        ),
        "imtp": (
            "IMTP",
            "N",
        ),
        "deep squat": (
            "Deep Squat",
            None,
        ),
    }

    return mappa.get(nome)


def _estrai_risultati_sessione(blocco_sessione):
    risultati_per_chiave = {}

    for riga in blocco_sessione.select("tr"):
        celle = riga.find_all(
            "td",
            recursive=False,
        )

        if len(celle) < 3:
            continue

        nome_originale = celle[0].get_text(
            " ",
            strip=True,
        )

        configurazione = _normalizza_nome_test(
            nome_originale
        )

        if configurazione is None:
            continue

        nome_test, unita = configurazione

        valore_testo = celle[2].get_text(
            " ",
            strip=True,
        )

        percentile = None

        if len(celle) >= 4:
            percentile = _estrai_percentile(
                celle[3].get_text(
                    " ",
                    strip=True,
                )
            )

        valori = _estrai_valori_cella(
            valore_testo
        )

        if not valori:
            continue

        test_dx_sx = {
            "Nordic Hamstring",
            "Single Hop",
            "Single Drop Jump",
            "CMJ monopodalico",
            "Single RSI",
            "Knee to Wall",
        }

        if nome_test in test_dx_sx:
            lati = [
                ("DX", valori[0] if len(valori) >= 1 else None),
                ("SX", valori[1] if len(valori) >= 2 else None),
            ]

            for lato, valore in lati:
                chiave = (
                    nome_test,
                    lato,
                )

                if valore is None:
                    risultati_per_chiave.pop(
                        chiave,
                        None,
                    )
                    continue

                risultati_per_chiave[chiave] = {
                    "nome_test": nome_test,
                    "valore": valore,
                    "lato": lato,
                    "percentile": percentile,
                    "unita": unita,
                }

        else:
            valore = valori[0]

            chiave = (
                nome_test,
                "BILATERALE",
            )

            if valore is None:
                risultati_per_chiave.pop(
                    chiave,
                    None,
                )
                continue

            risultati_per_chiave[chiave] = {
                "nome_test": nome_test,
                "valore": valore,
                "lato": "BILATERALE",
                "percentile": percentile,
                "unita": unita,
            }

    return list(
        risultati_per_chiave.values()
    )


def _estrai_nome_atleta(blocco_sessione):
    intestazione = blocco_sessione.find("h1")

    if intestazione is None:
        return None

    return " ".join(
        intestazione.get_text(
            " ",
            strip=True,
        ).split()
    ).upper()


def _estrai_dati_corpo(blocco_sessione):
    testo = blocco_sessione.get_text(
        " ",
        strip=True,
    )

    altezza = None
    peso = None

    match_altezza = re.search(
        r"\b(\d{3}(?:[.,]\d+)?)\s*cm\b",
        testo,
        flags=re.IGNORECASE,
    )

    if match_altezza:
        altezza = _numero(
            match_altezza.group(1)
        )

    match_peso = re.search(
        r"\b(\d{2,3}(?:[.,]\d+)?)\s*kg\b",
        testo,
        flags=re.IGNORECASE,
    )

    if match_peso:
        peso = _numero(
            match_peso.group(1)
        )

    return peso, altezza


def parse_neuromuscolare_html(html):
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    sessioni = []

    for blocco in soup.select(
        "[data-session-date]"
    ):
        data_originale = blocco.get(
            "data-session-date"
        )

        atleta = _estrai_nome_atleta(
            blocco
        )

        if not atleta:
            continue

        peso, altezza = _estrai_dati_corpo(
            blocco
        )

        risultati = _estrai_risultati_sessione(
            blocco
        )

        radice_atleta = blocco.select_one(
            "[data-athlete-id]"
        )

        atleta_report_id = None

        if radice_atleta is not None:
            atleta_report_id = (
                radice_atleta.get(
                    "data-athlete-id"
                )
            )

        sessioni.append(
            {
                "tipo_report": "NEUROMUSCOLARE",
                "data": _normalizza_data(
                    data_originale
                ),
                "data_originale": data_originale,
                "atleta": atleta,
                "atleta_report_id": atleta_report_id,
                "peso_kg": peso,
                "altezza_cm": altezza,
                "risultati": risultati,
            }
        )

    return {
        "tipo_report": "NEUROMUSCOLARE",
        "sessioni": sessioni,
        "numero_sessioni": len(sessioni),
        "numero_risultati": sum(
            len(sessione["risultati"])
            for sessione in sessioni
        ),
    }