import streamlit as st
import pandas as pd
import os

st.title("📥 Importazione dati GPEXE")

file = st.file_uploader(
    "Carica file CSV GPEXE",
    type=["csv"]
)

data = st.date_input(
    "Data allenamento"
)

seduta = st.text_input(
    "Tipo seduta",
    placeholder="es. Alta intensità"
)


if file is not None:

    df = pd.read_csv(file)

    st.subheader("Anteprima dati GPEXE")
    st.dataframe(df)


    if st.button("Importa dati"):

        df["data"] = str(data)
        df["seduta"] = seduta


        colonne = {
            "athlete": "giocatore",
            "dur": "durata",
            "dist": "distanza",
            "max sp": "max_speed",
            "dist/sp": "sprint_distance",
            "Z2 dist/sp": "z2_distance",
            "Z3 dist/sp": "z3_distance",
            "Z4 dist/sp": "z4_distance",
            "sp ev": "speed_events",
            "bursts": "accelerazioni",
            "brakes": "decelerazioni",
            "t/HR Z2": "hr_z2",
            "t/HR Z3": "hr_z3"
        }


        df.rename(
            columns=colonne,
            inplace=True
        )


        os.makedirs(
            "database",
            exist_ok=True
        )


        file_database = "database/gps_database.csv"


        if os.path.exists(file_database):

            vecchio = pd.read_csv(file_database)

            df = pd.concat(
                [vecchio, df],
                ignore_index=True
            )


        df.to_csv(
            file_database,
            index=False
        )


        st.success(
            "✅ Dati GPEXE importati correttamente"
        )
        
