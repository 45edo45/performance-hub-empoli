import streamlit as st
import pandas as pd


from utils.report_parsers import (
    parse_oxypeak_html,
    parse_neuromuscolare_html,
)

from utils.database import (
    get_seasons,
    get_players_by_season,
    get_test_types,
    add_test_type,
    add_test_session,
    get_test_sessions,
    save_test_result,
    get_player_test_history,
    update_test_type,
    delete_test_type,
    update_test_session,
    delete_test_session,
    get_test_results_by_session,
    update_test_result,
    delete_test_result,
    save_body_data,
    get_body_data_by_season,
    update_body_data,
    delete_body_data,
    get_latest_body_weight,
    get_player_cpet_profile,
    find_test_session_duplicate,
)


import re
import unicodedata
from difflib import SequenceMatcher


def normalizza_nome_confronto(testo):
    testo = str(testo or "").strip().upper()

    testo = unicodedata.normalize(
        "NFD",
        testo,
    )

    testo = "".join(
        carattere
        for carattere in testo
        if unicodedata.category(carattere) != "Mn"
    )

    testo = re.sub(
        r"[^A-Z0-9 ]",
        " ",
        testo,
    )

    testo = re.sub(
        r"\s+",
        " ",
        testo,
    ).strip()

    return testo


def calcola_associazione_atleta(
    nome_report,
    giocatori,
):
    nome_normalizzato = normalizza_nome_confronto(
        nome_report
    )

    migliore_id = None
    migliore_punteggio = 0.0

    for giocatore in giocatori:
        nome = giocatore.get("nome", "")
        cognome = giocatore.get("cognome", "")

        forma_nome_cognome = normalizza_nome_confronto(
            f"{nome} {cognome}"
        )

        forma_cognome_nome = normalizza_nome_confronto(
            f"{cognome} {nome}"
        )

        punteggio_1 = SequenceMatcher(
            None,
            nome_normalizzato,
            forma_nome_cognome,
        ).ratio()

        punteggio_2 = SequenceMatcher(
            None,
            nome_normalizzato,
            forma_cognome_nome,
        ).ratio()

        punteggio = max(
            punteggio_1,
            punteggio_2,
        )

        if punteggio > migliore_punteggio:
            migliore_punteggio = punteggio
            migliore_id = int(
                giocatore["id"]
            )

    return migliore_id, migliore_punteggio


def normalizza_nome_test_importazione(nome_test):
    nome_normalizzato = normalizza_nome_confronto(
        nome_test
    )

    mappa_test = {
        "SQUAT 1RM": "Squat 1 RM",
        "SQUAT 1 RM": "Squat 1 RM",

        "SQUAT 1RM PESO": None,
        "SQUAT 1 RM PESO": None,

        "NORDIC HAMSTRING": "Nordic hamstring",

        "SQUEEZE TEST": "Squeeze adduttori",
        "SQUEEZE SFIGMOMANOMETRO": "Squeeze adduttori",

        "CMJ": "CMJ altezza",
        "CMJ ALTEZZA": "CMJ altezza",

        "DROP JUMP": "Drop jump altezza",
        "DROP JUMP ALTEZZA": "Drop jump altezza",

        "SINGLE HOP": "Single leg hop",
        "SINGLE LEG HOP": "Single leg hop",

        "SINGLE DROP JUMP": "Single leg drop jump",
        "SINGLE LEG DROP JUMP": "Single leg drop jump",

        "CMJ MONOPODALICO": "Single leg CMJ",
        "SINGLE LEG CMJ": "Single leg CMJ",

        "RSI DROP JUMP": "RSI drop jump",

        "SINGLE RSI": "RSI single leg drop jump",
        "RSI SINGLE LEG DROP JUMP": (
            "RSI single leg drop jump"
        ),

        "SINGLE HOP SOMMA": None,
        "KNEE TO WALL": None,
        "IMTP": None,
        "DEEP SQUAT": None,
    }

    return mappa_test.get(
        nome_normalizzato,
        nome_test,
    )

def converti_neuromuscolare_in_formato_importazione(
    risultato_parser,
):
    sessioni_per_data = {}

    for sessione_atleta in risultato_parser.get(
        "sessioni",
        [],
    ):
        data_test = sessione_atleta.get("data")

        if not data_test:
            continue

        if data_test not in sessioni_per_data:
            sessioni_per_data[data_test] = {
                "data_test": data_test,
                "categoria": "Valutazione completa",
                "descrizione": (
                    "Importazione automatica "
                    "report neuromuscolare"
                ),
                "atleti": [],
            }

        risultati_convertiti = []

        for risultato in sessione_atleta.get(
            "risultati",
            [],
        ):
            st.write(
                "DEBUG RISULTATO:",
                risultato,
            )

            nome_test_originale = (
                risultato.get("nome_test")
                or risultato.get("tipo_test")
                or risultato.get("test")
                or risultato.get("nome")
            )

            nome_catalogo = (
                normalizza_nome_test_importazione(
                    nome_test_originale
                )
            )

            if not nome_catalogo:
                continue

            valore = (
                risultato.get("valore")
                if risultato.get("valore") is not None
                else risultato.get("value")
            )

            if valore is None:
                continue

            try:
                valore_numerico = float(valore)
            except (TypeError, ValueError):
                continue

            risultati_convertiti.append(
                {
                    "tipo_test": nome_catalogo,
                    "valore": valore_numerico,
                    "unita": risultato.get("unita"),
                    "lato": risultato.get(
                        "lato",
                        "BILATERALE",
                    ),
                    "tentativo": risultato.get(
                        "tentativo",
                        1,
                    ),
                    "percentile": risultato.get(
                        "percentile"
                    ),
                    "valido": 1,
                }
            )

        sessioni_per_data[data_test][
            "atleti"
        ].append(
            {
                "nome_report": (
                    sessione_atleta.get("atleta")
                    or sessione_atleta.get("nome_atleta")
                    or sessione_atleta.get("nome")
                    or sessione_atleta.get("athlete")
                ),
                "risultati": risultati_convertiti,
                "peso_kg": sessione_atleta.get(
                    "peso_kg"
                ),
                "altezza_cm": sessione_atleta.get(
                    "altezza_cm"
                ),
                "avvisi": [],
            }
        )

    sessioni = sorted(
        sessioni_per_data.values(),
        key=lambda sessione: sessione[
            "data_test"
        ],
        reverse=True,
    )

    return {
        "formato": "NEUROMUSCOLARE",
        "numero_sessioni": len(sessioni),
        "sessioni": sessioni,
    }


def normalizza_nome_test_importazione(nome_test):
    if not nome_test:
        return None

    nome = str(nome_test).strip().lower()

    mappa_test = {
        "squat 1rm / peso": "Squat 1 RM",
        "squat 1 rm / peso": "Squat 1 RM",
        "squat 1rm": "Squat 1 RM",
        "squat 1 rm": "Squat 1 RM",
        "1rm squat": "Squat 1 RM",

        "nordic hamstring": "Nordic hamstring",
        "nordic": "Nordic hamstring",

        "squeeze test": "Squeeze adduttori",
        "squeeze adduttori": "Squeeze adduttori",
        "adductor squeeze": "Squeeze adduttori",
        "squeeze": "Squeeze adduttori",

        "cmj altezza": "CMJ altezza",
        "cmj": "CMJ altezza",
        "countermovement jump": "CMJ altezza",

        "drop jump altezza": "Drop jump altezza",
        "drop jump": "Drop jump altezza",

        "single leg cmj": "Single leg CMJ",
        "sl cmj": "Single leg CMJ",

        "single leg drop jump": "Single leg drop jump",
        "sl drop jump": "Single leg drop jump",

        "single leg hop": "Single leg hop",
        "sl hop": "Single leg hop",

        "rsi drop jump": "RSI drop jump",
        "rsi dj": "RSI drop jump",

        "rsi single leg drop jump": (
            "RSI single leg drop jump"
        ),
        "rsi sl drop jump": (
            "RSI single leg drop jump"
        ),
    }

    if nome in mappa_test:
        return mappa_test[nome]

    for chiave, nome_catalogo in mappa_test.items():
        if chiave in nome:
            return nome_catalogo

    return None


def riconosci_e_analizza_report(
    contenuto_file,
    nome_file,
):
    testo_html = contenuto_file.decode(
        "utf-8",
        errors="ignore",
    )

    risultato_neuromuscolare = (
        parse_neuromuscolare_html(
            testo_html
        )
    )

    if risultato_neuromuscolare.get(
        "numero_sessioni",
        0,
    ) > 0:
        dati_convertiti = (
            converti_neuromuscolare_in_formato_importazione(
                risultato_neuromuscolare
            )
        )

        st.write(
            "DEBUG CONVERSIONE COMPLETA:",
            dati_convertiti,
        )

        return dati_convertiti

    return parse_oxypeak_html(
        contenuto_file,
        nome_file,
    )


st.set_page_config(
    page_title="Test fisici",
    page_icon="🏋️",
)


st.set_page_config(
    page_title="Test fisici",
    page_icon="🏋️",
)


@st.cache_data(ttl=30)
def load_seasons():
    return get_seasons()


@st.cache_data(ttl=30)
def load_players_by_season(stagione_id):
    return get_players_by_season(stagione_id)


@st.cache_data(ttl=30)
def load_test_types():
    return get_test_types()


@st.cache_data(ttl=30)
def load_test_sessions(stagione_id):
    return get_test_sessions(stagione_id)


@st.cache_data(ttl=30)
def load_player_test_history(
    giocatore_id,
    tipo_test_id,
):
    return get_player_test_history(
        giocatore_id,
        tipo_test_id,
    )

st.title("🏋️ Test fisici")


@st.cache_data(ttl=30)
def load_test_results_by_session(sessione_test_id):
    return get_test_results_by_session(
        sessione_test_id
    )


@st.cache_data(ttl=30)
def load_body_data_by_season(stagione_id):
    return get_body_data_by_season(stagione_id)


@st.cache_data(ttl=30)
def load_latest_body_weight(
    giocatore_id,
    data_riferimento=None,
):
    return get_latest_body_weight(
        giocatore_id,
        data_riferimento,
    )


@st.cache_data(ttl=30)
def load_player_cpet_profile(
    giocatore_id,
    data_riferimento=None,
):
    return get_player_cpet_profile(
        giocatore_id,
        data_riferimento,
    )


# =========================
# SELEZIONE STAGIONE
# =========================

stagioni = load_seasons()

if not stagioni:
    st.warning("Non sono presenti stagioni nel database.")
    st.stop()


opzioni_stagioni = {
    stagione["nome"]: stagione["id"]
    for stagione in stagioni
}


stagione_attiva = next(
    (
        stagione["nome"]
        for stagione in stagioni
        if stagione["attiva"] == 1
    ),
    stagioni[0]["nome"],
)


nomi_stagioni = list(opzioni_stagioni.keys())

indice_stagione = nomi_stagioni.index(
    stagione_attiva
)


stagione_scelta = st.selectbox(
    "Stagione",
    nomi_stagioni,
    index=indice_stagione,
    key="stagione_test_fisici",
)


stagione_id = int(
    opzioni_stagioni[stagione_scelta]
)


# =========================
# CARICAMENTO DATI
# =========================

giocatori = load_players_by_season(
    stagione_id
)

tipi_test = load_test_types()

sessioni_test = load_test_sessions(
    stagione_id
)

dati_corporei = load_body_data_by_season(
    stagione_id
)

# =========================
# RIEPILOGO
# =========================

col1, col2 = st.columns(2)

with col1:
    st.metric(
        "Giocatori in rosa",
        len(giocatori),
    )

with col2:
    st.metric(
        "Tipologie di test",
        len(tipi_test),
    )


# =========================
# SCHEDE
# =========================

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
    [
        "📚 Tipologie test",
        "📅 Sessioni test",
        "📝 Inserimento risultati",
        "🛠️ Gestione risultati",
        "⚖️ Dati corporei",
        "📊 Benchmark",
        "Importa report",
    ]
)


with tab1:
    st.subheader("Tipologie di test")

    catalogo_iniziale = [
        {
            "nome": "Squat 1 RM",
            "categoria": "Forza",
            "unita_misura": "kg",
            "migliore_se_alto": 1,
            "descrizione": (
                "Carico massimo sollevato nello squat."
            ),
        },
        {
            "nome": "Nordic hamstring",
            "categoria": "Forza",
            "unita_misura": "N",
            "migliore_se_alto": 1,
            "descrizione": (
                "Forza espressa nel Nordic hamstring."
            ),
        },
        {
            "nome": "Squeeze adduttori",
            "categoria": "Forza",
            "unita_misura": "mmHg",
            "migliore_se_alto": 1,
            "descrizione": (
                "Forza degli adduttori rilevata "
                "tramite sfigmomanometro."
            ),
        },
        {
            "nome": "CMJ altezza",
            "categoria": "Potenza",
            "unita_misura": "cm",
            "migliore_se_alto": 1,
            "descrizione": (
                "Altezza raggiunta nel Countermovement Jump."
            ),
        },
        {
            "nome": "Drop jump altezza",
            "categoria": "Potenza",
            "unita_misura": "cm",
            "migliore_se_alto": 1,
            "descrizione": (
                "Altezza raggiunta nel Drop Jump."
            ),
        },
        {
            "nome": "Single leg hop",
            "categoria": "Potenza",
            "unita_misura": "cm",
            "migliore_se_alto": 1,
            "descrizione": (
                "Distanza raggiunta nel salto monopodalico. "
                "Da rilevare separatamente per DX e SX."
            ),
        },
        {
            "nome": "Single leg drop jump",
            "categoria": "Potenza",
            "unita_misura": "cm",
            "migliore_se_alto": 1,
            "descrizione": (
                "Altezza raggiunta nel Drop Jump monopodalico. "
                "Da rilevare separatamente per DX e SX."
            ),
        },
        {
            "nome": "Single leg CMJ",
            "categoria": "Potenza",
            "unita_misura": "cm",
            "migliore_se_alto": 1,
            "descrizione": (
                "Altezza raggiunta nel CMJ monopodalico. "
                "Da rilevare separatamente per DX e SX."
            ),
        },
        {
            "nome": "RSI drop jump",
            "categoria": "Reattività",
            "unita_misura": "indice",
            "migliore_se_alto": 1,
            "descrizione": (
                "Reactive Strength Index nel Drop Jump."
            ),
        },
        {
            "nome": "RSI single leg drop jump",
            "categoria": "Reattività",
            "unita_misura": "indice",
            "migliore_se_alto": 1,
            "descrizione": (
                "Reactive Strength Index monopodalico. "
                "Da rilevare separatamente per DX e SX."
            ),
        },
                {
            "nome": "VO2max relativo",
            "categoria": "Cardiovascolare",
            "unita_misura": "ml/kg/min",
            "migliore_se_alto": 1,
            "descrizione": (
                "Massimo consumo di ossigeno rapportato "
                "al peso corporeo."
            ),
        },
        {
            "nome": "VO2max assoluto",
            "categoria": "Cardiovascolare",
            "unita_misura": "ml/min",
            "migliore_se_alto": 1,
            "descrizione": (
                "Massimo consumo assoluto di ossigeno "
                "raggiunto nel test cardiopolmonare."
            ),
        },
        {
            "nome": "Velocità massima CPET",
            "categoria": "Cardiovascolare",
            "unita_misura": "km/h",
            "migliore_se_alto": 1,
            "descrizione": (
                "Massima velocità raggiunta durante "
                "il test cardiopolmonare incrementale."
            ),
        },
        {
            "nome": "FC massima CPET",
            "categoria": "Cardiovascolare",
            "unita_misura": "bpm",
            "migliore_se_alto": 1,
            "descrizione": (
                "Frequenza cardiaca massima raggiunta "
                "nel test cardiopolmonare."
            ),
        },
        {
            "nome": "Velocità soglia anaerobica",
            "categoria": "Cardiovascolare",
            "unita_misura": "km/h",
            "migliore_se_alto": 1,
            "descrizione": (
                "Velocità rilevata in corrispondenza "
                "della soglia anaerobica."
            ),
        },
        {
            "nome": "FC soglia anaerobica",
            "categoria": "Cardiovascolare",
            "unita_misura": "bpm",
            "migliore_se_alto": 1,
            "descrizione": (
                "Frequenza cardiaca rilevata in "
                "corrispondenza della soglia anaerobica."
            ),
        },
    ]

    
    st.markdown("### Gestione tipologie test")

    tipi_test_gestione = load_test_types()

    if not tipi_test_gestione:
        st.info("Non ci sono tipologie di test da gestire.")

    else:
        opzioni_test_gestione = {
            (
                f"{test['categoria']} | "
                f"{test['nome']} | "
                f"ID {test['id']}"
            ): test
            for test in tipi_test_gestione
        }

        test_gestione_scelto = st.selectbox(
            "Seleziona il test da modificare o eliminare",
            list(opzioni_test_gestione.keys()),
            key="test_da_gestire",
        )

        test_da_gestire = opzioni_test_gestione[
            test_gestione_scelto
        ]

        categorie_test = [
            "Forza",
            "Potenza",
            "Reattività",
            "Cardiovascolare",
            "Velocità",
            "Mobilità",
            "Composizione corporea",
            "Altro",
        ]

        categoria_attuale = test_da_gestire["categoria"]

        indice_categoria = (
            categorie_test.index(categoria_attuale)
            if categoria_attuale in categorie_test
            else len(categorie_test) - 1
        )

        criterio_attuale = (
            "Più alto è meglio"
            if int(test_da_gestire["migliore_se_alto"]) == 1
            else "Più basso è meglio"
        )

        with st.expander(
            "✏️ Modifica test selezionato",
            expanded=False,
        ):
            with st.form(
                f"form_modifica_test_{test_da_gestire['id']}"
            ):
                nome_modificato = st.text_input(
                    "Nome del test",
                    value=test_da_gestire["nome"],
                )

                categoria_modificata = st.selectbox(
                    "Categoria",
                    categorie_test,
                    index=indice_categoria,
                )

                unita_modificata = st.text_input(
                    "Unità di misura",
                    value=test_da_gestire["unita_misura"],
                )

                criterio_modificato = st.selectbox(
                    "Criterio prestativo",
                    [
                        "Più alto è meglio",
                        "Più basso è meglio",
                    ],
                    index=(
                        0
                        if criterio_attuale
                        == "Più alto è meglio"
                        else 1
                    ),
                )

                descrizione_modificata = st.text_area(
                    "Descrizione",
                    value=test_da_gestire.get(
                        "descrizione"
                    ) or "",
                )

                conferma_modifica_test = (
                    st.form_submit_button(
                        "Salva modifiche"
                    )
                )

            if conferma_modifica_test:
                nome_pulito = nome_modificato.strip()
                unita_pulita = unita_modificata.strip()

                if not nome_pulito:
                    st.error(
                        "Il nome del test è obbligatorio."
                    )

                elif not unita_pulita:
                    st.error(
                        "L'unità di misura è obbligatoria."
                    )

                else:
                    nomi_altri_test = {
                        test["nome"].strip().lower()
                        for test in tipi_test_gestione
                        if int(test["id"])
                        != int(test_da_gestire["id"])
                    }

                    if nome_pulito.lower() in nomi_altri_test:
                        st.error(
                            "Esiste già un'altra tipologia "
                            "con questo nome."
                        )

                    else:
                        update_test_type(
                            tipo_test_id=int(
                                test_da_gestire["id"]
                            ),
                            nome=nome_pulito,
                            categoria=categoria_modificata,
                            unita_misura=unita_pulita,
                            migliore_se_alto=(
                                1
                                if criterio_modificato
                                == "Più alto è meglio"
                                else 0
                            ),
                            descrizione=(
                                descrizione_modificata.strip()
                            ),
                        )

                        st.cache_data.clear()

                        st.success(
                            "Tipologia di test modificata."
                        )

                        st.rerun()

        with st.expander(
            "🗑️ Elimina test selezionato",
            expanded=False,
        ):
            st.warning(
                "Il test può essere eliminato solo se non "
                "contiene risultati registrati."
            )

            conferma_eliminazione_test = st.checkbox(
                (
                    f"Confermo di voler eliminare "
                    f"“{test_da_gestire['nome']}”"
                ),
                key=(
                    f"conferma_elimina_test_"
                    f"{test_da_gestire['id']}"
                ),
            )

            if st.button(
                "Elimina definitivamente",
                type="primary",
                disabled=not conferma_eliminazione_test,
                key=(
                    f"elimina_test_"
                    f"{test_da_gestire['id']}"
                ),
            ):
                try:
                    delete_test_type(
                        int(test_da_gestire["id"])
                    )

                except ValueError as errore:
                    st.error(str(errore))

                else:
                    st.cache_data.clear()

                    st.success(
                        "Tipologia di test eliminata."
                    )

                    st.rerun()

    
    nomi_test_presenti = {
        test["nome"].strip().lower()
        for test in tipi_test
    }

    test_da_aggiungere = [
        test
        for test in catalogo_iniziale
        if test["nome"].strip().lower()
        not in nomi_test_presenti
    ]

    if test_da_aggiungere:
        st.info(
            f"Sono disponibili "
            f"{len(test_da_aggiungere)} test iniziali "
            f"da aggiungere al catalogo."
        )

        if st.button(
            "Carica catalogo iniziale",
            key="carica_catalogo_test",
        ):
            for test in test_da_aggiungere:
                add_test_type(
                    nome=test["nome"],
                    categoria=test["categoria"],
                    unita_misura=test["unita_misura"],
                    migliore_se_alto=(
                        test["migliore_se_alto"]
                    ),
                    descrizione=test["descrizione"],
                )

            st.cache_data.clear()

            st.success(
                "Catalogo iniziale caricato correttamente."
            )

            st.rerun()

    else:
        st.success(
            "Il catalogo iniziale è già presente."
        )

    tipi_test_aggiornati = load_test_types()

    if tipi_test_aggiornati:
        import pandas as pd

        df_tipi = pd.DataFrame(
            tipi_test_aggiornati
        )

        df_tipi = df_tipi.rename(
            columns={
                "id": "ID",
                "nome": "Test",
                "categoria": "Categoria",
                "unita_misura": "Unità",
                "migliore_se_alto": "Criterio",
                "descrizione": "Descrizione",
            }
        )

        df_tipi["Criterio"] = (
            df_tipi["Criterio"].map(
                {
                    1: "Più alto è meglio",
                    0: "Più basso è meglio",
                }
            )
        )

        st.dataframe(
            df_tipi,
            use_container_width=True,
            hide_index=True,
        )

    else:
        st.warning(
            "Non sono ancora presenti tipologie di test."
        )

    with st.expander(
        "➕ Aggiungi un test personalizzato"
    ):
        with st.form(
            "form_nuovo_test_fisico"
        ):
            nome_nuovo_test = st.text_input(
                "Nome del test"
            )

            categoria_nuovo_test = st.selectbox(
                "Categoria",
                [
                    "Forza",
                    "Potenza",
                    "Reattività",
                    "Cardiovascolare",
                    "Velocità",
                    "Mobilità",
                    "Composizione corporea",
                    "Altro",
                ],
            )

            unita_nuovo_test = st.text_input(
                "Unità di misura",
                placeholder="kg, N, cm, mmHg, secondi...",
            )

            criterio_nuovo_test = st.selectbox(
                "Criterio prestativo",
                [
                    "Più alto è meglio",
                    "Più basso è meglio",
                ],
            )

            descrizione_nuovo_test = st.text_area(
                "Descrizione"
            )

            conferma_nuovo_test = (
                st.form_submit_button(
                    "Salva test"
                )
            )

        if conferma_nuovo_test:
            nome_pulito = (
                nome_nuovo_test.strip()
            )

            unita_pulita = (
                unita_nuovo_test.strip()
            )

            nomi_esistenti = {
                test["nome"].strip().lower()
                for test in load_test_types()
            }

            if not nome_pulito:
                st.error(
                    "Inserisci il nome del test."
                )

            elif not unita_pulita:
                st.error(
                    "Inserisci l'unità di misura."
                )

            elif nome_pulito.lower() in nomi_esistenti:
                st.error(
                    "Esiste già un test con questo nome."
                )

            else:
                add_test_type(
                    nome=nome_pulito,
                    categoria=(
                        categoria_nuovo_test
                    ),
                    unita_misura=unita_pulita,
                    migliore_se_alto=(
                        1
                        if criterio_nuovo_test
                        == "Più alto è meglio"
                        else 0
                    ),
                    descrizione=(
                        descrizione_nuovo_test.strip()
                    ),
                )

                st.cache_data.clear()

                st.success(
                    "Test aggiunto correttamente."
                )

                st.rerun()



with tab2:
    st.subheader("Sessioni di test")

    if sessioni_test:
        import pandas as pd

        df_sessioni = pd.DataFrame(
            sessioni_test
        )

        df_sessioni = df_sessioni.rename(
            columns={
                "id": "ID",
                "data": "Data",
                "categoria": "Categoria",
                "descrizione": "Descrizione",
                "note": "Note",
            }
        )

        colonne_da_mostrare = [
            "ID",
            "Data",
            "Categoria",
            "Descrizione",
            "Note",
        ]

        colonne_presenti = [
            colonna
            for colonna in colonne_da_mostrare
            if colonna in df_sessioni.columns
        ]

        st.dataframe(
            df_sessioni[colonne_presenti],
            use_container_width=True,
            hide_index=True,
        )

    else:
        st.info(
            "Non sono ancora presenti sessioni "
            "di test per questa stagione."
        )


    st.markdown("### Gestione sessioni")

    if sessioni_test:
        opzioni_gestione_sessioni = {
            (
                f"{sessione['data']} | "
                f"{sessione['categoria']} | "
                f"{sessione['descrizione']} | "
                f"ID {sessione['id']}"
            ): sessione
            for sessione in sessioni_test
        }

        sessione_gestione_nome = st.selectbox(
            "Sessione da modificare o eliminare",
            list(opzioni_gestione_sessioni.keys()),
            key="sessione_test_da_gestire",
        )

        sessione_da_gestire = opzioni_gestione_sessioni[
            sessione_gestione_nome
        ]

        categorie_sessione = [
            "Forza",
            "Potenza",
            "Reattività",
            "Cardiovascolare",
            "Velocità",
            "Valutazione completa",
            "Altro",
        ]

        categoria_attuale_sessione = (
            sessione_da_gestire["categoria"]
        )

        if (
            categoria_attuale_sessione
            not in categorie_sessione
        ):
            categorie_sessione.append(
                categoria_attuale_sessione
            )

        with st.expander(
            "✏️ Modifica sessione selezionata",
            expanded=False,
        ):
            with st.form(
                f"modifica_sessione_"
                f"{sessione_da_gestire['id']}"
            ):
                data_modificata = st.date_input(
                    "Data",
                    value=pd.to_datetime(
                        sessione_da_gestire["data"]
                    ).date(),
                )

                categoria_sessione_modificata = (
                    st.selectbox(
                        "Categoria",
                        categorie_sessione,
                        index=categorie_sessione.index(
                            categoria_attuale_sessione
                        ),
                    )
                )

                descrizione_sessione_modificata = (
                    st.text_input(
                        "Descrizione",
                        value=sessione_da_gestire[
                            "descrizione"
                        ],
                    )
                )

                note_sessione_modificate = st.text_area(
                    "Note",
                    value=(
                        sessione_da_gestire.get("note")
                        or ""
                    ),
                )

                salva_modifica_sessione = (
                    st.form_submit_button(
                        "Salva modifiche"
                    )
                )

            if salva_modifica_sessione:
                descrizione_pulita = (
                    descrizione_sessione_modificata
                    .strip()
                )

                if not descrizione_pulita:
                    st.error(
                        "La descrizione è obbligatoria."
                    )

                else:
                    update_test_session(
                        sessione_test_id=int(
                            sessione_da_gestire["id"]
                        ),
                        data=str(data_modificata),
                        categoria=(
                            categoria_sessione_modificata
                        ),
                        descrizione=descrizione_pulita,
                        note=(
                            note_sessione_modificate.strip()
                        ),
                    )

                    st.cache_data.clear()
                    st.success(
                        "Sessione modificata correttamente."
                    )
                    st.rerun()

        with st.expander(
            "🗑️ Elimina sessione selezionata",
            expanded=False,
        ):
            st.error(
                "Eliminando la sessione verranno eliminati "
                "anche tutti i risultati collegati."
            )

            conferma_sessione = st.checkbox(
                (
                    "Confermo di voler eliminare "
                    f"“{sessione_da_gestire['descrizione']}”"
                ),
                key=(
                    f"conferma_elimina_sessione_"
                    f"{sessione_da_gestire['id']}"
                ),
            )

            testo_conferma = st.text_input(
                "Scrivi ELIMINA per confermare",
                key=(
                    f"testo_elimina_sessione_"
                    f"{sessione_da_gestire['id']}"
                ),
            )

            eliminazione_abilitata = (
                conferma_sessione
                and testo_conferma.strip().upper()
                == "ELIMINA"
            )

            if st.button(
                "Elimina definitivamente la sessione",
                disabled=not eliminazione_abilitata,
                key=(
                    f"elimina_sessione_"
                    f"{sessione_da_gestire['id']}"
                ),
            ):
                delete_test_session(
                    int(sessione_da_gestire["id"])
                )

                st.cache_data.clear()
                st.success(
                    "Sessione e risultati collegati eliminati."
                )
                st.rerun()


    with st.expander(
        "➕ Crea una nuova sessione test",
        expanded=False,
    ):
        with st.form(
            "form_nuova_sessione_test"
        ):
            data_sessione = st.date_input(
                "Data della sessione"
            )

            categoria_sessione = st.selectbox(
                "Categoria",
                [
                    "Forza",
                    "Potenza",
                    "Reattività",
                    "Cardiovascolare",
                    "Velocità",
                    "Valutazione completa",
                    "Altro",
                ],
            )

            descrizione_sessione = st.text_input(
                "Descrizione",
                placeholder=(
                    "Es. Test di forza pre-stagione"
                ),
            )

            note_sessione = st.text_area(
                "Note",
                placeholder=(
                    "Protocollo, condizioni, "
                    "strumentazione utilizzata..."
                ),
            )

            conferma_sessione = (
                st.form_submit_button(
                    "Crea sessione"
                )
            )

        if conferma_sessione:
            descrizione_pulita = (
                descrizione_sessione.strip()
            )

            if not descrizione_pulita:
                st.error(
                    "Inserisci una descrizione "
                    "per la sessione."
                )

            else:
                add_test_session(
                    data=str(data_sessione),
                    stagione_id=stagione_id,
                    categoria=(
                        categoria_sessione
                    ),
                    descrizione=(
                        descrizione_pulita
                    ),
                    note=note_sessione.strip(),
                )

                st.cache_data.clear()

                st.success(
                    "Sessione di test creata "
                    "correttamente."
                )

                st.rerun()


with tab3:
    st.subheader("Inserimento risultati")

        # ==========================================
    # INSERIMENTO RAPIDO TEST CARDIOPOLMONARE
    # ==========================================

    st.markdown("### Inserimento rapido CPET")

    nomi_test_cpet = [
        "VO2max relativo",
        "VO2max assoluto",
        "Velocità massima CPET",
        "FC massima CPET",
        "Velocità soglia anaerobica",
        "FC soglia anaerobica",
    ]

    test_cpet_disponibili = {
        test["nome"].strip().lower(): test
        for test in tipi_test
        if test["nome"].strip().lower()
        in {
            nome.lower()
            for nome in nomi_test_cpet
        }
    }

    test_cpet_mancanti = [
        nome
        for nome in nomi_test_cpet
        if nome.lower()
        not in test_cpet_disponibili
    ]

    if test_cpet_mancanti:
        st.warning(
            "Prima carica nel catalogo questi test: "
            + ", ".join(test_cpet_mancanti)
        )

    elif not sessioni_test:
        st.info(
            "Crea prima una sessione cardiovascolare."
        )

    elif not giocatori:
        st.info(
            "Non ci sono giocatori nella stagione selezionata."
        )

    else:
        sessioni_cardio = [
            sessione
            for sessione in sessioni_test
            if (
                sessione.get("categoria")
                or ""
            ).strip().lower()
            == "cardiovascolare"
        ]

        sessioni_cpet_utilizzabili = (
            sessioni_cardio
            if sessioni_cardio
            else sessioni_test
        )

        opzioni_sessioni_cpet = {
            (
                f"{sessione['data']} | "
                f"{sessione['categoria']} | "
                f"{sessione['descrizione']} | "
                f"ID {sessione['id']}"
            ): sessione["id"]
            for sessione
            in sessioni_cpet_utilizzabili
        }

        opzioni_giocatori_cpet = {
            (
                f"{giocatore['cognome']} "
                f"{giocatore['nome']} | "
                f"ID {giocatore['id']}"
            ): giocatore["id"]
            for giocatore in giocatori
        }

        with st.expander(
            "🫀 Compila test cardiopolmonare",
            expanded=False,
        ):
            sessione_cpet_scelta = st.selectbox(
                "Sessione cardiovascolare",
                list(opzioni_sessioni_cpet.keys()),
                key="sessione_inserimento_cpet",
            )

            giocatore_cpet_scelto = st.selectbox(
                "Giocatore",
                list(opzioni_giocatori_cpet.keys()),
                key="giocatore_inserimento_cpet",
            )

            sessione_cpet_id = int(
                opzioni_sessioni_cpet[
                    sessione_cpet_scelta
                ]
            )

            giocatore_cpet_id = int(
                opzioni_giocatori_cpet[
                    giocatore_cpet_scelto
                ]
            )

            with st.form(
                "form_inserimento_rapido_cpet"
            ):
                col_cpet_1, col_cpet_2 = (
                    st.columns(2)
                )

                with col_cpet_1:
                    vo2max_relativo = st.number_input(
                        "VO₂max relativo (ml/kg/min)",
                        min_value=0.0,
                        value=0.0,
                        step=0.1,
                        format="%.1f",
                    )

                    velocita_massima_cpet = (
                        st.number_input(
                            "Velocità massima CPET (km/h)",
                            min_value=0.0,
                            value=0.0,
                            step=0.1,
                            format="%.1f",
                        )
                    )

                    velocita_soglia = st.number_input(
                        (
                            "Velocità soglia "
                            "anaerobica (km/h)"
                        ),
                        min_value=0.0,
                        value=0.0,
                        step=0.1,
                        format="%.1f",
                    )

                with col_cpet_2:
                    vo2max_assoluto = st.number_input(
                        "VO₂max assoluto (ml/min)",
                        min_value=0.0,
                        value=0.0,
                        step=10.0,
                        format="%.0f",
                    )

                    fc_massima_cpet = st.number_input(
                        "FC massima CPET (bpm)",
                        min_value=0,
                        max_value=250,
                        value=0,
                        step=1,
                    )

                    fc_soglia = st.number_input(
                        (
                            "FC soglia "
                            "anaerobica (bpm)"
                        ),
                        min_value=0,
                        max_value=250,
                        value=0,
                        step=1,
                    )

                percentile_vo2_testo = (
                    st.text_input(
                        "Percentile VO₂max relativo",
                        placeholder=(
                            "Facoltativo, valore 0-100"
                        ),
                    )
                )

                note_cpet = st.text_area(
                    "Note CPET",
                    placeholder=(
                        "Interpretazione, protocollo, "
                        "osservazioni cliniche..."
                    ),
                )

                conferma_cpet = (
                    st.form_submit_button(
                        "Salva tutti i parametri CPET"
                    )
                )

            if conferma_cpet:
                valori_cpet = {
                    "VO2max relativo": (
                        float(vo2max_relativo)
                    ),
                    "VO2max assoluto": (
                        float(vo2max_assoluto)
                    ),
                    "Velocità massima CPET": (
                        float(velocita_massima_cpet)
                    ),
                    "FC massima CPET": (
                        float(fc_massima_cpet)
                    ),
                    "Velocità soglia anaerobica": (
                        float(velocita_soglia)
                    ),
                    "FC soglia anaerobica": (
                        float(fc_soglia)
                    ),
                }

                campi_non_compilati = [
                    nome
                    for nome, valore_cpet
                    in valori_cpet.items()
                    if valore_cpet <= 0
                ]

                percentile_vo2 = None

                if percentile_vo2_testo.strip():
                    try:
                        percentile_vo2 = float(
                            percentile_vo2_testo
                            .strip()
                            .replace(",", ".")
                        )

                    except ValueError:
                        st.error(
                            "Il percentile deve essere "
                            "un numero."
                        )
                        st.stop()

                    if not 0 <= percentile_vo2 <= 100:
                        st.error(
                            "Il percentile deve essere "
                            "compreso tra 0 e 100."
                        )
                        st.stop()

                if campi_non_compilati:
                    st.error(
                        "Compila tutti i parametri CPET: "
                        + ", ".join(
                            campi_non_compilati
                        )
                    )

                else:
                    try:
                        for nome_test, valore_cpet in (
                            valori_cpet.items()
                        ):
                            tipo_test_cpet = (
                                test_cpet_disponibili[
                                    nome_test.lower()
                                ]
                            )

                            percentile_risultato = (
                                percentile_vo2
                                if nome_test
                                == "VO2max relativo"
                                else None
                            )

                            save_test_result(
                                sessione_test_id=(
                                    sessione_cpet_id
                                ),
                                giocatore_id=(
                                    giocatore_cpet_id
                                ),
                                tipo_test_id=int(
                                    tipo_test_cpet["id"]
                                ),
                                valore=valore_cpet,
                                lato="BILATERALE",
                                tentativo=1,
                                percentile=(
                                    percentile_risultato
                                ),
                                valore_secondario=None,
                                valido=1,
                                note=note_cpet.strip(),
                            )

                    except Exception as errore:
                        st.error(
                            "Errore durante il salvataggio "
                            f"dei parametri CPET: {errore}"
                        )

                    else:
                        st.cache_data.clear()

                        st.success(
                            "Tutti i parametri CPET "
                            "sono stati salvati."
                        )

                        st.rerun()

    st.divider()
    st.markdown("### Inserimento singolo risultato")

    if not sessioni_test:
        st.warning(
            "Prima devi creare almeno una sessione di test."
        )

    elif not tipi_test:
        st.warning(
            "Prima devi aggiungere almeno una tipologia di test."
        )

    elif not giocatori:
        st.warning(
            "Non ci sono giocatori nella stagione selezionata."
        )

    else:
        opzioni_sessioni = {
            (
                f"{sessione['data']} | "
                f"{sessione['categoria']} | "
                f"{sessione['descrizione']} | "
                f"ID {sessione['id']}"
            ): sessione["id"]
            for sessione in sessioni_test
        }

        sessione_scelta = st.selectbox(
            "Sessione di test",
            list(opzioni_sessioni.keys()),
            key="sessione_inserimento_risultato",
        )

        sessione_test_id = int(
            opzioni_sessioni[sessione_scelta]
        )

        opzioni_test = {
            (
                f"{test['categoria']} | "
                f"{test['nome']} "
                f"({test['unita_misura']})"
            ): test
            for test in tipi_test
        }

        test_scelto = st.selectbox(
            "Tipologia di test",
            list(opzioni_test.keys()),
            key="test_inserimento_risultato",
        )

        tipo_test = opzioni_test[test_scelto]

        opzioni_giocatori = {
            (
                f"{giocatore['cognome']} "
                f"{giocatore['nome']} | "
                f"ID {giocatore['id']}"
            ): giocatore["id"]
            for giocatore in giocatori
        }

        giocatore_scelto = st.selectbox(
            "Giocatore",
            list(opzioni_giocatori.keys()),
            key="giocatore_inserimento_risultato",
        )

        giocatore_id = int(
            opzioni_giocatori[giocatore_scelto]
        )

        test_monopodalici = {
            "single leg hop",
            "single leg drop jump",
            "single leg cmj",
            "rsi single leg drop jump",
        }

        nome_test_normalizzato = (
            tipo_test["nome"].strip().lower()
        )

        if nome_test_normalizzato in test_monopodalici:
            opzioni_lato = ["DX", "SX"]
        else:
            opzioni_lato = ["BILATERALE", "DX", "SX"]

        with st.form(
            "form_inserimento_risultato_fisico"
        ):
            lato = st.selectbox(
                "Lato",
                opzioni_lato,
            )

            tentativo = st.number_input(
                "Numero tentativo",
                min_value=1,
                max_value=10,
                value=1,
                step=1,
            )

            valore = st.number_input(
                (
                    f"Risultato "
                    f"({tipo_test['unita_misura']})"
                ),
                min_value=0.0,
                value=0.0,
                step=0.01,
                format="%.3f",
            )

            percentile_testo = st.text_input(
                "Percentile",
                placeholder=(
                    "Facoltativo. Es. 78"
                ),
                help=(
                    "Inserisci un valore compreso "
                    "tra 0 e 100."
                ),
            )

            risultato_valido = st.checkbox(
                "Risultato valido",
                value=True,
            )

            note_risultato = st.text_area(
                "Note",
                placeholder=(
                    "Eventuali osservazioni sul test"
                ),
            )

            conferma_risultato = (
                st.form_submit_button(
                    "Salva risultato"
                )
            )

        if conferma_risultato:
            percentile = None

            if percentile_testo.strip():
                try:
                    percentile = float(
                        percentile_testo
                        .strip()
                        .replace(",", ".")
                    )

                except ValueError:
                    st.error(
                        "Il percentile deve essere numerico."
                    )
                    st.stop()

                if not 0 <= percentile <= 100:
                    st.error(
                        "Il percentile deve essere "
                        "compreso tra 0 e 100."
                    )
                    st.stop()

            if valore <= 0:
                st.error(
                    "Inserisci un risultato maggiore di zero."
                )

            else:
                save_test_result(
                    sessione_test_id=sessione_test_id,
                    giocatore_id=giocatore_id,
                    tipo_test_id=int(
                        tipo_test["id"]
                    ),
                    valore=float(valore),
                    lato=lato,
                    tentativo=int(tentativo),
                    percentile=percentile,
                    valore_secondario=None,
                    valido=(
                        1
                        if risultato_valido
                        else 0
                    ),
                    note=note_risultato.strip(),
                )

                st.cache_data.clear()

                st.success(
                    "Risultato salvato correttamente."
                )

                st.rerun()


with tab4:
    st.subheader("Gestione risultati")

    if not sessioni_test:
        st.info(
            "Non sono presenti sessioni di test."
        )

    else:
        opzioni_sessioni_risultati = {
            (
                f"{sessione['data']} | "
                f"{sessione['categoria']} | "
                f"{sessione['descrizione']} | "
                f"ID {sessione['id']}"
            ): sessione["id"]
            for sessione in sessioni_test
        }

        sessione_risultati_scelta = st.selectbox(
            "Sessione",
            list(opzioni_sessioni_risultati.keys()),
            key="sessione_gestione_risultati",
        )

        sessione_risultati_id = int(
            opzioni_sessioni_risultati[
                sessione_risultati_scelta
            ]
        )

        risultati_sessione = (
            load_test_results_by_session(
                sessione_risultati_id
            )
        )

        if not risultati_sessione:
            st.info(
                "Non ci sono risultati registrati "
                "per questa sessione."
            )

        else:
            df_risultati_sessione = pd.DataFrame(
                risultati_sessione
            )

            colonne_tabella = [
                "cognome",
                "nome",
                "test",
                "lato",
                "tentativo",
                "valore",
                "unita_misura",
                "percentile",
                "valido",
                "note",
            ]

            colonne_presenti = [
                colonna
                for colonna in colonne_tabella
                if colonna
                in df_risultati_sessione.columns
            ]

            df_visualizzazione = (
                df_risultati_sessione[
                    colonne_presenti
                ].rename(
                    columns={
                        "cognome": "Cognome",
                        "nome": "Nome",
                        "test": "Test",
                        "lato": "Lato",
                        "tentativo": "Tentativo",
                        "valore": "Risultato",
                        "unita_misura": "Unità",
                        "percentile": "Percentile",
                        "valido": "Valido",
                        "note": "Note",
                    }
                )
            )

            if "Valido" in df_visualizzazione.columns:
                df_visualizzazione["Valido"] = (
                    df_visualizzazione["Valido"].map(
                        {
                            1: "Sì",
                            0: "No",
                        }
                    )
                )

            st.dataframe(
                df_visualizzazione,
                use_container_width=True,
                hide_index=True,
            )

            opzioni_risultati = {
                (
                    f"{risultato['cognome']} "
                    f"{risultato['nome']} | "
                    f"{risultato['test']} | "
                    f"{risultato['lato']} | "
                    f"Tentativo "
                    f"{risultato['tentativo']} | "
                    f"{risultato['valore']} "
                    f"{risultato['unita_misura']} | "
                    f"ID {risultato['id']}"
                ): risultato
                for risultato in risultati_sessione
            }

            risultato_scelto_nome = st.selectbox(
                "Risultato da modificare o eliminare",
                list(opzioni_risultati.keys()),
                key="risultato_test_da_gestire",
            )

            risultato_da_gestire = (
                opzioni_risultati[
                    risultato_scelto_nome
                ]
            )

            with st.expander(
                "✏️ Modifica risultato",
                expanded=False,
            ):
                with st.form(
                    f"modifica_risultato_"
                    f"{risultato_da_gestire['id']}"
                ):
                    lato_attuale = (
                        risultato_da_gestire.get("lato")
                        or "BILATERALE"
                    )

                    opzioni_lati = [
                        "BILATERALE",
                        "DX",
                        "SX",
                    ]

                    if lato_attuale not in opzioni_lati:
                        opzioni_lati.append(
                            lato_attuale
                        )

                    lato_modificato = st.selectbox(
                        "Lato",
                        opzioni_lati,
                        index=opzioni_lati.index(
                            lato_attuale
                        ),
                    )

                    tentativo_modificato = (
                        st.number_input(
                            "Tentativo",
                            min_value=1,
                            max_value=20,
                            value=int(
                                risultato_da_gestire.get(
                                    "tentativo"
                                )
                                or 1
                            ),
                            step=1,
                        )
                    )

                    valore_modificato = st.number_input(
                        (
                            "Risultato "
                            f"({risultato_da_gestire['unita_misura']})"
                        ),
                        min_value=0.0,
                        value=float(
                            risultato_da_gestire["valore"]
                        ),
                        step=0.01,
                        format="%.3f",
                    )

                    percentile_attuale = (
                        risultato_da_gestire.get(
                            "percentile"
                        )
                    )

                    percentile_modificato_testo = (
                        st.text_input(
                            "Percentile",
                            value=(
                                ""
                                if percentile_attuale is None
                                else str(
                                    percentile_attuale
                                )
                            ),
                        )
                    )

                    valido_modificato = st.checkbox(
                        "Risultato valido",
                        value=bool(
                            risultato_da_gestire.get(
                                "valido",
                                1,
                            )
                        ),
                    )

                    note_modificate = st.text_area(
                        "Note",
                        value=(
                            risultato_da_gestire.get(
                                "note"
                            )
                            or ""
                        ),
                    )

                    salva_modifica_risultato = (
                        st.form_submit_button(
                            "Salva modifiche"
                        )
                    )

                if salva_modifica_risultato:
                    percentile_modificato = None

                    if (
                        percentile_modificato_testo
                        .strip()
                    ):
                        try:
                            percentile_modificato = float(
                                percentile_modificato_testo
                                .strip()
                                .replace(",", ".")
                            )

                        except ValueError:
                            st.error(
                                "Il percentile deve "
                                "essere numerico."
                            )
                            st.stop()

                        if not (
                            0
                            <= percentile_modificato
                            <= 100
                        ):
                            st.error(
                                "Il percentile deve essere "
                                "compreso tra 0 e 100."
                            )
                            st.stop()

                    if valore_modificato <= 0:
                        st.error(
                            "Il risultato deve essere "
                            "maggiore di zero."
                        )

                    else:
                        try:
                            update_test_result(
                                risultato_id=int(
                                    risultato_da_gestire[
                                        "id"
                                    ]
                                ),
                                valore=float(
                                    valore_modificato
                                ),
                                lato=lato_modificato,
                                tentativo=int(
                                    tentativo_modificato
                                ),
                                percentile=(
                                    percentile_modificato
                                ),
                                valido=(
                                    1
                                    if valido_modificato
                                    else 0
                                ),
                                note=(
                                    note_modificate.strip()
                                ),
                            )

                        except Exception as errore:
                            st.error(
                                "Impossibile modificare "
                                f"il risultato: {errore}"
                            )

                        else:
                            st.cache_data.clear()
                            st.success(
                                "Risultato modificato."
                            )
                            st.rerun()

            with st.expander(
                "🗑️ Elimina risultato",
                expanded=False,
            ):
                st.warning(
                    "Questa operazione elimina soltanto "
                    "il risultato selezionato."
                )

                conferma_elimina_risultato = (
                    st.checkbox(
                        (
                            "Confermo di voler eliminare "
                            "questo risultato"
                        ),
                        key=(
                            "conferma_elimina_risultato_"
                            f"{risultato_da_gestire['id']}"
                        ),
                    )
                )

                if st.button(
                    "Elimina definitivamente il risultato",
                    disabled=(
                        not conferma_elimina_risultato
                    ),
                    key=(
                        "elimina_risultato_"
                        f"{risultato_da_gestire['id']}"
                    ),
                ):
                    delete_test_result(
                        int(
                            risultato_da_gestire["id"]
                        )
                    )

                    st.cache_data.clear()
                    st.success(
                        "Risultato eliminato."
                    )
                    st.rerun()


with tab5:
    st.subheader("Dati corporei")

    st.caption(
        "Il peso viene storicizzato e potrà essere usato "
        "per calcolare gli indici di forza relativa."
    )

    if not giocatori:
        st.warning(
            "Non ci sono giocatori nella stagione selezionata."
        )

    else:
        opzioni_giocatori_corpo = {
            (
                f"{giocatore['cognome']} "
                f"{giocatore['nome']} | "
                f"ID {giocatore['id']}"
            ): giocatore["id"]
            for giocatore in giocatori
        }

        with st.expander(
            "➕ Inserisci dati corporei",
            expanded=False,
        ):
            giocatore_corpo_scelto = st.selectbox(
                "Giocatore",
                list(opzioni_giocatori_corpo.keys()),
                key="giocatore_dati_corporei",
            )

            giocatore_corpo_id = int(
                opzioni_giocatori_corpo[
                    giocatore_corpo_scelto
                ]
            )

            with st.form("form_dati_corporei"):
                data_rilevazione = st.date_input(
                    "Data rilevazione"
                )

                peso_kg = st.number_input(
                    "Peso (kg)",
                    min_value=0.0,
                    value=0.0,
                    step=0.1,
                    format="%.2f",
                )

                altezza_cm = st.number_input(
                    "Altezza (cm)",
                    min_value=0.0,
                    value=0.0,
                    step=0.1,
                    format="%.1f",
                )

                massa_grassa = st.number_input(
                    "Massa grassa (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=0.0,
                    step=0.1,
                    format="%.1f",
                )

                note_corpo = st.text_area("Note")

                salva_corpo = st.form_submit_button(
                    "Salva dati corporei"
                )

            if salva_corpo:
                if peso_kg <= 0:
                    st.error(
                        "Inserisci almeno un peso maggiore di zero."
                    )

                else:
                    save_body_data(
                        giocatore_id=giocatore_corpo_id,
                        stagione_id=stagione_id,
                        data=str(data_rilevazione),
                        peso_kg=float(peso_kg),
                        altezza_cm=(
                            float(altezza_cm)
                            if altezza_cm > 0
                            else None
                        ),
                        massa_grassa_percentuale=(
                            float(massa_grassa)
                            if massa_grassa > 0
                            else None
                        ),
                        note=note_corpo.strip(),
                    )

                    st.cache_data.clear()
                    st.success(
                        "Dati corporei salvati."
                    )
                    st.rerun()

    if not dati_corporei:
        st.info(
            "Non sono ancora presenti rilevazioni corporee."
        )

    else:
        df_corpo = pd.DataFrame(dati_corporei)

        colonne_corpo = [
            "data",
            "cognome",
            "nome",
            "peso_kg",
            "altezza_cm",
            "massa_grassa_percentuale",
            "note",
        ]

        st.dataframe(
            df_corpo[colonne_corpo].rename(
                columns={
                    "data": "Data",
                    "cognome": "Cognome",
                    "nome": "Nome",
                    "peso_kg": "Peso kg",
                    "altezza_cm": "Altezza cm",
                    "massa_grassa_percentuale": "Massa grassa %",
                    "note": "Note",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        opzioni_dati_corpo = {
            (
                f"{dato['data']} | "
                f"{dato['cognome']} {dato['nome']} | "
                f"{dato['peso_kg']} kg | "
                f"ID {dato['id']}"
            ): dato
            for dato in dati_corporei
        }

        dato_corpo_nome = st.selectbox(
            "Rilevazione da modificare o eliminare",
            list(opzioni_dati_corpo.keys()),
            key="dato_corporeo_da_gestire",
        )

        dato_corpo = opzioni_dati_corpo[
            dato_corpo_nome
        ]

        with st.expander(
            "✏️ Modifica rilevazione",
            expanded=False,
        ):
            with st.form(
                f"modifica_corpo_{dato_corpo['id']}"
            ):
                data_corpo_modificata = st.date_input(
                    "Data",
                    value=pd.to_datetime(
                        dato_corpo["data"]
                    ).date(),
                )

                peso_modificato = st.number_input(
                    "Peso (kg)",
                    min_value=0.0,
                    value=float(
                        dato_corpo.get("peso_kg") or 0
                    ),
                    step=0.1,
                )

                altezza_modificata = st.number_input(
                    "Altezza (cm)",
                    min_value=0.0,
                    value=float(
                        dato_corpo.get("altezza_cm") or 0
                    ),
                    step=0.1,
                )

                grasso_modificato = st.number_input(
                    "Massa grassa (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(
                        dato_corpo.get(
                            "massa_grassa_percentuale"
                        )
                        or 0
                    ),
                    step=0.1,
                )

                note_corpo_modificate = st.text_area(
                    "Note",
                    value=dato_corpo.get("note") or "",
                )

                salva_corpo_modificato = (
                    st.form_submit_button(
                        "Salva modifiche"
                    )
                )

            if salva_corpo_modificato:
                if peso_modificato <= 0:
                    st.error(
                        "Il peso deve essere maggiore di zero."
                    )

                else:
                    update_body_data(
                        dato_corporeo_id=int(
                            dato_corpo["id"]
                        ),
                        data=str(data_corpo_modificata),
                        peso_kg=float(peso_modificato),
                        altezza_cm=(
                            float(altezza_modificata)
                            if altezza_modificata > 0
                            else None
                        ),
                        massa_grassa_percentuale=(
                            float(grasso_modificato)
                            if grasso_modificato > 0
                            else None
                        ),
                        note=(
                            note_corpo_modificate.strip()
                        ),
                    )

                    st.cache_data.clear()
                    st.success(
                        "Rilevazione modificata."
                    )
                    st.rerun()

        with st.expander(
            "🗑️ Elimina rilevazione",
            expanded=False,
        ):
            conferma_corpo = st.checkbox(
                "Confermo di voler eliminare la rilevazione",
                key=f"conferma_corpo_{dato_corpo['id']}",
            )

            if st.button(
                "Elimina definitivamente",
                disabled=not conferma_corpo,
                key=f"elimina_corpo_{dato_corpo['id']}",
            ):
                delete_body_data(
                    int(dato_corpo["id"])
                )

                st.cache_data.clear()
                st.success(
                    "Rilevazione eliminata."
                )
                st.rerun()


with tab6:
    st.subheader("Benchmark individuali")

    if not giocatori:
        st.warning(
            "Non ci sono giocatori nella stagione selezionata."
        )

    elif not tipi_test:
        st.warning(
            "Non sono presenti tipologie di test."
        )

    else:
        opzioni_giocatori_benchmark = {
            (
                f"{giocatore['cognome']} "
                f"{giocatore['nome']} | "
                f"ID {giocatore['id']}"
            ): giocatore
            for giocatore in giocatori
        }

        giocatore_benchmark_scelto = st.selectbox(
            "Giocatore",
            list(opzioni_giocatori_benchmark.keys()),
            key="giocatore_benchmark_fisico",
        )

        giocatore_benchmark = (
            opzioni_giocatori_benchmark[
                giocatore_benchmark_scelto
            ]
        )

        profilo_cpet = load_player_cpet_profile(
            int(giocatore_benchmark["id"])
        )

        with st.expander(
            "🫀 Profilo cardiovascolare attuale",
            expanded=False,
        ):
            if not profilo_cpet:
                st.info(
                    "Non sono disponibili risultati CPET "
                    "per questo giocatore."
                )

            else:
                valori_cpet = [
                    (
                        "VO₂max relativo",
                        "VO2max relativo",
                    ),
                    (
                        "VO₂max assoluto",
                        "VO2max assoluto",
                    ),
                    (
                        "Velocità massima CPET",
                        "Velocità massima CPET",
                    ),
                    (
                        "FC massima CPET",
                        "FC massima CPET",
                    ),
                    (
                        "Velocità soglia anaerobica",
                        "Velocità soglia anaerobica",
                    ),
                    (
                        "FC soglia anaerobica",
                        "FC soglia anaerobica",
                    ),
                ]

                for indice in range(
                    0,
                    len(valori_cpet),
                    3,
                ):
                    colonne = st.columns(3)

                    gruppo = valori_cpet[
                        indice:indice + 3
                    ]

                    for colonna, (
                        etichetta,
                        nome_database,
                    ) in zip(
                        colonne,
                        gruppo,
                    ):
                        with colonna:
                            dato = profilo_cpet.get(
                                nome_database
                            )

                            if dato:
                                st.metric(
                                    etichetta,
                                    (
                                        f"{dato['valore']:.1f} "
                                        f"{dato['unita_misura']}"
                                    ),
                                )

                                st.caption(
                                    pd.to_datetime(
                                        dato["data"]
                                    ).strftime(
                                        "%d/%m/%Y"
                                    )
                                )

                            else:
                                st.metric(
                                    etichetta,
                                    "—",
                                )

        opzioni_test_benchmark = {
            (
                f"{test['categoria']} | "
                f"{test['nome']} "
                f"({test['unita_misura']})"
            ): test
            for test in tipi_test
        }

        test_benchmark_scelto = st.selectbox(
            "Test",
            list(opzioni_test_benchmark.keys()),
            key="test_benchmark_fisico",
        )

        test_benchmark = (
            opzioni_test_benchmark[
                test_benchmark_scelto
            ]
        )

        storico = load_player_test_history(
            int(giocatore_benchmark["id"]),
            int(test_benchmark["id"]),
        )

        if not storico:
            st.info(
                "Non sono ancora presenti risultati validi "
                "per questo giocatore e questo test."
            )

        else:
            df_storico = pd.DataFrame(storico)

            df_storico["data"] = pd.to_datetime(
                df_storico["data"],
                errors="coerce",
            )

            df_storico = df_storico.sort_values(
                by=[
                    "data",
                    "sessione_test_id",
                    "tentativo",
                ],
                ascending=[
                    False,
                    False,
                    True,
                ],
            )

            migliore_se_alto = (
                int(
                    test_benchmark["migliore_se_alto"]
                )
                == 1
            )

            if migliore_se_alto:
                indici_migliori = (
                    df_storico.groupby(
                        [
                            "sessione_test_id",
                            "lato",
                        ]
                    )["valore"].idxmax()
                )
            else:
                indici_migliori = (
                    df_storico.groupby(
                        [
                            "sessione_test_id",
                            "lato",
                        ]
                    )["valore"].idxmin()
                )

            df_migliori = (
                df_storico.loc[indici_migliori]
                .sort_values(
                    by=[
                        "data",
                        "sessione_test_id",
                    ],
                    ascending=False,
                )
                .reset_index(drop=True)
            )

            lati_presenti = set(
                df_migliori["lato"]
                .dropna()
                .astype(str)
                .str.upper()
            )

            test_con_lati = (
                "DX" in lati_presenti
                or "SX" in lati_presenti
            )

            if test_con_lati:
                lato_benchmark = st.radio(
                    "Lato da analizzare",
                    [
                        "DX",
                        "SX",
                    ],
                    horizontal=True,
                    key="lato_benchmark_fisico",
                )

                df_analisi = df_migliori[
                    df_migliori["lato"]
                    .astype(str)
                    .str.upper()
                    == lato_benchmark
                ].copy()

            else:
                lato_benchmark = "BILATERALE"

                df_analisi = df_migliori.copy()

            if df_analisi.empty:
                st.info(
                    f"Non sono presenti risultati "
                    f"per il lato {lato_benchmark}."
                )

            else:
                df_analisi = (
                    df_analisi.sort_values(
                        by=[
                            "data",
                            "sessione_test_id",
                        ],
                        ascending=False,
                    )
                    .reset_index(drop=True)
                )

                ultimo = float(
                    df_analisi.iloc[0]["valore"]
                )

                precedente = None

                if len(df_analisi) >= 2:
                    precedente = float(
                        df_analisi.iloc[1]["valore"]
                    )

                if migliore_se_alto:
                    personal_best = float(
                        df_analisi["valore"].max()
                    )

                    percentuale_pb = (
                        ultimo / personal_best * 100
                        if personal_best > 0
                        else None
                    )

                else:
                    personal_best = float(
                        df_analisi["valore"].min()
                    )

                    percentuale_pb = (
                        personal_best / ultimo * 100
                        if ultimo > 0
                        else None
                    )

                miglioramento = None

                if (
                    precedente is not None
                    and precedente != 0
                ):
                    variazione_grezza = (
                        ultimo - precedente
                    ) / precedente * 100

                    if migliore_se_alto:
                        miglioramento = (
                            variazione_grezza
                        )
                    else:
                        miglioramento = (
                            -variazione_grezza
                        )

                unita = test_benchmark[
                    "unita_misura"
                ]

                nome_test_benchmark = (
                    test_benchmark["nome"]
                    .strip()
                    .lower()
                )

                forza_relativa = None
                peso_utilizzato = None
                data_peso_utilizzato = None

                if nome_test_benchmark == "squat 1 rm":
                    data_ultimo_test = (
                        df_analisi.iloc[0]["data"]
                    )

                    if pd.notna(data_ultimo_test):
                        data_riferimento_peso = (
                            data_ultimo_test.strftime(
                                "%Y-%m-%d"
                            )
                        )
                    else:
                        data_riferimento_peso = None

                    dato_peso = (
                        load_latest_body_weight(
                            int(
                                giocatore_benchmark[
                                    "id"
                                ]
                            ),
                            data_riferimento_peso,
                        )
                    )

                    if dato_peso:
                        peso_utilizzato = float(
                            dato_peso["peso_kg"]
                        )

                        data_peso_utilizzato = (
                            dato_peso["data"]
                        )

                        if peso_utilizzato > 0:
                            forza_relativa = (
                                ultimo
                                / peso_utilizzato
                            )

                col1, col2, col3, col4 = (
                    st.columns(4)
                )

                with col1:
                    st.metric(
                        "Ultimo risultato",
                        f"{ultimo:.2f} {unita}",
                    )

                with col2:
                    if precedente is None:
                        st.metric(
                            "Risultato precedente",
                            "—",
                        )
                    else:
                        st.metric(
                            "Risultato precedente",
                            (
                                f"{precedente:.2f} "
                                f"{unita}"
                            ),
                        )

                with col3:
                    st.metric(
                        "Personal best",
                        f"{personal_best:.2f} {unita}",
                    )

                with col4:
                    if percentuale_pb is None:
                        st.metric(
                            "% del personal best",
                            "—",
                        )
                    else:
                        st.metric(
                            "% del personal best",
                            f"{percentuale_pb:.1f}%",
                        )

                if nome_test_benchmark == "squat 1 rm":
                    st.markdown(
                        "### Forza relativa"
                    )

                    if forza_relativa is None:
                        st.warning(
                            "Non è disponibile un peso "
                            "corporeo registrato entro "
                            "la data del test."
                        )

                    else:
                        col_relativa, col_peso = (
                            st.columns(2)
                        )

                        with col_relativa:
                            st.metric(
                                (
                                    "Squat 1 RM / "
                                    "peso corporeo"
                                ),
                                (
                                    f"{forza_relativa:.2f} "
                                    "xBW"
                                ),
                            )

                        with col_peso:
                            st.metric(
                                "Peso utilizzato",
                                (
                                    f"{peso_utilizzato:.2f} "
                                    "kg"
                                ),
                            )

                        if data_peso_utilizzato:
                            data_peso_formattata = (
                                pd.to_datetime(
                                    data_peso_utilizzato
                                ).strftime(
                                    "%d/%m/%Y"
                                )
                            )

                            st.caption(
                                "Peso rilevato il "
                                f"{data_peso_formattata}."
                            )

                if miglioramento is not None:
                    if miglioramento > 0:
                        st.success(
                            "Miglioramento rispetto al "
                            "test precedente: "
                            f"{miglioramento:+.2f}%"
                        )

                    elif miglioramento < 0:
                        st.warning(
                            "Peggioramento rispetto al "
                            "test precedente: "
                            f"{miglioramento:.2f}%"
                        )

                    else:
                        st.info(
                            "Risultato invariato rispetto "
                            "al test precedente."
                        )

                if test_con_lati:
                    ultima_sessione_id = int(
                        df_migliori.iloc[0][
                            "sessione_test_id"
                        ]
                    )

                    df_ultima_sessione = (
                        df_migliori[
                            df_migliori[
                                "sessione_test_id"
                            ]
                            == ultima_sessione_id
                        ]
                    )

                    riga_dx = df_ultima_sessione[
                        df_ultima_sessione["lato"]
                        .astype(str)
                        .str.upper()
                        == "DX"
                    ]

                    riga_sx = df_ultima_sessione[
                        df_ultima_sessione["lato"]
                        .astype(str)
                        .str.upper()
                        == "SX"
                    ]

                    if (
                        not riga_dx.empty
                        and not riga_sx.empty
                    ):
                        valore_dx = float(
                            riga_dx.iloc[0]["valore"]
                        )

                        valore_sx = float(
                            riga_sx.iloc[0]["valore"]
                        )

                        riferimento = max(
                            valore_dx,
                            valore_sx,
                        )

                        if riferimento > 0:
                            asimmetria = (
                                abs(
                                    valore_dx
                                    - valore_sx
                                )
                                / riferimento
                                * 100
                            )
                        else:
                            asimmetria = 0.0

                        if valore_dx < valore_sx:
                            lato_deficitario = "DX"

                        elif valore_sx < valore_dx:
                            lato_deficitario = "SX"

                        else:
                            lato_deficitario = (
                                "Nessuno"
                            )

                        st.markdown(
                            "### Asimmetria "
                            "ultima sessione"
                        )

                        col_dx, col_sx, col_asim = (
                            st.columns(3)
                        )

                        with col_dx:
                            st.metric(
                                "DX",
                                (
                                    f"{valore_dx:.2f} "
                                    f"{unita}"
                                ),
                            )

                        with col_sx:
                            st.metric(
                                "SX",
                                (
                                    f"{valore_sx:.2f} "
                                    f"{unita}"
                                ),
                            )

                        with col_asim:
                            st.metric(
                                "Asimmetria",
                                f"{asimmetria:.2f}%",
                            )

                        st.caption(
                            "Lato con valore inferiore: "
                            f"{lato_deficitario}"
                        )

                st.markdown("### Storico")

                df_visualizzazione = (
                    df_analisi.copy()
                )

                df_visualizzazione["data"] = (
                    df_visualizzazione["data"]
                    .dt.strftime("%d/%m/%Y")
                )

                colonne_storico = [
                    "data",
                    "sessione",
                    "lato",
                    "tentativo",
                    "valore",
                    "percentile",
                    "note",
                ]

                colonne_presenti = [
                    colonna
                    for colonna in colonne_storico
                    if colonna
                    in df_visualizzazione.columns
                ]

                df_visualizzazione = (
                    df_visualizzazione[
                        colonne_presenti
                    ].rename(
                        columns={
                            "data": "Data",
                            "sessione": "Sessione",
                            "lato": "Lato",
                            "tentativo": "Tentativo",
                            "valore": "Risultato",
                            "percentile": "Percentile",
                            "note": "Note",
                        }
                    )
                )

                st.dataframe(
                    df_visualizzazione,
                    use_container_width=True,
                    hide_index=True,
                )

                if len(df_analisi) >= 2:
                    df_grafico = (
                        df_analisi[
                            [
                                "data",
                                "valore",
                            ]
                        ]
                        .sort_values("data")
                        .set_index("data")
                    )

                    st.markdown(
                        "### Andamento nel tempo"
                    )

                    st.line_chart(
                        df_grafico,
                        y="valore",
                    )


# ==========================================
# TAB 7 - IMPORTAZIONE AUTOMATICA REPORT
# ==========================================

with tab7:
    st.subheader(
        "📥 Importazione automatica dei report"
    )

    st.write(
        "Carica un report HTML OXYPEAK "
        "o Neuromuscolare. "
        "Il programma riconoscerà automaticamente "
        "il formato e leggerà atleti, date "
        "e risultati dei test."
    )

    file_report = st.file_uploader(
        "Seleziona report HTML",
        type=["html", "htm"],
        accept_multiple_files=False,
        key="upload_report_test_fisici",
    )

    if file_report is None:
        st.info(
            "Carica un file HTML per iniziare "
            "l'analisi automatica."
        )

    else:
        st.write(
            f"**File selezionato:** "
            f"{file_report.name}"
        )

        try:
            contenuto_file = file_report.getvalue()

            risultato_importazione = (
                riconosci_e_analizza_report(
                    contenuto_file,
                    file_report.name,
                )
            )

        except Exception as errore:
            st.error(
                "Non è stato possibile leggere "
                "il report."
            )

            st.exception(errore)

        else:
            st.success(
                "Report riconosciuto correttamente."
            )

            col_import_1, col_import_2 = (
                st.columns(2)
            )

            with col_import_1:
                st.metric(
                    "Formato riconosciuto",
                    risultato_importazione.get(
                        "formato",
                        "—",
                    ),
                )

            with col_import_2:
                st.metric(
                    "Sessioni trovate",
                    risultato_importazione.get(
                        "numero_sessioni",
                        0,
                    ),
                )

            sessioni_importate = (
                risultato_importazione.get(
                    "sessioni",
                    [],
                )
            )

            if not sessioni_importate:
                st.warning(
                    "Il file è stato riconosciuto, "
                    "ma non sono state trovate "
                    "sessioni importabili."
                )

            else:
                opzioni_sessioni_importate = {}

                for indice, sessione in enumerate(
                    sessioni_importate
                ):
                    data_test = sessione.get(
                        "data_test",
                        "Data non disponibile",
                    )

                    numero_atleti = len(
                        sessione.get(
                            "atleti",
                            [],
                        )
                    )

                    descrizione_sessione = (
                        f"{data_test} | "
                        f"{numero_atleti} atleti"
                    )

                    opzioni_sessioni_importate[
                        descrizione_sessione
                    ] = indice

                sessione_importata_scelta = (
                    st.selectbox(
                        "Sessione del report",
                        list(
                            opzioni_sessioni_importate.keys()
                        ),
                        key=(
                            "sessione_report_"
                            "oxypeak"
                        ),
                    )
                )

                indice_sessione = (
                    opzioni_sessioni_importate[
                        sessione_importata_scelta
                    ]
                )

                sessione_selezionata = (
                    sessioni_importate[
                        indice_sessione
                    ]
                )

                data_test_importata = (
                    sessione_selezionata.get(
                        "data_test"
                    )
                )

                atleti_importati = (
                    sessione_selezionata.get(
                        "atleti",
                        [],
                    )
                )

                st.markdown(
                    "### Anteprima della sessione"
                )

                col_sess_1, col_sess_2 = (
                    st.columns(2)
                )

                with col_sess_1:
                    st.metric(
                        "Data test",
                        (
                            data_test_importata
                            or "—"
                        ),
                    )

                with col_sess_2:
                    st.metric(
                        "Atleti trovati",
                        len(atleti_importati),
                    )

                righe_anteprima = []

                for atleta in atleti_importati:
                    nome_atleta = atleta.get(
                        "nome_report",
                        "Atleta non riconosciuto",
                    )

                    risultati_atleta = atleta.get(
                        "risultati",
                        [],
                    )

                    avvisi_atleta = atleta.get(
                        "avvisi",
                        [],
                    )

                    for risultato in risultati_atleta:
                        righe_anteprima.append(
                            {
                                "Atleta report": (
                                    nome_atleta
                                ),
                                "Test": risultato.get(
                                    "tipo_test"
                                ),
                                "Valore": risultato.get(
                                    "valore"
                                ),
                                "Unità": risultato.get(
                                    "unita"
                                ),
                                "Lato": risultato.get(
                                    "lato",
                                    "BILATERALE",
                                ),
                                "Avvisi": (
                                    " | ".join(
                                        avvisi_atleta
                                    )
                                    if avvisi_atleta
                                    else ""
                                ),
                            }
                        )

                df_anteprima_importazione = (
                    pd.DataFrame(
                        righe_anteprima
                    )
                )

                if df_anteprima_importazione.empty:
                    st.warning(
                        "Non sono stati trovati "
                        "risultati numerici nella "
                        "sessione selezionata."
                    )

                else:
                    st.dataframe(
                        df_anteprima_importazione,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Atleta report": (
                                st.column_config.TextColumn(
                                    "Atleta"
                                )
                            ),
                            "Test": (
                                st.column_config.TextColumn(
                                    "Test"
                                )
                            ),
                            "Valore": (
                                st.column_config.NumberColumn(
                                    "Valore",
                                    format="%.2f",
                                )
                            ),
                            "Unità": (
                                st.column_config.TextColumn(
                                    "Unità"
                                )
                            ),
                            "Lato": (
                                st.column_config.TextColumn(
                                    "Lato"
                                )
                            ),
                            "Avvisi": (
                                st.column_config.TextColumn(
                                    "Avvisi"
                                )
                            ),
                        },
                    )

                    st.write(
                        f"Risultati numerici trovati: "
                        f"{len(df_anteprima_importazione)}"
                    )

                    nomi_atleti_unici = (
                        df_anteprima_importazione[
                            "Atleta report"
                        ]
                        .dropna()
                        .unique()
                    )

                    st.write(
                        f"Atleti unici riconosciuti: "
                        f"{len(nomi_atleti_unici)}"
                    )

                    with st.expander(
                        "🔍 Controllo dettagliato "
                        "per atleta",
                        expanded=False,
                    ):
                        atleta_da_controllare = (
                            st.selectbox(
                                "Atleta",
                                sorted(
                                    nomi_atleti_unici
                                ),
                                key=(
                                    "controllo_atleta_"
                                    "importazione"
                                ),
                            )
                        )

                        df_atleta_controllo = (
                            df_anteprima_importazione[
                                df_anteprima_importazione[
                                    "Atleta report"
                                ]
                                == atleta_da_controllare
                            ]
                        )

                        st.dataframe(
                            df_atleta_controllo,
                            use_container_width=True,
                            hide_index=True,
                        )

                    st.info(
                        "In questa fase i dati sono "
                        "soltanto in anteprima. "
                        "Non sono ancora stati salvati "
                        "nel database."
                    )

                    st.markdown(
                        "### Associazione con la rosa"
                    )

                    stagioni_importazione = get_seasons()

                    if not stagioni_importazione:
                        st.warning(
                            "Non sono presenti stagioni "
                            "nel database."
                        )

                    else:
                        opzioni_stagioni_importazione = {
                            stagione["nome"]: int(
                                stagione["id"]
                            )
                            for stagione
                            in stagioni_importazione
                        }

                        stagione_attiva_importazione = next(
                            (
                                stagione["nome"]
                                for stagione
                                in stagioni_importazione
                                if stagione.get(
                                    "attiva"
                                ) == 1
                            ),
                            list(
                                opzioni_stagioni_importazione.keys()
                            )[0],
                        )

                        indice_stagione_importazione = list(
                            opzioni_stagioni_importazione.keys()
                        ).index(
                            stagione_attiva_importazione
                        )

                        stagione_importazione_scelta = (
                            st.selectbox(
                                "Stagione di destinazione",
                                list(
                                    opzioni_stagioni_importazione.keys()
                                ),
                                index=(
                                    indice_stagione_importazione
                                ),
                                key=(
                                    "stagione_importazione_"
                                    "report_test"
                                ),
                            )
                        )

                        stagione_importazione_id = (
                            opzioni_stagioni_importazione[
                                stagione_importazione_scelta
                            ]
                        )

                        rosa_importazione = (
                            get_players_by_season(
                                stagione_importazione_id
                            )
                        )

                        rosa_importazione = [
                            giocatore
                            for giocatore
                            in rosa_importazione
                            if giocatore.get(
                                "attivo",
                                1,
                            ) == 1
                        ]

                        if not rosa_importazione:
                            st.warning(
                                "La stagione selezionata "
                                "non contiene giocatori attivi."
                            )

                        else:
                            opzioni_giocatori = {
                                int(giocatore["id"]): (
                                    f"{giocatore['cognome']} "
                                    f"{giocatore['nome']}"
                                )
                                for giocatore
                                in rosa_importazione
                            }

                            associazioni_importazione = {}
                            associazioni_dubbie = 0
                            associazioni_mancanti = 0

                            nomi_report_unici = sorted(
                                {
                                    atleta.get(
                                        "nome_report",
                                        "",
                                    )
                                    for atleta
                                    in atleti_importati
                                    if atleta.get(
                                        "nome_report"
                                    )
                                }
                            )

                            st.write(
                                "Controlla le associazioni "
                                "prima del salvataggio."
                            )

                            for indice_nome, nome_report in enumerate(
                                nomi_report_unici
                            ):
                                (
                                    giocatore_proposto_id,
                                    punteggio_proposto,
                                ) = calcola_associazione_atleta(
                                    nome_report,
                                    rosa_importazione,
                                )

                                etichetta_affidabilita = (
                                    "Alta"
                                    if punteggio_proposto >= 0.90
                                    else (
                                        "Media"
                                        if punteggio_proposto >= 0.75
                                        else "Bassa"
                                    )
                                )

                                if punteggio_proposto < 0.90:
                                    associazioni_dubbie += 1

                                col_nome, col_associazione = (
                                    st.columns(
                                        [1, 2]
                                    )
                                )

                                with col_nome:
                                    st.write(
                                        f"**{nome_report}**"
                                    )

                                    st.caption(
                                        "Affidabilità proposta: "
                                        f"{etichetta_affidabilita} "
                                        f"({punteggio_proposto * 100:.0f}%)"
                                    )

                                with col_associazione:
                                    lista_id_giocatori = [
                                        None
                                    ] + list(
                                        opzioni_giocatori.keys()
                                    )

                                    indice_default_giocatore = 0

                                    if (
                                        giocatore_proposto_id
                                        in lista_id_giocatori
                                    ):
                                        indice_default_giocatore = (
                                            lista_id_giocatori.index(
                                                giocatore_proposto_id
                                            )
                                        )

                                    giocatore_selezionato_id = (
                                        st.selectbox(
                                            "Giocatore associato",
                                            lista_id_giocatori,
                                            index=(
                                                indice_default_giocatore
                                            ),
                                            format_func=lambda valore: (
                                                "— Non associare —"
                                                if valore is None
                                                else opzioni_giocatori[
                                                    valore
                                                ]
                                            ),
                                            key=(
                                                "associazione_report_"
                                                f"{indice_sessione}_"
                                                f"{indice_nome}_"
                                                f"{stagione_importazione_id}"
                                            ),
                                            label_visibility=(
                                                "collapsed"
                                            ),
                                        )
                                    )

                                associazioni_importazione[
                                    nome_report
                                ] = giocatore_selezionato_id

                                if giocatore_selezionato_id is None:
                                    associazioni_mancanti += 1

                            st.session_state[
                                "associazioni_importazione_report"
                            ] = associazioni_importazione

                            col_assoc_1, col_assoc_2, col_assoc_3 = (
                                st.columns(3)
                            )

                            with col_assoc_1:
                                st.metric(
                                    "Atleti nel report",
                                    len(
                                        nomi_report_unici
                                    ),
                                )

                            with col_assoc_2:
                                st.metric(
                                    "Associazioni dubbie",
                                    associazioni_dubbie,
                                )

                            with col_assoc_3:
                                st.metric(
                                    "Non associati",
                                    associazioni_mancanti,
                                )

                            if associazioni_mancanti > 0:
                                st.warning(
                                    "Uno o più atleti non sono "
                                    "associati. I loro risultati "
                                    "non potranno essere salvati."
                                )

                            elif associazioni_dubbie > 0:
                                st.info(
                                    "Tutti gli atleti sono associati, "
                                    "ma alcune corrispondenze devono "
                                    "essere controllate manualmente."
                                )

                            else:
                                st.success(
                                    "Tutti gli atleti sono stati "
                                    "associati con alta affidabilità."
                                )

                            st.markdown(
                                "### Salvataggio nel database"
                            )

                            tipi_test_catalogo = get_test_types()

                            tipi_test_per_nome = {
                                str(tipo_test["nome"]).strip(): int(
                                    tipo_test["id"]
                                )
                                for tipo_test in tipi_test_catalogo
                            }

                            test_presenti_nel_report = sorted(
                                {
                                    risultato.get("tipo_test")
                                    for atleta in atleti_importati
                                    for risultato in atleta.get(
                                        "risultati",
                                        [],
                                    )
                                    if risultato.get("tipo_test")
                                }
                            )

                            test_mancanti_catalogo = [
                                nome_test
                                for nome_test
                                in test_presenti_nel_report
                                if nome_test
                                not in tipi_test_per_nome
                            ]

                            if test_mancanti_catalogo:
                                st.warning(
                                    "Prima del salvataggio devi creare "
                                    "nel catalogo queste tipologie di test:"
                                )

                                for nome_test in test_mancanti_catalogo:
                                    st.write(
                                        f"- {nome_test}"
                                    )

                            risultati_salvabili = 0
                            atleti_salvabili = 0

                            for atleta in atleti_importati:
                                nome_report = atleta.get(
                                    "nome_report"
                                )

                                giocatore_id_associato = (
                                    associazioni_importazione.get(
                                        nome_report
                                    )
                                )

                                if giocatore_id_associato is None:
                                    continue

                                atleti_salvabili += 1

                                for risultato in atleta.get(
                                    "risultati",
                                    [],
                                ):
                                    nome_test = risultato.get(
                                        "tipo_test"
                                    )

                                    valore_test = risultato.get(
                                        "valore"
                                    )

                                    if (
                                        nome_test
                                        in tipi_test_per_nome
                                        and valore_test is not None
                                    ):
                                        risultati_salvabili += 1

                            col_salva_1, col_salva_2 = (
                                st.columns(2)
                            )

                            with col_salva_1:
                                st.metric(
                                    "Atleti salvabili",
                                    atleti_salvabili,
                                )

                            with col_salva_2:
                                st.metric(
                                    "Risultati salvabili",
                                    risultati_salvabili,
                                )

                            descrizione_importazione = (
                                st.text_input(
                                    "Descrizione sessione",
                                    value=(
                                        "Importazione automatica "
                                        "report OXYPEAK"
                                    ),
                                    key=(
                                        "descrizione_sessione_"
                                        "import_oxypeak"
                                    ),
                                )
                            )

                            note_importazione = st.text_area(
                                "Note importazione",
                                value=(
                                    f"File origine: "
                                    f"{file_report.name}"
                                ),
                                key=(
                                    "note_sessione_"
                                    "import_oxypeak"
                                ),
                            )

                            conferma_importazione = st.checkbox(
                                "Confermo di aver controllato "
                                "associazioni, data e valori",
                                key=(
                                    "conferma_importazione_"
                                    "oxypeak"
                                ),
                            )

                            categoria_importazione = (
                                sessione_selezionata.get(
                                    "categoria",
                                    "CPET",
                                )
                            )

                            sessione_duplicata = (
                                find_test_session_duplicate(
                                    data=data_test_importata,
                                    stagione_id=stagione_importazione_id,
                                    categoria=categoria_importazione,
                                    descrizione=descrizione_importazione.strip(),
                                )
                            )

                            autorizza_duplicato = False

                            if sessione_duplicata:
                                st.warning(
                                    "Esiste già una sessione test "
                                    "con la stessa data, stagione, "
                                    "categoria e descrizione."
                                )

                                st.write(
                                    f"**ID sessione esistente:** "
                                    f"{sessione_duplicata['id']}"
                                )

                                autorizza_duplicato = st.checkbox(
                                    "Confermo di voler creare "
                                    "comunque una nuova sessione",
                                    key=(
                                        "autorizza_duplicato_"
                                        f"{indice_sessione}_"
                                        f"{stagione_importazione_id}"
                                    ),
                                )
                            
                            blocco_duplicato = bool(
                                sessione_duplicata is not None
                                and not bool(autorizza_duplicato)
                            )

                            pulsante_disabilitato = bool(
                                not bool(conferma_importazione)
                                or int(associazioni_mancanti or 0) > 0
                                or len(test_mancanti_catalogo or []) > 0
                                or int(risultati_salvabili or 0) == 0
                                or data_test_importata is None
                                or blocco_duplicato
                            )

                            if st.button(
                                "💾 Salva sessione e risultati",
                                type="primary",
                                disabled=pulsante_disabilitato,
                                key=(
                                    "salva_importazione_"
                                    f"{indice_sessione}_"
                                    f"{stagione_importazione_id}"
                                ),
                            ):
                                try:
                                    sessione_test_id = add_test_session(
                                        data_test_importata,
                                        stagione_importazione_id,
                                        sessione_selezionata.get(
                                            "categoria",
                                            "CPET",
                                        ),
                                        descrizione_importazione.strip(),
                                        note_importazione.strip(),
                                    )

                                    risultati_salvati = 0
                                    atleti_salvati = set()

                                    for atleta in atleti_importati:
                                        nome_report = atleta.get(
                                            "nome_report"
                                        )

                                        giocatore_id_associato = (
                                            associazioni_importazione.get(
                                                nome_report
                                            )
                                        )

                                        if giocatore_id_associato is None:
                                            continue

                                        for risultato in atleta.get(
                                            "risultati",
                                            [],
                                        ):
                                            nome_test = risultato.get(
                                                "tipo_test"
                                            )

                                            valore_test = risultato.get(
                                                "valore"
                                            )

                                            tipo_test_id = (
                                                tipi_test_per_nome.get(
                                                    nome_test
                                                )
                                            )

                                            if (
                                                tipo_test_id is None
                                                or valore_test is None
                                            ):
                                                continue

                                            percentile_test = risultato.get(
                                                "percentile"
                                            )

                                            if percentile_test is not None:
                                                try:
                                                    percentile_test = float(
                                                        percentile_test
                                                    )
                                                except (
                                                    TypeError,
                                                    ValueError,
                                                ):
                                                    percentile_test = None

                                            save_test_result(
                                                sessione_test_id=(
                                                    sessione_test_id
                                                ),
                                                giocatore_id=int(
                                                    giocatore_id_associato
                                                ),
                                                tipo_test_id=int(
                                                    tipo_test_id
                                                ),
                                                valore=float(
                                                    valore_test
                                                ),
                                                lato=risultato.get(
                                                    "lato",
                                                    "BILATERALE",
                                                ),
                                                tentativo=int(
                                                    risultato.get(
                                                        "tentativo",
                                                        1,
                                                    )
                                                ),
                                                percentile=percentile_test,
                                                valore_secondario=None,
                                                valido=int(
                                                    risultato.get(
                                                        "valido",
                                                        1,
                                                    )
                                                ),
                                                note=(
                                                    "Importato automaticamente "
                                                    f"da {file_report.name}"
                                                ),
                                            )

                                            risultati_salvati += 1

                                            atleti_salvati.add(
                                                int(
                                                    giocatore_id_associato
                                                )
                                            )

                                except Exception as errore:
                                    st.error(
                                        "Errore durante il salvataggio "
                                        "della sessione."
                                    )

                                    st.exception(
                                        errore
                                    )

                                else:
                                    st.cache_data.clear()

                                    st.success(
                                        "Importazione completata."
                                    )

                                    col_esito_1, col_esito_2, col_esito_3 = (
                                        st.columns(3)
                                    )

                                    with col_esito_1:
                                        st.metric(
                                            "ID sessione",
                                            sessione_test_id,
                                        )

                                    with col_esito_2:
                                        st.metric(
                                            "Atleti salvati",
                                            len(atleti_salvati),
                                        )

                                    with col_esito_3:
                                        st.metric(
                                            "Risultati salvati",
                                            risultati_salvati,
                                        )

                                    st.info(
                                        "I dati sono ora disponibili "
                                        "nelle sezioni Sessioni test, "
                                        "Gestione risultati e Benchmark."
                                    )
                    