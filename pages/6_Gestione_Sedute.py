import pandas as pd
import streamlit as st

from utils.database_training import (
    add_exercise_to_training,
    add_full_training,
    get_catalogo_esercitazioni,
    get_exercises_by_training,
    get_full_training,
    get_stagioni_training,
    elimina_exercise_seduta,
    get_exercise_by_id,
    update_exercise_seduta,
)


st.set_page_config(
    page_title="Allenamenti",
    page_icon="🏋️",
    layout="wide",
)

st.title("🏋️ Gestione allenamenti")

st.caption(
    "Crea le sedute complete e collega le esercitazioni "
    "del catalogo."
)


# ==========================
# FUNZIONI DI SUPPORTO
# ==========================

def get_etichetta_stagione(stagione):
    for campo in [
        "nome",
        "stagione",
        "descrizione",
        "denominazione",
    ]:
        valore = stagione.get(campo)

        if valore:
            return str(valore)

    return f"Stagione ID {stagione['id']}"


# ==========================
# CARICAMENTO DATI
# ==========================

stagioni = get_stagioni_training()
catalogo = get_catalogo_esercitazioni()

stagioni_per_etichetta = {
    get_etichetta_stagione(stagione): stagione["id"]
    for stagione in stagioni
}

catalogo_per_etichetta = {}

for esercitazione in catalogo:
    macro = (
        esercitazione.get("macro_tipologia")
        or "Senza macro-tipologia"
    )

    etichetta = (
        f'{esercitazione["nome"]} — {macro} '
        f'— ID {esercitazione["id"]}'
    )

    catalogo_per_etichetta[etichetta] = esercitazione


tab_nuovo, tab_esercizi, tab_riepilogo = st.tabs(
    [
        "➕ Nuovo allenamento",
        "🏃 Aggiungi esercitazioni",
        "📋 Riepilogo",
    ]
)


# ==========================
# NUOVO FULL TRAINING
# ==========================

with tab_nuovo:
    st.subheader("Crea un FULL TRAINING")

    if not stagioni:
        st.warning(
            "Non risultano stagioni presenti nel database."
        )

    else:
        with st.form(
            "form_nuovo_full_training",
            clear_on_submit=True,
        ):
            col1, col2 = st.columns(2)

            with col1:
                stagione_selezionata = st.selectbox(
                    "Stagione *",
                    options=list(
                        stagioni_per_etichetta.keys()
                    ),
                )

                data_attivita = st.date_input(
                    "Data allenamento *"
                )

                nome_allenamento = st.text_input(
                    "Nome seduta *",
                    placeholder=(
                        "Esempio: MD-3 - Seduta campo"
                    ),
                )

            with col2:
                durata_minuti = st.number_input(
                    "Durata totale prevista",
                    min_value=0.0,
                    step=5.0,
                    format="%.1f",
                )

                fase_stagione = st.text_input(
                    "Fase della stagione",
                    placeholder=(
                        "Esempio: Precampionato"
                    ),
                )

                categoria_squadra = st.text_input(
                    "Categoria squadra",
                    placeholder="Esempio: Primavera",
                )

            descrizione = st.text_area(
                "Descrizione della seduta"
            )

            note = st.text_area(
                "Note"
            )

            salva_training = st.form_submit_button(
                "Crea allenamento",
                type="primary",
                use_container_width=True,
            )

        if salva_training:
            nome_pulito = nome_allenamento.strip()

            if not nome_pulito:
                st.error(
                    "Inserisci il nome dell'allenamento."
                )

            else:
                try:
                    training_id = add_full_training(
                        stagione_id=(
                            stagioni_per_etichetta[
                                stagione_selezionata
                            ]
                        ),
                        data_attivita=(
                            data_attivita.isoformat()
                        ),
                        nome=nome_pulito,
                        durata_minuti=(
                            durata_minuti
                            if durata_minuti > 0
                            else None
                        ),
                        fase_stagione=(
                            fase_stagione.strip()
                            or None
                        ),
                        categoria_squadra=(
                            categoria_squadra.strip()
                            or None
                        ),
                        descrizione=(
                            descrizione.strip()
                            or None
                        ),
                        note=note.strip() or None,
                    )

                    st.success(
                        "Allenamento creato "
                        f"correttamente. ID: {training_id}"
                    )

                    st.rerun()

                except Exception as errore:
                    st.error(
                        "Errore durante la creazione "
                        f"dell'allenamento: {errore}"
                    )


# ==========================
# AGGIUNTA EXERCISE
# ==========================

with tab_esercizi:
    st.subheader(
        "Aggiungi un'esercitazione alla seduta"
    )

    full_training = get_full_training()

    if not full_training:
        st.info(
            "Crea prima almeno un FULL TRAINING."
        )

    elif not catalogo:
        st.info(
            "Il catalogo non contiene esercitazioni attive."
        )

    else:
        training_per_etichetta = {}

        for training in full_training:
            etichetta = (
                f'{training["data_attivita"]} — '
                f'{training["nome"]} '
                f'— ID {training["id"]}'
            )

            training_per_etichetta[etichetta] = training

        training_selezionato = st.selectbox(
            "Allenamento",
            options=list(
                training_per_etichetta.keys()
            ),
        )

        training = training_per_etichetta[
            training_selezionato
        ]

        with st.form(
            "form_aggiungi_exercise",
            clear_on_submit=True,
        ):
            esercitazione_selezionata = st.selectbox(
                "Esercitazione del catalogo",
                options=list(
                    catalogo_per_etichetta.keys()
                ),
            )

            col1, col2 = st.columns(2)

            with col1:
                nome_personalizzato = st.text_input(
                    "Nome visualizzato",
                    placeholder=(
                        "Lascia vuoto per usare il nome "
                        "del catalogo"
                    ),
                )

            with col2:
                durata_esercizio = st.number_input(
                    "Durata esercitazione",
                    min_value=0.0,
                    step=1.0,
                    format="%.1f",
                )

            descrizione_esercizio = st.text_area(
                "Descrizione o regole specifiche"
            )

            note_esercizio = st.text_area(
                "Note esercitazione"
            )

            salva_esercizio = st.form_submit_button(
                "Aggiungi esercitazione",
                type="primary",
                use_container_width=True,
            )

        if salva_esercizio:
            esercitazione = catalogo_per_etichetta[
                esercitazione_selezionata
            ]

            nome_finale = (
                nome_personalizzato.strip()
                or esercitazione["nome"]
            )

            try:
                exercise_id = add_exercise_to_training(
                    full_training_id=training["id"],
                    stagione_id=training["stagione_id"],
                    data_attivita=(
                        training["data_attivita"]
                    ),
                    esercitazione_catalogo_id=(
                        esercitazione["id"]
                    ),
                    nome=nome_finale,
                    macro_tipologia_id=(
                        esercitazione[
                            "macro_tipologia_id"
                        ]
                    ),
                    obiettivo_id=(
                        esercitazione[
                            "obiettivo_principale_id"
                        ]
                    ),
                    durata_minuti=(
                        durata_esercizio
                        if durata_esercizio > 0
                        else None
                    ),
                    descrizione=(
                        descrizione_esercizio.strip()
                        or None
                    ),
                    note=(
                        note_esercizio.strip()
                        or None
                    ),
                )

                st.success(
                    "Esercitazione aggiunta "
                    f"correttamente. ID: {exercise_id}"
                )

                st.rerun()

            except Exception as errore:
                st.error(
                    "Errore durante l'aggiunta "
                    f"dell'esercitazione: {errore}"
                )

        st.divider()
        st.markdown("#### Esercitazioni della seduta")

        esercizi_seduta = get_exercises_by_training(
            training["id"]
        )

        if not esercizi_seduta:
            st.info(
                "La seduta non contiene ancora "
                "esercitazioni."
            )

        else:
            df_esercizi = pd.DataFrame(
                esercizi_seduta
            )

            df_esercizi = df_esercizi.rename(
                columns={
                    "nome": "Esercitazione",
                    "macro_tipologia": "Macro-tipologia",
                    "obiettivo": "Obiettivo",
                    "durata_minuti": "Durata",
                    "descrizione": "Descrizione",
                }
            )

            colonne = [
                "Esercitazione",
                "Macro-tipologia",
                "Obiettivo",
                "Durata",
                "Descrizione",
            ]

            st.dataframe(
                df_esercizi[colonne],
                use_container_width=True,
                hide_index=True,
            )


        st.divider()
        st.markdown("#### Modifica o elimina esercitazione")

        esercizi_seduta = get_exercises_by_training(
            training["id"]
        )

        if esercizi_seduta:
            esercizi_per_etichetta = {}

            for esercizio in esercizi_seduta:
                durata_testo = (
                    f'{esercizio["durata_minuti"]} min'
                    if esercizio["durata_minuti"] is not None
                    else "durata non indicata"
                )

                etichetta = (
                    f'{esercizio["nome"]} '
                    f'— {durata_testo} '
                    f'— ID {esercizio["id"]}'
                )

                esercizi_per_etichetta[etichetta] = esercizio["id"]

            esercizio_selezionato_label = st.selectbox(
                "Seleziona l'esercitazione da gestire",
                options=list(esercizi_per_etichetta.keys()),
                key=f"exercise_manage_{training['id']}",
            )

            exercise_id = esercizi_per_etichetta[
                esercizio_selezionato_label
            ]

            exercise = get_exercise_by_id(exercise_id)

            catalogo_id_attuale = exercise[
                "esercitazione_catalogo_id"
            ]

            etichetta_catalogo_attuale = None

            for etichetta, voce in catalogo_per_etichetta.items():
                if voce["id"] == catalogo_id_attuale:
                    etichetta_catalogo_attuale = etichetta
                    break

            opzioni_catalogo = list(
                catalogo_per_etichetta.keys()
            )

            if etichetta_catalogo_attuale in opzioni_catalogo:
                indice_catalogo = opzioni_catalogo.index(
                    etichetta_catalogo_attuale
                )
            else:
                indice_catalogo = 0

            with st.form(
                f"form_modifica_exercise_{exercise_id}"
            ):
                esercitazione_catalogo_modifica = st.selectbox(
                    "Esercitazione del catalogo",
                    options=opzioni_catalogo,
                    index=indice_catalogo,
                )

                col_mod1, col_mod2 = st.columns(2)

                with col_mod1:
                    nome_modificato = st.text_input(
                        "Nome visualizzato",
                        value=exercise["nome"] or "",
                    )

                with col_mod2:
                    durata_modificata = st.number_input(
                        "Durata esercitazione",
                        min_value=0.0,
                        step=1.0,
                        format="%.1f",
                        value=float(
                            exercise["durata_minuti"] or 0
                        ),
                    )

                descrizione_modificata = st.text_area(
                    "Descrizione o regole specifiche",
                    value=exercise["descrizione"] or "",
                )

                note_modificate = st.text_area(
                    "Note esercitazione",
                    value=exercise["note"] or "",
                )

                col_salva, col_elimina = st.columns(2)

                with col_salva:
                    salva_modifica = st.form_submit_button(
                        "Salva modifiche",
                        type="primary",
                        use_container_width=True,
                    )

                with col_elimina:
                    elimina_esercizio = st.form_submit_button(
                        "Elimina dalla seduta",
                        use_container_width=True,
                    )

            if salva_modifica:
                esercitazione_catalogo = (
                    catalogo_per_etichetta[
                        esercitazione_catalogo_modifica
                    ]
                )

                try:
                    update_exercise_seduta(
                        exercise_id=exercise_id,
                        nome=nome_modificato.strip(),
                        esercitazione_catalogo_id=(
                            esercitazione_catalogo["id"]
                        ),
                        macro_tipologia_id=(
                            esercitazione_catalogo[
                                "macro_tipologia_id"
                            ]
                        ),
                        obiettivo_id=(
                            esercitazione_catalogo[
                                "obiettivo_principale_id"
                            ]
                        ),
                        durata_minuti=(
                            durata_modificata
                            if durata_modificata > 0
                            else None
                        ),
                        descrizione=(
                            descrizione_modificata.strip()
                            or None
                        ),
                        note=(
                            note_modificate.strip()
                            or None
                        ),
                    )

                    st.success(
                        "Esercitazione aggiornata correttamente."
                    )
                    st.rerun()

                except Exception as errore:
                    st.error(
                        "Errore durante la modifica: "
                        f"{errore}"
                    )

            if elimina_esercizio:
                try:
                    elimina_exercise_seduta(exercise_id)

                    st.success(
                        "Esercitazione eliminata dalla seduta."
                    )
                    st.rerun()

                except Exception as errore:
                    st.error(
                        "Errore durante l'eliminazione: "
                        f"{errore}"
                    )


# ==========================
# RIEPILOGO ALLENAMENTI
# ==========================

with tab_riepilogo:
    st.subheader("Allenamenti registrati")

    allenamenti = get_full_training()

    if not allenamenti:
        st.info(
            "Non sono ancora presenti allenamenti."
        )

    else:
        righe = []

        for allenamento in allenamenti:
            esercizi = get_exercises_by_training(
                allenamento["id"]
            )

            durata_esercizi = sum(
                float(esercizio["durata_minuti"] or 0)
                for esercizio in esercizi
            )

            righe.append(
                {
                    "Data": allenamento[
                        "data_attivita"
                    ],
                    "Allenamento": allenamento["nome"],
                    "Fase": allenamento[
                        "fase_stagione"
                    ],
                    "Categoria": allenamento[
                        "categoria_squadra"
                    ],
                    "Esercitazioni": len(esercizi),
                    "Durata esercizi": durata_esercizi,
                }
            )

        dataframe = pd.DataFrame(righe)

        st.dataframe(
            dataframe,
            use_container_width=True,
            hide_index=True,
        )