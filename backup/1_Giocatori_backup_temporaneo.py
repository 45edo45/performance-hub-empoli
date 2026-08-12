import streamlit as st
import pandas as pd
import os


st.title("👥 Gestione Giocatori")


file_database = "database/giocatori.csv"


# Creo database se non esiste
if not os.path.exists(file_database):

    df = pd.DataFrame(
        columns=[
            "ID",
            "Nome",
            "Cognome",
            "Ruolo",
            "Anno_nascita",
            "Numero_maglia",
            "Note"
        ]
    )

    df.to_csv(
        file_database,
        index=False
    )


# Carico database
df = pd.read_csv(file_database)


st.subheader("➕ Inserisci nuovo giocatore")


with st.form("nuovo_giocatore"):

    nome = st.text_input("Nome")
    cognome = st.text_input("Cognome")
    ruolo = st.selectbox(
        "Ruolo",
        [
            "Portiere",
            "Difensore",
            "Centrocampista",
            "Esterno",
            "Attaccante"
        ]
    )

    anno = st.number_input(
        "Anno di nascita",
        min_value=1990,
        max_value=2030,
        step=1
    )

    numero = st.number_input(
        "Numero maglia",
        min_value=1,
        max_value=99,
        step=1
    )

    note = st.text_area("Note")

    salva = st.form_submit_button(
       "Salva giocatore"
    )


    if salva:

        nuovo = pd.DataFrame(
            [
                {
                    "ID": f"{cognome[:3].upper()}{len(df)+1}",
                    "Nome": nome,
                    "Cognome": cognome,
                    "Ruolo": ruolo,
                    "Anno_nascita": anno,
                    "Numero_maglia": numero,
                    "Note": note
                }
            ]
        )


        df = pd.concat(
            [df, nuovo],
            ignore_index=True
        )


        df.to_csv(
            file_database,
            index=False
        )


        st.success(
            "✅ Giocatore aggiunto"
        )


st.subheader("📋 Rosa giocatori")

st.dataframe(
    df,
    use_container_width=True
)
