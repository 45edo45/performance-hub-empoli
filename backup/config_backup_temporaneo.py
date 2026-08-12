"""
=========================================
Football GPS Analytics
Configuration File
Version: 0.2.0
=========================================
"""

from pathlib import Path

# ==========================================================
# SOFTWARE
# ==========================================================

APP_NAME = "Football GPS Analytics"
APP_SUBTITLE = "Performance Monitoring Suite"
APP_VERSION = "0.2.0"

# ==========================================================
# SQUADRA
# ==========================================================

TEAM_NAME = "Empoli Primavera"
SEASON = "2026/27"

# ==========================================================
# CARTELLE
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent

DATABASE_DIR = BASE_DIR / "database"
BACKUP_DIR = BASE_DIR / "backup"
ASSETS_DIR = BASE_DIR / "assets"
LOGS_DIR = BASE_DIR / "logs"
DOCS_DIR = BASE_DIR / "docs"

# Creazione automatica cartelle
for folder in (
    DATABASE_DIR,
    BACKUP_DIR,
    ASSETS_DIR,
    LOGS_DIR,
    DOCS_DIR,
):
    folder.mkdir(exist_ok=True)

# ==========================================================
# DATABASE
# ==========================================================

DB_NAME = "football.db"
DB_PATH = DATABASE_DIR / DB_NAME

# ==========================================================
# COLORI
# ==========================================================

PRIMARY_COLOR = "#005BAC"
SECONDARY_COLOR = "#00AEEF"
SUCCESS_COLOR = "#2E8B57"
WARNING_COLOR = "#F4B400"
DANGER_COLOR = "#D93025"

# ==========================================================
# RUOLI
# ==========================================================

ROLES = [
    "Portiere",
    "Difensore",
    "Centrocampista",
    "Esterno",
    "Attaccante"
]

# ==========================================================
# STATI GIOCATORE
# ==========================================================

PLAYER_STATUS = [
    "Disponibile",
    "Gestione Carico",
    "Personalizzato",
    "Infortunato",
    "Assente"
]

# ==========================================================
# TIPO SEDUTA
# ==========================================================

SESSION_TYPES = [
    "Allenamento",
    "Partita",
    "Test"
]

# ==========================================================
# TAG SEDUTE
# ==========================================================

SESSION_TAGS = [
    "Forza",
    "Velocità",
    "Possesso",
    "Tattica",
    "Recupero",
    "Alta Intensità",
    "Rifinitura"
]

# ==========================================================
# PARAMETRI GPS
# ==========================================================

GPS_PARAMETERS = [
    "durata",
    "distanza",
    "max_speed",
    "sprint_distance",
    "z2",
    "z3",
    "z4",
    "speed_events",
    "accelerazioni",
    "decelerazioni",
    "hr_z2",
    "hr_z3",
]

# ==========================================================
# BENCHMARK DEFAULT
# (modificabili dal software)
# ==========================================================

DEFAULT_BENCHMARK = {

    "Portiere": {
        "distanza": 4500,
        "max_speed": 24,
        "accelerazioni": 15,
        "decelerazioni": 15
    },

    "Difensore": {
        "distanza": 8000,
        "max_speed": 31,
        "accelerazioni": 45,
        "decelerazioni": 45
    },

    "Centrocampista": {
        "distanza": 9500,
        "max_speed": 30,
        "accelerazioni": 55,
        "decelerazioni": 55
    },

    "Esterno": {
        "distanza": 9200,
        "max_speed": 33,
        "accelerazioni": 60,
        "decelerazioni": 60
    },

    "Attaccante": {
        "distanza": 8500,
        "max_speed": 32,
        "accelerazioni": 50,
        "decelerazioni": 50
    }

}

# ==========================================================
# BACKUP
# ==========================================================

AUTO_BACKUP = True
KEEP_BACKUPS = 30

# ==========================================================
# REPORT
# ==========================================================

REPORT_TITLE = "Football GPS Analytics Report"

# ==========================================================
# DEBUG
# ==========================================================

DEBUG = False

