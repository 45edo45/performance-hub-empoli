"""
Football GPS Analytics
Backup Manager
Version: 0.2.0
"""

import shutil
from pathlib import Path
from datetime import datetime

from config import DB_PATH, BACKUP_DIR, KEEP_BACKUPS


# ==========================================
# CREAZIONE BACKUP
# ==========================================

def create_backup():

    if not DB_PATH.exists():
        return False

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    backup_file = (
        BACKUP_DIR /
        f"football_backup_{timestamp}.db"
    )

    shutil.copy2(
        DB_PATH,
        backup_file
    )

    clean_old_backups()

    return backup_file


# ==========================================
# LISTA BACKUP
# ==========================================

def list_backups():

    backups = sorted(
        BACKUP_DIR.glob("*.db"),
        reverse=True
    )

    return backups


# ==========================================
# CANCELLA BACKUP VECCHI
# ==========================================

def clean_old_backups():

    backups = list_backups()

    if len(backups) <= KEEP_BACKUPS:
        return

    for old_backup in backups[KEEP_BACKUPS:]:

        old_backup.unlink()


# ==========================================
# RIPRISTINO BACKUP
# ==========================================

def restore_backup(backup_file):

    backup_file = Path(backup_file)

    if not backup_file.exists():
        return False


    shutil.copy2(
        backup_file,
        DB_PATH
    )

    return True
