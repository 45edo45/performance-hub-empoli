import streamlit as st
import pandas as pd

from utils.database import (
    get_seasons,
    get_players_by_season,
    get_test_types,
    add_test_type,
    add_test_session,
    get_test_sessions,
    save_test_result,
    get_test_results_by_session,
)


st.set_page_config(
    page_title="Dati fisici",
    page_icon="🏋️",
)


# =========================
# FUNZIONI DI CARICAMENTO
# =========================

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
def load_test_results(sessione_test_id):
    return get_test_results_by_session(
        sessione_test_id
    )


st.title("🏋️ Test e dati fisici")


# =========================
# SELEZIONE STAGIONE
# =========================

stagioni = load_seasons()

if not stagioni:
    st.warning(
        "Non sono presenti stagioni nel database."
    )
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


indice_stagione = list(
    opzioni_stagioni.keys()
).index(stagione_attiva)


stagione_scelta = st.selectbox(
    "Stagione",
    list(opzioni_stagioni.keys()),
    index=indice_stagione,
    key="stagione_dati_fisici",
)


stagione_id = int(
    opzioni_stagioni[stagione_scelta]
)


# =========================
# CARICAMENTO DATI DI BASE
# =========================

giocatori = load_players_by_season(
    stagione_id
)

tipi_test = load_test_types()

sessioni_test = load_test_sessions(
    stagione_id
)


# =========================
# TABS PRINCIPALI
# =========================

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "📚 Tipologie test",
        "📅 Sessioni test",
        "📝 Inserimento risultati",
        "📊 Risultati",
    ]
)


# =========================
# TAB 1 - TIPOLOGIE TEST
# =========================

with tab1:

    st.subheader("Tipologie di test disponibili")

    if tipi_test:

        df_tipi_test = pd.DataFrame(
            tipi_test
        )

        df_tipi_test = df_tipi_test.rename(
            columns={
                "id": "ID",
                "nome": "Test",
                "categoria": "Categoria",
                "unita_misura": "Unità",
                "migliore_se_alto": "Criterio",
                "descrizione": "Descrizione",
            }
        )

        if "Criterio" in df_tipi_test.columns:
            df_tipi_test["Criterio"] = (
                df_tipi_test["Criterio"].map(
                    {
                        1: "Più alto è meglio",
                        0: "Più basso è meglio",
                    }
                )
            )

        st.dataframe(
            df_tipi_test,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info(
            "Non sono ancora presenti tipologie di test."
        )


    with st.expander(
        "➕ Aggiungi una tipologia di test",
        expanded=False,
    ):

        with st.form("nuovo_tipo_test"):

            nome_test = st.text_input(
                "Nome del test",
                placeholder="Es. CMJ, Sprint 10 m, Yo-Yo IR1",
            )

            categoria_test = st.selectbox(
                "Categoria",
                [
                    "Forza",
                    "Potenza",
                    "Velocità",
                    "Cardiovascolare",
                    "Mobilità",
                    "Composizione corporea",
                    "Altro",
                ],
            )

            unita_misura = st.text_input(
                "Unità di misura",
                placeholder="Es. cm, s, m, km/h, N",
            )

            criterio = st.selectbox(
                "Criterio prestativo",
                [
                    "Più alto è meglio",
                    "Più basso è meglio",
                ],
            )

            descrizione_test = st.text_area(
                "Descrizione",
                placeholder=(
                    "Descrizione del protocollo "
                    "o del valore misurato"
                ),
            )

            salva_tipo_test = (
                st.form_submit_button(
                    "Salva tipologia test"
                )
            )


        if salva_tipo_test:

            if (
                not nome_test.strip()
                or not unita_misura.strip()
            ):

                st.error(
                    "Nome del test e unità di misura "
                    "sono obbligatori."
                )

            else:

                migliore_se_alto = (
                    1
                    if criterio
                    == "Più alto è meglio"
                    else 0
                )

                add_test_type(
                    nome=nome_test.strip(),
                    categoria=categoria_test,
                    unita_misura=(
                        unita_misura.strip()
                    ),
                    migliore_se_alto=(
                        migliore_se_alto
                    ),
                    descrizione=(
                        descrizione_test.strip()
                    ),
                )

                st.cache_data.clear()

                st.success(
                    "Tipologia di test aggiunta."
                )

                st.rerun()


# =========================
# TAB 2 - SESSIONI TEST
# =========================

with tab2:

    st.subheader("Sessioni di test")

    if sessioni_test:

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

        st.dataframe(
            df_sessioni,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info(
            "Non sono ancora presenti sessioni "
            "di test per questa stagione."
        )


    with st.expander(
        "➕ Crea una nuova sessione test",
        expanded=False,
    ):

        with st.form("nuova_sessione_test"):

            data_sessione = st.date_input(
                "Data della sessione"
            )

            categoria_sessione = st.selectbox(
                "Categoria della sessione",
                [
                    "Forza",
                    "Cardiovascolare",
                    "Velocità",
                    "Valutazione completa",
                    "Altro",
                ],
            )

            descrizione_sessione = st.text_input(
                "Descrizione",
                placeholder=(
                    "Es. Test forza pre-stagione"
                ),
            )

            note_sessione = st.text_area(
                "Note"
            )

            salva_sessione = (
                st.form_submit_button(
                    "Crea sessione"
                )
            )


        if salva_sessione:

            if not descrizione_sessione.strip():

                st.error(
                    "La descrizione della sessione "
                    "è obbligatoria."
                )

            else:

                add_test_session(
                    data=str(data_sessione),
                    stagione_id=stagione_id,
                    categoria=(
                        categoria_sessione
                    ),
                    descrizione=(
                        descrizione_sessione.strip()
                    ),
                    note=note_sessione.strip(),
                )

                st.cache_data.clear()

                st.success(
                    "Sessione di test creata."
                )

                st.rerun()


# =========================
# TAB 3 - INSERIMENTO RISULTATI
# =========================

with tab3:

    st.subheader("Inserimento risultati")

    if not sessioni_test:

        st.warning(
            "Prima devi creare una sessione di test."
        )

    elif not tipi_test:

        st.warning(
            "Prima devi creare almeno una "
            "tipologia di test."
        )

    elif not giocatori:

        st.warning(
            "Non ci sono giocatori associati "
            "alla stagione selezionata."
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
            "Sessione test",
            list(opzioni_sessioni.keys()),
            key="sessione_inserimento_test",
        )


        sessione_test_id = int(
            opzioni_sessioni[
                sessione_scelta
            ]
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
            "Test",
            list(opzioni_test.keys()),
            key="tipo_test_inserimento",
        )


        tipo_test = opzioni_test[
            test_scelto
        ]


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
            key="giocatore_test",
        )


        giocatore_id = int(
            opzioni_giocatori[
                giocatore_scelto
            ]
        )


        with st.form("inserimento_risultato_test"):

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

            valore_secondario_testo = st.text_input(
                "Valore secondario",
                placeholder=(
                    "Facoltativo, ad esempio lato destro "
                    "o secondo tentativo"
                ),
            )

            risultato_valido = st.checkbox(
                "Risultato valido",
                value=True,
            )

            note_risultato = st.text_area(
                "Note sul risultato"
            )

            salva_risultato = (
                st.form_submit_button(
                    "Salva risultato"
                )
            )


        if salva_risultato:

            if valore_secondario_testo.strip():

                try:
                    valore_secondario = float(
                        valore_secondario_testo
                        .strip()
                        .replace(",", ".")
                    )

                except ValueError:
                    st.error(
                        "Il valore secondario deve "
                        "essere numerico."
                    )
                    st.stop()

            else:
                valore_secondario = None


            save_test_result(
                sessione_test_id=(
                    sessione_test_id
                ),
                giocatore_id=giocatore_id,
                tipo_test_id=int(
                    tipo_test["id"]
                ),
                valore=float(valore),
                valore_secondario=(
                    valore_secondario
                ),
                valido=(
                    1
                    if risultato_valido
                    else 0
                ),
                note=note_risultato.strip(),
            )

            st.cache_data.clear()

            st.success(
                "Risultato salvato."
            )

            st.rerun()


# =========================
# TAB 4 - RISULTATI
# =========================

with tab4:

    st.subheader("Risultati delle sessioni")

    if not sessioni_test:

        st.info(
            "Non sono presenti sessioni di test."
        )

    else:

        opzioni_sessioni_report = {
            (
                f"{sessione['data']} | "
                f"{sessione['categoria']} | "
                f"{sessione['descrizione']} | "
                f"ID {sessione['id']}"
            ): sessione["id"]
            for sessione in sessioni_test
        }


        opzione_vuota = (
            "— Nessuna sessione selezionata —"
        )


        sessione_report = st.selectbox(
            "Sessione da visualizzare",
            [
                opzione_vuota
            ] + list(
                opzioni_sessioni_report.keys()
            ),
            index=0,
            key="sessione_report_test",
        )


        if sessione_report == opzione_vuota:

            st.info(
                "Seleziona una sessione per "
                "visualizzare i risultati."
            )

        else:

            sessione_report_id = int(
                opzioni_sessioni_report[
                    sessione_report
                ]
            )


            risultati = load_test_results(
                sessione_report_id
            )


            if not risultati:

                st.info(
                    "Non sono ancora presenti risultati "
                    "per questa sessione."
                )

            else:

                df_risultati = pd.DataFrame(
                    risultati
                )


                colonne_da_mostrare = [
                    "cognome",
                    "nome",
                    "test",
                    "categoria",
                    "valore",
                    "valore_secondario",
                    "unita_misura",
                    "valido",
                    "note",
                ]


                colonne_presenti = [
                    colonna
                    for colonna
                    in colonne_da_mostrare
                    if colonna
                    in df_risultati.columns
                ]


                df_risultati = df_risultati[
                    colonne_presenti
                ]


                df_risultati = (
                    df_risultati.rename(
                        columns={
                            "cognome": "Cognome",
                            "nome": "Nome",
                            "test": "Test",
                            "categoria": "Categoria",
                            "valore": "Risultato",
                            "valore_secondario": (
                                "Valore secondario"
                            ),
                            "unita_misura": "Unità",
                            "valido": "Valido",
                            "note": "Note",
                        }
                    )
                )


                if "Valido" in df_risultati.columns:

                    df_risultati["Valido"] = (
                        df_risultati[
                            "Valido"
                        ].map(
                            {
                                1: "Sì",
                                0: "No",
                            }
                        )
                    )


                st.write(
                    f"Risultati presenti: "
                    f"{len(df_risultati)}"
                )


                st.dataframe(
                    df_risultati,
                    use_container_width=True,
                    hide_index=True,
                )