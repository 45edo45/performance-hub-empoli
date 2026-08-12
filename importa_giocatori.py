import pandas as pd

from utils.database import add_player, create_database


create_database()


file_csv = "database/giocatori.csv"


df = pd.read_csv(file_csv)


for _, row in df.iterrows():

    add_player(
        row["Nome"],
        row["Cognome"],
        row["Ruolo"],
        int(row["Anno_nascita"]),
        int(row["Numero_maglia"]),
        row["Note"]
    )


print("✅ Giocatori importati in SQLite")
