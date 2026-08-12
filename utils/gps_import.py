"""
Football GPS Analytics
GPEXE Import Module
Version 1.0
"""

import pandas as pd

from utils.column_mapping import COLUMN_MAP

from utils.database import (
    get_player_id,
    add_gps
)

def convert_numeric_columns(df):
    for colonna in df.columns:
        if df[colonna].dtype == "object":
            serie_convertita = (
                df[colonna]
                .astype(str)
                .str.replace(",", ".", regex=False)
            )

            valori_numerici = pd.to_numeric(
                serie_convertita,
                errors="coerce",
            )

            if valori_numerici.notna().any():
                df[colonna] = valori_numerici

    return df

# ==========================
# LETTURA FILE
# ==========================

def load_gpexe_file(file):

    df = pd.read_csv(file, sep=";")
    return df



# ==========================
# VALIDAZIONE COLONNE
# ==========================

def validate_gpexe(df):

    required = [
        "athlete",
        "duration (mm:ss)",
        "distance (m)",
        "max speed (km/h)"
    ]

    missing = []


    for col in required:

        if col not in df.columns:

            missing.append(col)


    if missing:

        return False, (
            "Colonne mancanti: "
            + ", ".join(missing)
        )


    return True, "File GPEXE valido"



# ==========================
# PREPARAZIONE DATI
# ==========================

def prepare_gpexe(df):

    df = convert_numeric_columns(df)

    columns = {

        "duration (mm:ss)": "durata",

        "distance (m)": "distanza",

        "max speed (km/h)": "max_speed",

        "distance/speed Z2 (m)": "z2",

        "distance/speed Z3 (m)": "z3",

        "distance/speed Z4 (m)": "z4",

        "speed events": "speed_events",

        "bursts": "bursts",

        "brakes": "brakes",

        "time/HR Z2 (mm:ss)": "hr_z2",

        "time/HR Z3 (mm:ss)": "hr_z3",

        "high ext workᐩ (J/kg)": "high_ext_work_plus",

        "high ext workᐨ (J/kg)": "high_ext_work_minus",

        "eccentric index": "eccentric_index",

        "energy (J/kg)": "energy",

        "eq distance index (%)": "eq_distance_index",

        "avg MP (W/kg)": "avg_metabolic_power",

        "met power events": "met_power_events",

        "MPE rec avg time (s)": "mpe_rec_avg_time",

        "MPE rec avg met power (W/kg)": "mpe_rec_avg_power"

        }


    df.rename(
        columns=columns,
        inplace=True
    )


    return df

    # ==========================
    # KPI CALCOLATI
    # ==========================


    df["hsr"] = (
        df["z3"]
        +
        df["z4"]
    )


    df["vhsr"] = df["z4"]



    # metri/minuto

    df["meters_min"] = (
        df["distanza"]
        /
        (convert_duration(df["durata"]))
    )


    return df



# ==========================
# CONVERSIONE TEMPO
# ==========================

def convert_duration(series):

    seconds = []

    for value in series:

        try:

            m, s = value.split(":")

            total = (
                int(m) * 60
                +
                int(s)
            )

            seconds.append(
                total / 60
            )


        except:

            seconds.append(
                0
            )


    return pd.Series(seconds)



# ==========================
# IMPORT DATABASE
# ==========================

def import_gps(df, seduta_id):

    importati = 0
    non_trovati = []

    for _, row in df.iterrows():

        athlete = str(row["athlete"]).replace("*", "").strip().upper()

        parti = athlete.split()

        cognome = parti[0]
        iniziale = parti[-1][0]

        giocatore_id = get_player_id(
            cognome,
            iniziale
        )

        if giocatore_id is None:

            non_trovati.append(athlete)
            continue

        add_gps(

            seduta_id,
            giocatore_id,

            row.get("durata"),
            row.get("distanza"),
            row.get("meters_min"),

            row.get("max_speed"),
            row.get("z2"),
            row.get("z3"),
            row.get("z4"),

            row.get("hsr"),
            row.get("vhsr"),

            row.get("speed_events"),

            row.get("bursts"),
            row.get("brakes"),

            row.get("high_ext_work_plus"),
            row.get("high_ext_work_minus"),
            row.get("eccentric_index"),

            row.get("energy"),
            row.get("eq_distance_index"),
            row.get("avg_metabolic_power"),

            row.get("met_power_events"),
            row.get("mpe_rec_avg_time"),
            row.get("mpe_rec_avg_power"),

            row.get("hr_z2"),
            row.get("hr_z3"),

            row.get("hsr_min"),
            row.get("sprint_min"),
            row.get("accel_min"),
            row.get("decel_min")
        )

        importati += 1

    return {
        "importati": importati,
        "non_trovati": non_trovati
    }