import streamlit as st
import pandas as pd

from utils.database import (
    add_session,
    get_sessions,
    get_gps_by_session,
    get_seasons,
    delete_session,
    get_player_cpet_profile,
    get_players_by_season,
    get_player_gps_history,
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

@st.cache_data(ttl=30)
def load_players_by_season(stagione_id):
    return get_players_by_season(stagione_id)

@st.cache_data(ttl=30)
def load_player_gps_history(
    giocatore_id,
    data_fine=None,
    giorni=28,
):
    return get_player_gps_history(
        giocatore_id,
        data_fine,
        giorni,
    )

def classifica_esposizione_soglia(percentuale):
    if pd.isna(percentuale):
        return "Dato non disponibile"

    if percentuale < 80:
        return "< 80% soglia"

    if percentuale < 90:
        return "80-90% soglia"

    if percentuale < 100:
        return "90-100% soglia"

    if percentuale < 110:
        return "100-110% soglia"

    return "> 110% soglia"


st.set_page_config(
    page_title="Allenamenti",
    page_icon="📅",
)


st.title("📅 Gestione Allenamenti")


# =========================
# SELEZIONE STAGIONE
# =========================

stagioni = get_seasons()

if not stagioni:
    st.warning("Nessuna stagione presente nel database.")
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


indice_default = list(
    opzioni_stagioni.keys()
).index(stagione_attiva)


stagione_scelta = st.selectbox(
    "Stagione",
    list(opzioni_stagioni.keys()),
    index=indice_default,
    key="stagione_allenamenti",
)


stagione_id = int(
    opzioni_stagioni[stagione_scelta]
)


# =========================
# NUOVA SEDUTA
# =========================

with st.expander(
    "➕ Nuova seduta",
    expanded=False,
):

    fase_stagione = st.selectbox(
        "Fase della stagione",
        [
            "Pre-stagione",
            "In stagione",
        ],
        key="fase_nuova_seduta",
    )


    if fase_stagione == "Pre-stagione":

        opzioni_microciclo = [
            "PS-1",
            "PS-2",
            "PS-3",
            "PS-4",
            "PS-5",
            "PS-6",
        ]

    else:

        opzioni_microciclo = [
            "MD",
            "MD-1",
            "MD-2",
            "MD-3",
            "MD-4",
            "MD+1",
            "MD+2",
        ]


    with st.form("nuova_seduta"):

        data = st.date_input("Data")

        md = st.selectbox(
            "Microciclo",
            opzioni_microciclo,
        )

        tipo = st.selectbox(
            "Tipo seduta",
            [
                "Allenamento",
                "Partita",
                "Recupero",
                "Palestra",
            ],
        )

        avversario = st.text_input(
            "Avversario"
        )

        luogo = st.selectbox(
            "Luogo",
            [
                "Centro Sportivo",
                "Casa",
                "Trasferta",
            ],
        )

        momento_giornata = st.selectbox(
            "Momento della giornata",
            [
               "Unica seduta",
               "Mattina",
               "Pomeriggio",
               "Sera"
            ]
        )

        note = st.text_area(
            "Note"
        )

        salva = st.form_submit_button(
            "Salva seduta"
        )


    if salva:

        add_session(
            str(data),
            md,
            tipo,
            avversario.strip(),
            luogo,
            stagione_id,
            fase_stagione,
            momento_giornata,
            note.strip(),
        )

        st.cache_data.clear()

        st.success(
            "✅ Seduta salvata"
        )

        st.rerun()


# =========================
# STORICO SEDUTE
# =========================

st.subheader("📋 Ultime 5 sedute")


sedute = get_sessions()


df = pd.DataFrame(
    sedute,
    columns=[
        "ID",
        "Data",
        "MD",
        "Tipo",
        "Avversario",
        "Luogo",
        "Note",
        "Stagione_ID",
        "Fase_stagione",
        "Momento_giornata",
    ],
)


if not df.empty:

    df["Stagione_ID"] = pd.to_numeric(
        df["Stagione_ID"],
        errors="coerce",
    )

    df = df[
        df["Stagione_ID"] == stagione_id
    ].copy()


if df.empty:

    st.info(
        "Non ci sono sedute salvate "
        "per questa stagione."
    )

else:

    df = df.sort_values(
        by=["Data", "ID"],
        ascending=[False, False],
    )

    # Tutte le sedute, usate per il menu di selezione
    df_tutte_sedute = df.copy()

    # Solo le ultime 5, usate per la tabella visibile
    df_ultime_5 = df.head(5).copy()

    df_visualizzazione = df_ultime_5.drop(
        columns=["Stagione_ID"]
    )


    st.dataframe(
        df_visualizzazione,
        use_container_width=True,
        hide_index=True,
    )


    # =========================
    # SELEZIONE SEDUTA
    # =========================

    st.subheader("🔎 Seleziona una seduta")


    opzioni_sedute = {}


    for _, riga in df_tutte_sedute.iterrows():

        momento = (
            riga["Momento_giornata"]
            if pd.notna(riga["Momento_giornata"])
            and riga["Momento_giornata"]
            else "Unica seduta"
        )

        descrizione = (
            f"{riga['Data']} | "
            f"{momento} | "
            f"{riga['Tipo']} | "
            f"{riga['MD']} | "
            f"ID {riga['ID']}"
        )


        if (
            pd.notna(riga["Avversario"])
            and riga["Avversario"]
        ):

            descrizione += (
                f" | {riga['Avversario']}"
            )

        opzioni_sedute[
            descrizione
        ] = int(riga["ID"])


    opzioni_selectbox = [
        "— Nessuna seduta selezionata —"
    ] + list(opzioni_sedute.keys())


    seduta_scelta = st.selectbox(
        "Seduta",
        opzioni_selectbox,
        index=0,
        key=f"seduta_storico_{stagione_id}",
    )


    if (
        seduta_scelta
        == "— Nessuna seduta selezionata —"
    ):

        st.info(
            "Seleziona una seduta per visualizzare "
            "dettagli e dati GPS."
        )

    else:

        seduta_id = opzioni_sedute[
            seduta_scelta
        ]


        dettaglio = df_tutte_sedute[
         df_tutte_sedute["ID"] == seduta_id
        ].iloc[0]


        # =========================
        # DETTAGLI SEDUTA
        # =========================

        st.markdown("### Dettagli seduta")


        col1, col2, col3 = st.columns(3)


        with col1:

            st.write(
                f"**Data:** "
                f"{dettaglio['Data']}"
            )

            st.write(
                f"**Microciclo:** "
                f"{dettaglio['MD']}"
            )

            st.write(
                f"**Fase:** "
                f"{dettaglio['Fase_stagione'] or '-'}"
            )


        with col2:

            st.write(
                f"**Tipo:** "
                f"{dettaglio['Tipo']}"
            )

            st.write(
                f"**Luogo:** "
                f"{dettaglio['Luogo']}"
            )


        with col3:

            avversario_dettaglio = (
                dettaglio["Avversario"]
                if (
                    pd.notna(
                        dettaglio["Avversario"]
                    )
                    and dettaglio["Avversario"]
                )
                else "-"
            )

            st.write(
                f"**Avversario:** "
                f"{avversario_dettaglio}"
            )

            st.write(
                f"**ID seduta:** "
                f"{seduta_id}"
            )


        note_dettaglio = (
            dettaglio["Note"]
            if (
                pd.notna(dettaglio["Note"])
                and dettaglio["Note"]
            )
            else "-"
        )


        st.write(
            f"**Note:** "
            f"{note_dettaglio}"
        )


        # =========================
        # DATI GPS
        # =========================

        st.subheader(
            "📡 Dati GPS della seduta"
        )


        dati_gps = get_gps_by_session(
            seduta_id
        )


        if not dati_gps:

            st.info(
                "Nessun dato GPS collegato "
                "a questa seduta."
            )

        else:

            df_gps = pd.DataFrame(
                dati_gps
            )


            df_gps = df_gps.replace(
                ["", "None", "nan"],
                pd.NA,
            )

            # ==========================================
            # COLLEGAMENTO GPS CON PROFILO CPET
            # ==========================================

            data_seduta_cpet = None

            righe_seduta_cpet = df_tutte_sedute[
                df_tutte_sedute["ID"] == seduta_id
            ]

            if not righe_seduta_cpet.empty:
                data_seduta_cpet = str(
                    righe_seduta_cpet.iloc[0]["Data"]
                )


            velocita_soglia_lista = []
            velocita_massima_cpet_lista = []
            percentuale_soglia_lista = []
            percentuale_max_cpet_lista = []
            fascia_soglia_lista = []


            for _, riga_gps in df_gps.iterrows():
                giocatore_id_gps = riga_gps.get(
                    "giocatore_id"
                )

                max_speed_gps = pd.to_numeric(
                    riga_gps.get("max_speed"),
                    errors="coerce",
                )

                velocita_soglia = None
                velocita_massima_cpet = None
                percentuale_soglia = None
                percentuale_max_cpet = None

                if pd.notna(giocatore_id_gps):
                    profilo_cpet = load_player_cpet_profile(
                        int(giocatore_id_gps),
                        data_seduta_cpet,
                    )

                    dato_soglia = profilo_cpet.get(
                    "Velocità soglia anaerobica"
                    )  

                    dato_max_cpet = profilo_cpet.get(
                        "Velocità massima CPET"
                    )

                    if dato_soglia:
                        velocita_soglia = float(
                            dato_soglia["valore"]
                        )

                    if dato_max_cpet:
                        velocita_massima_cpet = float(
                            dato_max_cpet["valore"]
                        )

                if (
                    pd.notna(max_speed_gps)
                    and velocita_soglia is not None
                    and velocita_soglia > 0
                ):
                    percentuale_soglia = (
                        float(max_speed_gps)
                        / velocita_soglia
                        * 100
                    )

                if (
                    pd.notna(max_speed_gps)
                    and velocita_massima_cpet is not None
                    and velocita_massima_cpet > 0
                ):
                    percentuale_max_cpet = (
                        float(max_speed_gps)
                        / velocita_massima_cpet
                        * 100
                    )

                velocita_soglia_lista.append(
                    velocita_soglia
                )

                velocita_massima_cpet_lista.append(
                    velocita_massima_cpet
                )

                percentuale_soglia_lista.append(
                    percentuale_soglia
                )

                percentuale_max_cpet_lista.append(
                    percentuale_max_cpet
                )

                fascia_soglia_lista.append(
                classifica_esposizione_soglia(
                        percentuale_soglia
                    )
                )


            df_gps[
                "Soglia anaerobica km/h"
            ] = velocita_soglia_lista

            df_gps[
                "Velocità massima CPET km/h"
            ] = velocita_massima_cpet_lista

            df_gps[
                "% max speed / soglia"
            ] = percentuale_soglia_lista

            df_gps[
                "% max speed / max CPET"
            ] = percentuale_max_cpet_lista

            df_gps[
                "Fascia esposizione soglia"
            ] = fascia_soglia_lista


            df_gps[
                "Soglia anaerobica km/h"
            ] = pd.to_numeric(
                df_gps["Soglia anaerobica km/h"],
                errors="coerce",
            ).round(2)

            df_gps[
                "Velocità massima CPET km/h"
            ] = pd.to_numeric(
                df_gps["Velocità massima CPET km/h"],
                errors="coerce",
            ).round(2)

            df_gps[
                "% max speed / soglia"
            ] = pd.to_numeric(
                df_gps["% max speed / soglia"],
                errors="coerce",
            ).round(1)

            df_gps[
                "% max speed / max CPET"
            ] = pd.to_numeric(
                df_gps["% max speed / max CPET"],
                errors="coerce",
            ).round(1)
             
            # ==========================================
            # VISTA SINTETICA PROFESSIONALE CPET + GPS
            # ==========================================

            st.markdown(
                "### 🫀 Sintesi cardiovascolare della seduta"
            )

            rosa_seduta = load_players_by_season(
                stagione_id
            )

            nomi_giocatori = {
                int(giocatore["id"]): (
                    f"{giocatore['cognome']} "
                    f"{giocatore['nome']}"
                )
                for giocatore in rosa_seduta
            }

            df_sintesi_cpet = df_gps.copy()

            df_sintesi_cpet[
                "Giocatore_ID"
            ] = pd.to_numeric(
                df_sintesi_cpet["giocatore_id"],
                errors="coerce",
            )

            giocatore_id_numerico = pd.to_numeric(
                df_sintesi_cpet["giocatore_id"],
                errors="coerce",
            )

            df_sintesi_cpet["Giocatore"] = (
                giocatore_id_numerico.map(
                    nomi_giocatori
                )
            )

            giocatore_id_testo = (
                giocatore_id_numerico
                .astype("Int64")
                .astype(str)
            )

            df_sintesi_cpet["Giocatore"] = (
                df_sintesi_cpet["Giocatore"]
                .fillna(
                    "Giocatore ID "
                    + giocatore_id_testo
                )
            )

            df_sintesi_cpet[
                "Max speed GPS km/h"
            ] = pd.to_numeric(
                df_sintesi_cpet["max_speed"],
                errors="coerce",
            ).round(2)

            # ==========================================
            # VOLUME AD ALTA INTENSITÀ
            # ==========================================

            colonne_numeriche_sintesi = [
                "hsr",
                "vhsr",
                "sprint",
                "hsr_min",
                "sprint_min",
                "accelerazioni",
                "decelerazioni",
                "durata",
                "meters_min",
            ]

            for colonna in colonne_numeriche_sintesi:
                if colonna in df_sintesi_cpet.columns:
                    df_sintesi_cpet[colonna] = (
                        pd.to_numeric(
                            df_sintesi_cpet[colonna],
                            errors="coerce",
                        )
                    )

            if "hsr" in df_sintesi_cpet.columns:
                df_sintesi_cpet[
                    "HSR"
                ] = df_sintesi_cpet["hsr"].round(1)

            if "vhsr" in df_sintesi_cpet.columns:
                df_sintesi_cpet[
                    "VHSR"
                ] = df_sintesi_cpet["vhsr"].round(1)

            if "sprint" in df_sintesi_cpet.columns:
                df_sintesi_cpet[
                    "Sprint"
                ] = df_sintesi_cpet["sprint"].round(1)

            if "hsr_min" in df_sintesi_cpet.columns:
                df_sintesi_cpet[
                    "HSR/min"
                ] = df_sintesi_cpet["hsr_min"].round(2)

            if "sprint_min" in df_sintesi_cpet.columns:
                df_sintesi_cpet[
                    "Sprint/min"
                ] = df_sintesi_cpet[
                    "sprint_min"
                ].round(2)

            if "accelerazioni" in df_sintesi_cpet.columns:
                df_sintesi_cpet[
                    "Accelerazioni"
                ] = df_sintesi_cpet[
                    "accelerazioni"
                ].round(0)

            if "decelerazioni" in df_sintesi_cpet.columns:
                df_sintesi_cpet[
                    "Decelerazioni"
                ] = df_sintesi_cpet[
                    "decelerazioni"
                ].round(0)

            df_sintesi_cpet[
                "Profilo CPET"
            ] = (
                df_sintesi_cpet[
                    "Soglia anaerobica km/h"
                ].notna()
                & df_sintesi_cpet[
                    "Velocità massima CPET km/h"
                ].notna()
            ).map(
                {
                    True: "Disponibile",
                    False: "Mancante",
                }
            )

            def valuta_esposizione_cpet(
                percentuale,
            ):
                if pd.isna(percentuale):
                    return "Profilo non disponibile"

                if percentuale < 80:
                    return "Esposizione bassa"

                if percentuale < 100:
                    return "Esposizione moderata"

                if percentuale < 120:
                    return "Sopra soglia"

                if percentuale < 150:
                    return "Esposizione elevata"

                return "Esposizione molto elevata"

            df_sintesi_cpet[
                "Valutazione"
            ] = df_sintesi_cpet[
                "% max speed / soglia"
            ].apply(
                valuta_esposizione_cpet
            )

            colonne_sintesi_cpet = [
                "Giocatore_ID",
                "Giocatore",
                "Max speed GPS km/h",
                "Soglia anaerobica km/h",
                "Velocità massima CPET km/h",
                "% max speed / soglia",
                "% max speed / max CPET",
                "HSR",
                "VHSR",
                "Sprint",
                "HSR/min",
                "Sprint/min",
                "Accelerazioni",
                "Decelerazioni",
                "Valutazione",
                "Profilo CPET",
            ]

            colonne_sintesi_presenti = [
                colonna
                for colonna in colonne_sintesi_cpet
                if colonna
                in df_sintesi_cpet.columns
            ]

            df_sintesi_cpet = (
                df_sintesi_cpet[
                    colonne_sintesi_presenti
                ]
                .sort_values(
                    by="% max speed / soglia",
                    ascending=False,
                    na_position="last",
                )
                .reset_index(drop=True)
            )

            giocatori_con_cpet = int(
                (
                    df_sintesi_cpet[
                        "Profilo CPET"
                    ]
                    == "Disponibile"
                ).sum()
            )

            giocatori_senza_cpet = int(
                (
                    df_sintesi_cpet[
                        "Profilo CPET"
                    ]
                    == "Mancante"
                ).sum()
            )

            percentuali_valide = pd.to_numeric(
                df_sintesi_cpet[
                    "% max speed / soglia"
                ],
                errors="coerce",
            ).dropna()

            col_cpet_1, col_cpet_2, col_cpet_3 = (
                st.columns(3)
            )

            with col_cpet_1:
                st.metric(
                    "Giocatori con profilo CPET",
                    giocatori_con_cpet,
                )

            with col_cpet_2:
                st.metric(
                    "Profili CPET mancanti",
                    giocatori_senza_cpet,
                )

            with col_cpet_3:
                if percentuali_valide.empty:
                    st.metric(
                        "Media esposizione alla soglia",
                        "—",
                    )
                else:
                    st.metric(
                        "Media esposizione alla soglia",
                        (
                            f"{percentuali_valide.mean():.1f}%"
                        ),
                    )

            st.dataframe(
                df_sintesi_cpet,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Giocatore_ID": None,
                    "Giocatore": (
                        st.column_config.TextColumn(
                            "Giocatore",
                            width="medium",
                        )
                    ),
                    "Max speed GPS km/h": (
                        st.column_config.NumberColumn(
                            "Max speed GPS",
                            format="%.2f km/h",
                        )
                    ),
                    "Soglia anaerobica km/h": (
                        st.column_config.NumberColumn(
                            "Soglia anaerobica",
                            format="%.2f km/h",
                        )
                    ),
                    "Velocità massima CPET km/h": (
                        st.column_config.NumberColumn(
                            "Velocità max CPET",
                            format="%.2f km/h",
                        )
                    ),
                    "% max speed / soglia": (
                        st.column_config.ProgressColumn(
                            "% rispetto alla soglia",
                            format="%.1f%%",
                            min_value=0,
                            max_value=250,
                        )
                    ),
                    "% max speed / max CPET": (
                        st.column_config.ProgressColumn(
                            "% rispetto al max CPET",
                            format="%.1f%%",
                            min_value=0,
                            max_value=200,
                        )
                    ),
                                        "HSR": (
                        st.column_config.NumberColumn(
                            "HSR",
                            format="%.1f",
                        )
                    ),
                    "VHSR": (
                        st.column_config.NumberColumn(
                            "VHSR",
                            format="%.1f",
                        )
                    ),
                    "Sprint": (
                        st.column_config.NumberColumn(
                            "Sprint",
                            format="%.1f",
                        )
                    ),
                    "HSR/min": (
                        st.column_config.NumberColumn(
                            "HSR/min",
                            format="%.2f",
                        )
                    ),
                    "Sprint/min": (
                        st.column_config.NumberColumn(
                            "Sprint/min",
                            format="%.2f",
                        )
                    ),
                    "Accelerazioni": (
                        st.column_config.NumberColumn(
                            "Accelerazioni",
                            format="%.0f",
                        )
                    ),
                    "Decelerazioni": (
                        st.column_config.NumberColumn(
                            "Decelerazioni",
                            format="%.0f",
                        )
                    ),
                    "Valutazione": (
                        st.column_config.TextColumn(
                            "Valutazione",
                            width="medium",
                        )
                    ),
                    "Profilo CPET": (
                        st.column_config.TextColumn(
                            "Profilo CPET",
                            width="small",
                        )
                    ),
                },
            )

            # ==========================================
            # DETTAGLIO INDIVIDUALE CPET + GPS
            # ==========================================

            st.markdown(
                "### 👤 Dettaglio individuale"
            )

            giocatori_sintesi = (
                df_sintesi_cpet["Giocatore"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )

            giocatori_sintesi = sorted(
                giocatori_sintesi
            )

            if giocatori_sintesi:
                giocatore_dettaglio = st.selectbox(
                    "Giocatore da analizzare",
                    giocatori_sintesi,
                    key=(
                        f"giocatore_dettaglio_cpet_"
                        f"{seduta_id}"
                    ),
                )

                riga_dettaglio_cpet = (
                    df_sintesi_cpet[
                        df_sintesi_cpet[
                            "Giocatore"
                        ]
                        == giocatore_dettaglio
                    ]
                )

                if not riga_dettaglio_cpet.empty:
                    riga_dettaglio_cpet = (
                        riga_dettaglio_cpet.iloc[0]
                    )

                    giocatore_id_dettaglio = (
                        pd.to_numeric(
                            riga_dettaglio_cpet.get(
                                "Giocatore_ID"
                            ),
                            errors="coerce",
                        )
                    )

                    max_speed_individuale = (
                        pd.to_numeric(
                            riga_dettaglio_cpet.get(
                                "Max speed GPS km/h"
                            ),
                            errors="coerce",
                        )
                    )

                    soglia_individuale = (
                        pd.to_numeric(
                            riga_dettaglio_cpet.get(
                                "Soglia anaerobica km/h"
                            ),
                            errors="coerce",
                        )
                    )

                    max_cpet_individuale = (
                        pd.to_numeric(
                            riga_dettaglio_cpet.get(
                                "Velocità massima CPET km/h"
                            ),
                            errors="coerce",
                        )
                    )

                    percentuale_soglia_individuale = (
                        pd.to_numeric(
                            riga_dettaglio_cpet.get(
                                "% max speed / soglia"
                            ),
                            errors="coerce",
                        )
                    )

                    percentuale_max_cpet_individuale = (
                        pd.to_numeric(
                            riga_dettaglio_cpet.get(
                                "% max speed / max CPET"
                            ),
                            errors="coerce",
                        )
                    )

                    hsr_individuale = pd.to_numeric(
                        riga_dettaglio_cpet.get("HSR"),
                        errors="coerce",
                    )

                    vhsr_individuale = pd.to_numeric(
                        riga_dettaglio_cpet.get("VHSR"),
                        errors="coerce",
                    )

                    sprint_individuale = pd.to_numeric(
                        riga_dettaglio_cpet.get("Sprint"),
                        errors="coerce",
                    )

                    hsr_min_individuale = pd.to_numeric(
                        riga_dettaglio_cpet.get("HSR/min"),
                        errors="coerce",
                    )

                    sprint_min_individuale = (
                        pd.to_numeric(
                            riga_dettaglio_cpet.get(
                                "Sprint/min"
                            ),
                            errors="coerce",
                        )
                    )

                    accelerazioni_individuali = (
                        pd.to_numeric(
                            riga_dettaglio_cpet.get(
                                "Accelerazioni"
                            ),
                            errors="coerce",
                        )
                    )

                    decelerazioni_individuali = (
                        pd.to_numeric(
                            riga_dettaglio_cpet.get(
                                "Decelerazioni"
                            ),
                            errors="coerce",
                        )
                    )

                    col_det_1, col_det_2, col_det_3 = (
                        st.columns(3)
                    )

                    with col_det_1:
                        st.metric(
                            "Max speed GPS",
                            (
                                f"{max_speed_individuale:.2f} "
                                "km/h"
                                if pd.notna(
                                    max_speed_individuale
                                )
                                else "—"
                            ),
                        )

                    with col_det_2:
                        st.metric(
                            "Soglia anaerobica",
                            (
                                f"{soglia_individuale:.2f} "
                                "km/h"
                                if pd.notna(
                                    soglia_individuale
                                )
                                else "—"
                            ),
                        )

                    with col_det_3:
                        st.metric(
                            "Velocità massima CPET",
                            (
                                f"{max_cpet_individuale:.2f} "
                                "km/h"
                                if pd.notna(
                                    max_cpet_individuale
                                )
                                else "—"
                            ),
                        )

                    col_det_4, col_det_5 = (
                        st.columns(2)
                    )

                    with col_det_4:
                        st.metric(
                            "% rispetto alla soglia",
                            (
                                f"{percentuale_soglia_individuale:.1f}%"
                                if pd.notna(
                                    percentuale_soglia_individuale
                                )
                                else "—"
                            ),
                        )

                    with col_det_5:
                        st.metric(
                            "% rispetto al max CPET",
                            (
                                f"{percentuale_max_cpet_individuale:.1f}%"
                                if pd.notna(
                                    percentuale_max_cpet_individuale
                                )
                                else "—"
                            ),
                        )
                        
                    st.markdown(
                        "#### Volume ad alta intensità"
                    )

                    col_vol_1, col_vol_2, col_vol_3 = (
                        st.columns(3)
                    )

                    with col_vol_1:
                        st.metric(
                            "HSR",
                            (
                                f"{hsr_individuale:.1f}"
                                if pd.notna(
                                    hsr_individuale
                                )
                                else "—"
                            ),
                        )

                    with col_vol_2:
                        st.metric(
                            "VHSR",
                            (
                                f"{vhsr_individuale:.1f}"
                                if pd.notna(
                                    vhsr_individuale
                                )
                                else "—"
                            ),
                        )

                    with col_vol_3:
                        st.metric(
                            "Sprint",
                            (
                                f"{sprint_individuale:.1f}"
                                if pd.notna(
                                    sprint_individuale
                                )
                                else "—"
                            ),
                        )

                    col_vol_4, col_vol_5 = st.columns(2)

                    with col_vol_4:
                        st.metric(
                            "HSR/min",
                            (
                                f"{hsr_min_individuale:.2f}"
                                if pd.notna(
                                    hsr_min_individuale
                                )
                                else "—"
                            ),
                        )

                    with col_vol_5:
                        st.metric(
                            "Sprint/min",
                            (
                                f"{sprint_min_individuale:.2f}"
                                if pd.notna(
                                    sprint_min_individuale
                                )
                                else "—"
                            ),
                        )

                    st.markdown(
                        "#### Carico neuromuscolare esterno"
                    )

                    col_neuro_1, col_neuro_2 = (
                        st.columns(2)
                    )

                    with col_neuro_1:
                        st.metric(
                            "Accelerazioni",
                            (
                                f"{accelerazioni_individuali:.0f}"
                                if pd.notna(
                                    accelerazioni_individuali
                                )
                                else "—"
                            ),
                        )

                    with col_neuro_2:
                        st.metric(
                            "Decelerazioni",
                            (
                                f"{decelerazioni_individuali:.0f}"
                                if pd.notna(
                                    decelerazioni_individuali
                                )
                                else "—"
                            ),
                        )

                    st.markdown(
                        "#### Interpretazione della seduta"
                    )

                    indicatori_alti = 0

                    if (
                        pd.notna(
                            percentuale_max_cpet_individuale
                        )
                        and percentuale_max_cpet_individuale
                        >= 100
                    ):
                        indicatori_alti += 1

                    if (
                        pd.notna(hsr_min_individuale)
                        and hsr_min_individuale > 0
                    ):
                        indicatori_alti += 1

                    if (
                        pd.notna(sprint_min_individuale)
                        and sprint_min_individuale > 0
                    ):
                        indicatori_alti += 1

                    if indicatori_alti >= 3:
                        st.success(
                            "La seduta ha combinato "
                            "un'elevata esposizione di velocità "
                            "con volumi di corsa ad alta intensità."
                        )

                    elif indicatori_alti == 2:
                        st.info(
                            "La seduta ha prodotto uno stimolo "
                            "significativo ad alta intensità, "
                            "ma non completo in tutti gli indicatori."
                        )

                    elif indicatori_alti == 1:
                        st.info(
                            "È presente uno stimolo specifico "
                            "ad alta intensità, con volume "
                            "complessivamente contenuto."
                        )

                    else:
                        st.info(
                            "La seduta non mostra esposizioni "
                            "rilevanti negli indicatori ad alta "
                            "intensità disponibili."
                        )

                    # ==========================================
                    # BENCHMARK INDIVIDUALE ULTIMI 28 GIORNI
                    # ==========================================

                    st.markdown(
                        "#### Benchmark individuale - ultimi 28 giorni"
                    )

                    if pd.isna(giocatore_id_dettaglio):
                        st.warning(
                            "ID giocatore non disponibile."
                        )

                    else:
                        storico_gps = load_player_gps_history(
                            int(giocatore_id_dettaglio),
                            data_seduta_cpet,
                            28,
                        )

                        df_storico_gps = pd.DataFrame(
                            storico_gps
                        )

                        if df_storico_gps.empty:
                            st.info(
                                "Non ci sono sedute GPS sufficienti "
                                "nei 28 giorni precedenti."
                            )

                        else:
                            colonne_benchmark = {
                                "max_speed": (
                                    "Max speed GPS",
                                    max_speed_individuale,
                                ),
                                "hsr": (
                                    "HSR",
                                    hsr_individuale,
                                ),
                                "vhsr": (
                                    "VHSR",
                                    vhsr_individuale,
                                ),
                                "sprint": (
                                    "Sprint",
                                    sprint_individuale,
                                ),
                                "hsr_min": (
                                    "HSR/min",
                                    hsr_min_individuale,
                                ),
                                "sprint_min": (
                                    "Sprint/min",
                                    sprint_min_individuale,
                                ),
                                "accelerazioni": (
                                    "Accelerazioni",
                                    accelerazioni_individuali,
                                ),
                                "decelerazioni": (
                                    "Decelerazioni",
                                    decelerazioni_individuali,
                                ),
                            }

                            righe_benchmark = []

                            for (
                                colonna_storico,
                                dati_indicatore,
                            ) in colonne_benchmark.items():

                                nome_indicatore = (
                                    dati_indicatore[0]
                                )

                                valore_seduta = pd.to_numeric(
                                    dati_indicatore[1],
                                    errors="coerce",
                                )

                                if (
                                    colonna_storico
                                    not in df_storico_gps.columns
                                ):
                                    continue

                                serie_storica = pd.to_numeric(
                                    df_storico_gps[
                                        colonna_storico
                                    ],
                                    errors="coerce",
                                ).dropna()

                                if serie_storica.empty:
                                    continue

                                media_28_giorni = (
                                    serie_storica.mean()
                                )

                                massimo_28_giorni = (
                                    serie_storica.max()
                                )

                                minimo_28_giorni = (
                                    serie_storica.min()
                                )

                                numero_sedute = int(
                                    serie_storica.count()
                                )

                                scostamento_percentuale = pd.NA

                                if (
                                    pd.notna(valore_seduta)
                                    and media_28_giorni != 0
                                ):
                                    scostamento_percentuale = (
                                        (
                                            valore_seduta
                                            - media_28_giorni
                                        )
                                        / media_28_giorni
                                        * 100
                                    )

                                righe_benchmark.append(
                                    {
                                        "Indicatore": nome_indicatore,
                                        "Seduta selezionata": (
                                            valore_seduta
                                        ),
                                        "Media 28 giorni": (
                                            media_28_giorni
                                        ),
                                        "Massimo 28 giorni": (
                                            massimo_28_giorni
                                        ),
                                        "Minimo 28 giorni": (
                                            minimo_28_giorni
                                        ),
                                        "Scostamento dalla media %": (
                                            scostamento_percentuale
                                        ),
                                        "Sedute considerate": (
                                            numero_sedute
                                        ),
                                    }
                                )

                            df_benchmark = pd.DataFrame(
                                righe_benchmark
                            )

                            if df_benchmark.empty:
                                st.info(
                                    "Non sono disponibili indicatori "
                                    "utilizzabili per il benchmark."
                                )

                            else:
                                colonne_da_arrotondare = [
                                    "Seduta selezionata",
                                    "Media 28 giorni",
                                    "Massimo 28 giorni",
                                    "Minimo 28 giorni",
                                    "Scostamento dalla media %",
                                ]

                                for colonna in (
                                    colonne_da_arrotondare
                                ):
                                    df_benchmark[colonna] = (
                                        pd.to_numeric(
                                            df_benchmark[colonna],
                                            errors="coerce",
                                        ).round(2)
                                    )

                                st.dataframe(
                                    df_benchmark,
                                    use_container_width=True,
                                    hide_index=True,
                                    column_config={
                                        "Indicatore": (
                                            st.column_config.TextColumn(
                                                "Indicatore"
                                            )
                                        ),
                                        "Seduta selezionata": (
                                            st.column_config.NumberColumn(
                                                "Seduta",
                                                format="%.2f",
                                            )
                                        ),
                                        "Media 28 giorni": (
                                            st.column_config.NumberColumn(
                                                "Media 28 gg",
                                                format="%.2f",
                                            )
                                        ),
                                        "Massimo 28 giorni": (
                                            st.column_config.NumberColumn(
                                                "Massimo 28 gg",
                                                format="%.2f",
                                            )
                                        ),
                                        "Minimo 28 giorni": (
                                            st.column_config.NumberColumn(
                                                "Minimo 28 gg",
                                                format="%.2f",
                                            )
                                        ),
                                        "Scostamento dalla media %": (
                                            st.column_config.NumberColumn(
                                                "Scostamento",
                                                format="%.1f%%",
                                            )
                                        ),
                                        "Sedute considerate": (
                                            st.column_config.NumberColumn(
                                                "N. sedute",
                                                format="%d",
                                            )
                                        ),
                                    },
                                )

                    valutazione_individuale = (
                        riga_dettaglio_cpet.get(
                            "Valutazione"
                        )
                    )

                    profilo_individuale = (
                        riga_dettaglio_cpet.get(
                            "Profilo CPET"
                        )
                    )

                    if (
                        profilo_individuale
                        == "Mancante"
                    ):
                        st.warning(
                            "Il giocatore non dispone di "
                            "un profilo CPET completo."
                        )

                    elif (
                        valutazione_individuale
                        == "Esposizione bassa"
                    ):
                        st.info(
                            "La velocità massima della seduta "
                            "è rimasta sensibilmente sotto il "
                            "riferimento di soglia individuale."
                        )

                    elif (
                        valutazione_individuale
                        == "Esposizione moderata"
                    ):
                        st.info(
                            "La velocità massima della seduta "
                            "si è avvicinata alla soglia "
                            "anaerobica individuale."
                        )

                    elif (
                        valutazione_individuale
                        == "Sopra soglia"
                    ):
                        st.success(
                            "Il giocatore ha raggiunto una "
                            "velocità superiore alla soglia "
                            "anaerobica individuale."
                        )

                    elif (
                        valutazione_individuale
                        in {
                            "Esposizione elevata",
                            "Esposizione molto elevata",
                        }
                    ):
                        st.success(
                            "La seduta ha previsto esposizioni "
                            "di velocità nettamente superiori "
                            "alla soglia anaerobica."
                        )

            st.caption(
                "Le percentuali confrontano il picco di "
                "velocità GPS con i riferimenti del test "
                "cardiopolmonare. Non rappresentano il tempo "
                "effettivamente trascorso nelle diverse "
                "zone metaboliche."
            )


            df_report = df_gps.dropna(
                axis=1,
                how="all",
            )


            colonne_da_nascondere = [
                "id",
                "seduta_id",
                "giocatore_id",
            ]


            df_report = df_report.drop(
                columns=[
                    colonna
                    for colonna
                    in colonne_da_nascondere
                    if colonna
                    in df_report.columns
                ]
            )


            colonne_prioritarie = [
                "cognome",
                "nome",
                "durata",
                "distanza",
                "meters_min",
                "max_speed",
                "hsr",
                "accelerazioni",
                "decelerazioni",
            ]


            colonne_ordinate = [
                colonna
                for colonna
                in colonne_prioritarie
                if colonna
                in df_report.columns
            ]


            altre_colonne = [
                colonna
                for colonna
                in df_report.columns
                if colonna
                not in colonne_ordinate
            ]


            df_report = df_report[
                colonne_ordinate
                + altre_colonne
            ]


            st.write(
                f"Giocatori nel report: "
                f"{len(df_report)}"
            )


            st.dataframe(
                df_report,
                use_container_width=True,
                hide_index=True,
            )


        # =========================
        # ELIMINAZIONE SEDUTA
        # =========================

        with st.expander(
            "🗑️ Elimina seduta",
            expanded=False,
        ):

            st.error(
                "Questa operazione eliminerà "
                "definitivamente la seduta e tutti "
                "i dati GPS collegati."
            )


            conferma_eliminazione = st.checkbox(
                "Confermo l'eliminazione definitiva "
                "della seduta",
                key=(
                    f"conferma_elimina_"
                    f"seduta_{seduta_id}"
                ),
            )


            if st.button(
                "Elimina seduta",
                type="primary",
                disabled=not conferma_eliminazione,
                key=(
                    f"elimina_seduta_"
                    f"{seduta_id}"
                ),
            ):

                delete_session(
                    seduta_id
                )

                st.cache_data.clear()

                st.success(
                    "Seduta e dati GPS eliminati."
                )

                st.rerun()