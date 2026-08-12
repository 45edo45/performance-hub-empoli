"""
Football GPS Analytics
Column Mapping
Version 1.0
"""


# ==========================
# GPEXE -> DATABASE
# ==========================

COLUMN_MAP = {

    # ----------------------
    # PLAYER
    # ----------------------

    "athlete": "athlete",

    # ----------------------
    # VOLUME
    # ----------------------

    "duration (mm:ss)": "durata",

    "distance (m)": "distanza",

    # ----------------------
    # SPEED
    # ----------------------

    "max speed (km/h)": "max_speed",

    "distance/speed Z2 (m)": "z2",

    "distance/speed Z3 (m)": "z3",

    "distance/speed Z4 (m)": "z4",

    "speed events": "speed_events",

    # ----------------------
    # ACCELERATIONS
    # ----------------------

    "bursts": "bursts",

    "brakes": "brakes",

    # ----------------------
    # HEART RATE
    # ----------------------

    "time/HR Z2 (mm:ss)": "hr_z2",

    "time/HR Z3 (mm:ss)": "hr_z3",

    # ----------------------
    # MECHANICAL
    # ----------------------

    "high ext work+ (J/kg)": "high_ext_work_plus",

    "high ext work− (J/kg)": "high_ext_work_minus",

    "eccentric index": "eccentric_index",

    # ----------------------
    # METABOLIC
    # ----------------------

    "energy (J/kg)": "energy",

    "eq distance index (%)": "eq_distance_index",

    "avg MP (W/kg)": "avg_metabolic_power",

    "met power events": "met_power_events",

    "MPE rec avg time (s)": "mpe_rec_avg_time",

    "MPE rec avg met power (W/kg)": "mpe_rec_avg_power"

}