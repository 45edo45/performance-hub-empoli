import pandas as pd
import streamlit as st

from utils.database_training import (
    add_catalogo_esercitazione,
    get_catalogo_con_tag,
    get_esercitazione_catalogo_by_id,
    get_macro_tipologie,
    get_obiettivi_attivita,
    get_tag_by_esercitazione,
    get_tag_esercitazioni,
    set_catalogo_esercitazione_attiva,
    sostituisci_tag_esercitazione,
    update_catalogo_esercitazione,
)


st.set_page_config(
    page_title="Catalogo esercitazioni",
    page_icon="📚",
    layout="wide",
)

st.title("📚 Catalogo esercitazioni")

st.caption(
    "Crea, modifica e gestisci le esercitazioni utilizzate "
    "nei report di allenamento."
)


# ==========================
# CARICAMENTO DATI BASE
# ==========================

macro_tipologie = get_macro_tipologie()
obiettivi = get_obiettivi_attivita()
tag_disponibili = get_tag_esercitazioni()

macro_per_nome = {
    voce["nome"]: voce["id"]
    for voce in macro_tipologie
}

macro_per_id = {
    voce["id"]: voce["nome"]
    for voce in macro_tipologie
}

obiettivi_per_nome = {
    voce["nome"]: voce["id"]
    for voce in obiettivi
}

obiettivi_per_id = {
    voce["id"]: voce["nome"]
    for voce in obiettivi
}

tag_per_nome = {
    voce["nome"]: voce["id"]
    for voce in tag_disponibili
}


# ==========================
# TABELLE PRINCIPALI
# ==========================

tab_nuova, tab_modifica, tab_catalogo = st.tabs(
    [
        "➕ Nuova esercitazione",
        "✏️ Modifica esercitazione",
        "📋 Catalogo completo",
    ]
)


# ==========================
# NUOVA ESERCITAZIONE
# ==========================

with tab_nuova:
    st.subheader("Nuova esercitazione")

    with st.form(
        "form_nuova_esercitazione",
        clear_on_submit=True,
    ):
        col1, col2 = st.columns(2)

        with col1:
            nome = st.text_input(
                "Nome esercitazione *",
                placeholder="Esempio: 6vs6 + 2 jolly",
            )

            macro_selezionata = st.selectbox(
                "Macro-tipologia",
                options=[
                    "Nessuna",
                    *list(macro_per_nome.keys()),
                ],
                key="nuova_macro",
            )

        with col2:
            obiettivo_selezionato = st.selectbox(
                "Obiettivo principale",
                options=[
                    "Nessuno",
                    *list(obiettivi_per_nome.keys()),
                ],
                key="nuovo_obiettivo",
            )

            tag_selezionati = st.multiselect(
                "Tag",
                options=list(tag_per_nome.keys()),
                placeholder="Seleziona uno o più tag",
                key="nuovi_tag",
            )

        descrizione = st.text_area(
            "Descrizione",
            placeholder=(
                "Dimensioni del campo, numero di giocatori, "
                "regole, tempi di lavoro e altre informazioni."
            ),
        )

        salva = st.form_submit_button(
            "Salva esercitazione",
            type="primary",
            use_container_width=True,
        )

    if salva:
        nome_pulito = nome.strip()

        if not nome_pulito:
            st.error(
                "Inserisci il nome dell'esercitazione."
            )

        else:
            macro_id = (
                macro_per_nome[macro_selezionata]
                if macro_selezionata != "Nessuna"
                else None
            )

            obiettivo_id = (
                obiettivi_per_nome[obiettivo_selezionato]
                if obiettivo_selezionato != "Nessuno"
                else None
            )

            try:
                esercitazione_id = add_catalogo_esercitazione(
                    nome=nome_pulito,
                    macro_tipologia_id=macro_id,
                    obiettivo_principale_id=obiettivo_id,
                    descrizione=descrizione.strip() or None,
                )

                tag_ids = [
                    tag_per_nome[nome_tag]
                    for nome_tag in tag_selezionati
                ]

                sostituisci_tag_esercitazione(
                    esercitazione_id=esercitazione_id,
                    tag_ids=tag_ids,
                )

                st.success(
                    f"Esercitazione “{nome_pulito}” "
                    "salvata correttamente."
                )

                st.rerun()

            except Exception as errore:
                st.error(
                    "Errore durante il salvataggio: "
                    f"{errore}"
                )


# ==========================
# MODIFICA ESERCITAZIONE
# ==========================

with tab_modifica:
    st.subheader("Modifica esercitazione")

    catalogo_completo = get_catalogo_con_tag(
        solo_attive=False,
    )

    if not catalogo_completo:
        st.info(
            "Non sono ancora presenti esercitazioni."
        )

    else:
        esercitazioni_per_etichetta = {}

        for esercitazione in catalogo_completo:
            stato = (
                "Attiva"
                if esercitazione["attiva"] == 1
                else "Disattivata"
            )

            etichetta = (
                f'{esercitazione["nome"]} '
                f'— {stato} '
                f'— ID {esercitazione["id"]}'
            )

            esercitazioni_per_etichetta[etichetta] = (
                esercitazione["id"]
            )

        etichetta_selezionata = st.selectbox(
            "Seleziona l'esercitazione",
            options=list(
                esercitazioni_per_etichetta.keys()
            ),
        )

        esercitazione_id = (
            esercitazioni_per_etichetta[
                etichetta_selezionata
            ]
        )

        esercitazione = (
            get_esercitazione_catalogo_by_id(
                esercitazione_id
            )
        )

        tag_attuali = get_tag_by_esercitazione(
            esercitazione_id
        )

        nomi_tag_attuali = [
            tag["nome"]
            for tag in tag_attuali
            if tag["nome"] in tag_per_nome
        ]

        macro_attuale = macro_per_id.get(
            esercitazione["macro_tipologia_id"],
            "Nessuna",
        )

        obiettivo_attuale = obiettivi_per_id.get(
            esercitazione[
                "obiettivo_principale_id"
            ],
            "Nessuno",
        )

        opzioni_macro = [
            "Nessuna",
            *list(macro_per_nome.keys()),
        ]

        opzioni_obiettivi = [
            "Nessuno",
            *list(obiettivi_per_nome.keys()),
        ]

        indice_macro = opzioni_macro.index(
            macro_attuale
        )

        indice_obiettivo = opzioni_obiettivi.index(
            obiettivo_attuale
        )

        stato_testo = (
            "🟢 Esercitazione attiva"
            if esercitazione["attiva"] == 1
            else "🔴 Esercitazione disattivata"
        )

        st.write(stato_testo)

        with st.form(
            f"form_modifica_{esercitazione_id}"
        ):
            col1, col2 = st.columns(2)

            with col1:
                nuovo_nome = st.text_input(
                    "Nome esercitazione *",
                    value=esercitazione["nome"],
                )

                nuova_macro = st.selectbox(
                    "Macro-tipologia",
                    options=opzioni_macro,
                    index=indice_macro,
                )

            with col2:
                nuovo_obiettivo = st.selectbox(
                    "Obiettivo principale",
                    options=opzioni_obiettivi,
                    index=indice_obiettivo,
                )

                nuovi_tag = st.multiselect(
                    "Tag",
                    options=list(
                        tag_per_nome.keys()
                    ),
                    default=nomi_tag_attuali,
                )

            nuova_descrizione = st.text_area(
                "Descrizione",
                value=(
                    esercitazione["descrizione"]
                    or ""
                ),
            )

            col_salva, col_stato = st.columns(2)

            with col_salva:
                aggiorna = st.form_submit_button(
                    "Salva modifiche",
                    type="primary",
                    use_container_width=True,
                )

            with col_stato:
                if esercitazione["attiva"] == 1:
                    cambia_stato = (
                        st.form_submit_button(
                            "Disattiva esercitazione",
                            use_container_width=True,
                        )
                    )
                else:
                    cambia_stato = (
                        st.form_submit_button(
                            "Riattiva esercitazione",
                            use_container_width=True,
                        )
                    )

        if aggiorna:
            nome_pulito = nuovo_nome.strip()

            if not nome_pulito:
                st.error(
                    "Il nome non può essere vuoto."
                )

            else:
                nuova_macro_id = (
                    macro_per_nome[nuova_macro]
                    if nuova_macro != "Nessuna"
                    else None
                )

                nuovo_obiettivo_id = (
                    obiettivi_per_nome[
                        nuovo_obiettivo
                    ]
                    if nuovo_obiettivo != "Nessuno"
                    else None
                )

                nuovi_tag_ids = [
                    tag_per_nome[nome_tag]
                    for nome_tag in nuovi_tag
                ]

                try:
                    update_catalogo_esercitazione(
                        esercitazione_id=(
                            esercitazione_id
                        ),
                        nome=nome_pulito,
                        macro_tipologia_id=(
                            nuova_macro_id
                        ),
                        obiettivo_principale_id=(
                            nuovo_obiettivo_id
                        ),
                        descrizione=(
                            nuova_descrizione.strip()
                            or None
                        ),
                    )

                    sostituisci_tag_esercitazione(
                        esercitazione_id=(
                            esercitazione_id
                        ),
                        tag_ids=nuovi_tag_ids,
                    )

                    st.success(
                        "Esercitazione aggiornata "
                        "correttamente."
                    )

                    st.rerun()

                except Exception as errore:
                    st.error(
                        "Errore durante la modifica: "
                        f"{errore}"
                    )

        if cambia_stato:
            nuovo_stato = (
                esercitazione["attiva"] != 1
            )

            try:
                set_catalogo_esercitazione_attiva(
                    esercitazione_id=(
                        esercitazione_id
                    ),
                    attiva=nuovo_stato,
                )

                messaggio = (
                    "Esercitazione riattivata."
                    if nuovo_stato
                    else "Esercitazione disattivata."
                )

                st.success(messaggio)
                st.rerun()

            except Exception as errore:
                st.error(
                    "Errore durante il cambio di stato: "
                    f"{errore}"
                )


# ==========================
# CATALOGO COMPLETO
# ==========================

with tab_catalogo:
    st.subheader("Esercitazioni presenti")

    mostra_disattivate = st.checkbox(
        "Mostra anche le esercitazioni disattivate",
        value=False,
    )

    catalogo = get_catalogo_con_tag(
        solo_attive=not mostra_disattivate,
    )

    if not catalogo:
        st.info(
            "Il catalogo non contiene esercitazioni."
        )

    else:
        dataframe = pd.DataFrame(catalogo)

        dataframe["Stato"] = dataframe[
            "attiva"
        ].apply(
            lambda valore: (
                "Attiva"
                if valore == 1
                else "Disattivata"
            )
        )

        dataframe = dataframe.rename(
            columns={
                "nome": "Esercitazione",
                "macro_tipologia": (
                    "Macro-tipologia"
                ),
                "obiettivo_principale": (
                    "Obiettivo"
                ),
                "descrizione": "Descrizione",
                "tag": "Tag",
            }
        )

        colonne_visibili = [
            "Esercitazione",
            "Macro-tipologia",
            "Obiettivo",
            "Tag",
            "Descrizione",
            "Stato",
        ]

        dataframe = dataframe[colonne_visibili]

        testo_ricerca = st.text_input(
            "Cerca nel catalogo",
            placeholder=(
                "Cerca per nome, macro-tipologia, "
                "obiettivo o tag"
            ),
        )

        if testo_ricerca:
            ricerca = (
                testo_ricerca.strip().lower()
            )

            maschera = (
                dataframe
                .fillna("")
                .astype(str)
                .apply(
                    lambda colonna: (
                        colonna
                        .str.lower()
                        .str.contains(
                            ricerca,
                            regex=False,
                        )
                    )
                )
                .any(axis=1)
            )

            dataframe = dataframe[maschera]

        st.dataframe(
            dataframe,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Esercitazione": (
                    st.column_config.TextColumn(
                        width="medium",
                    )
                ),
                "Macro-tipologia": (
                    st.column_config.TextColumn(
                        width="medium",
                    )
                ),
                "Obiettivo": (
                    st.column_config.TextColumn(
                        width="medium",
                    )
                ),
                "Tag": (
                    st.column_config.TextColumn(
                        width="large",
                    )
                ),
                "Descrizione": (
                    st.column_config.TextColumn(
                        width="large",
                    )
                ),
                "Stato": (
                    st.column_config.TextColumn(
                        width="small",
                    )
                ),
            },
        )

        st.caption(
            "Esercitazioni visualizzate: "
            f"{len(dataframe)}"
        )