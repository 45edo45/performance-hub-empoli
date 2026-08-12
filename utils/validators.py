"""
Football GPS Analytics
Data Validators
Version: 0.2.0
"""

import pandas as pd


# =====================================
# CONTROLLO FILE CSV
# =====================================

def validate_csv(df: pd.DataFrame):

    required_columns = [

        "athlete",
        "duration (mm:ss)",
        "distance (m)",
        "max speed (km/h)",
        "distance/speed Z2 (m)",
        "distance/speed Z3 (m)",
        "distance/speed Z4 (m)",
        "speed events",
        "bursts",
        "brakes",
        "time/HR Z2 (mm:ss)",
        "time/HR Z3 (mm:ss)"

    ]


    missing = []


    for col in required_columns:

        if col not in df.columns:
            missing.append(col)


    if missing:

        return False, (
            "Colonne mancanti: "
            + ", ".join(missing)
        )


    return True, "CSV corretto"


# =====================================
# CONTROLLO VALORI VUOTI
# =====================================

def check_empty_values(df):

    empty = df.isnull().sum()

    empty = empty[empty > 0]


    if len(empty) > 0:

        return False, empty.to_dict()


    return True, {}



# =====================================
# CONTROLLO NUMERI
# =====================================

def convert_numeric_columns(df):

    numeric_columns = [

        "distance (m)",
        "max speed (km/h)",
        "distance/speed Z2 (m)",
        "distance/speed Z3 (m)",
        "distance/speed Z4 (m)",
        "speed events",
        "bursts",
        "brakes"

    ]

    for col in numeric_columns:

        if col in df.columns:

            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            )

    return df
