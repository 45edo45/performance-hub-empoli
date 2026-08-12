import streamlit as st
import pandas as pd

from utils.database import (
    add_player,
    add_player_to_season,
    get_seasons,
    get_players_by_season,
    update_player_season_status,
    update_player_season_data,
    remove_player_from_season,
    get_all_players,
)


st.set_page_config(
    page_title="Giocatori",
    page_icon="👥",
)


@st.cache_data(ttl=30)
def load_seasons():
    return get_seasons()


@st.cache_data(ttl=30)
def load_players_by_season(stagione_id):
    return get_players_by_season(stagione_id)


@st.cache_data(ttl=30)
def load_all_players():
    return get_all_players()


st.title("👥 Gestione Giocatori")


# =========================
# SELEZIONE STAGIONE
# =========================

with st.spinner("Caricamento gestione giocatori..."):
    stagioni = load_seasons()

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
    key="stagione_giocatori",
)


stagione_id = int(
    opzioni_stagioni[stagione_scelta]
)


# =========================
# INSERIMENTO GIOCATORE
# =========================

with st.expander(
    "➕ Inserisci nuovo giocatore",
    expanded=False
):

    with st.form("nuovo_giocatore"):

        nome = st.text_input("Nome")

        cognome = st.text_input("Cognome")

        ruolo = st.selectbox(
            "Ruolo",
            [
                "Portiere",
                "Difensore centrale",
                "Terzino",
                "Esterno",
                "Centrocampista",
                "Trequartista",
                "Attaccante",
            ],
        )

        anno = st.number_input(
            "Anno di nascita",
            min_value=1990,
            max_value=2030,
            step=1,
        )

        numero = st.number_input(
            "Numero maglia",
            min_value=1,
            max_value=99,
            step=1,
        )

        note = st.text_area("Note")

        salva = st.form_submit_button(
            "Salva giocatore"
        )


    if salva:

        if not nome.strip() or not cognome.strip():
            st.error(
                "Nome e cognome sono obbligatori."
            )

        else:
            add_player(
                nome.strip(),
                cognome.strip(),
                ruolo,
                int(anno),
                int(numero),
                note.strip(),
            )

            st.success(
                "Giocatore salvato nell'anagrafica generale."
            )

            st.rerun()


with st.expander(
    "➕ Aggiungi giocatore alla stagione",
    expanded=False
):

    with st.spinner("Caricamento anagrafica..."):
        tutti_giocatori = load_all_players()

    with st.spinner("Caricamento rosa..."):
        giocatori_stagione = load_players_by_season(
            stagione_id
        )

    id_giocatori_stagione = {
        giocatore["id"]
        for giocatore in giocatori_stagione
    }

    giocatori_disponibili = [
        giocatore
        for giocatore in tutti_giocatori
        if giocatore["id"] not in id_giocatori_stagione
    ]

    if not giocatori_disponibili:

        st.info(
            "Tutti i giocatori presenti nell'anagrafica "
            "sono già associati a questa stagione."
        )

    else:

        opzioni_disponibili = {
            (
                f"{giocatore['cognome']} "
                f"{giocatore['nome']} | "
                f"ID {giocatore['id']}"
            ): giocatore
            for giocatore in giocatori_disponibili
        }

    giocatore_da_aggiungere = st.selectbox(
        "Giocatore",
        list(opzioni_disponibili.keys()),
        key=f"aggiungi_giocatore_{stagione_id}",
    )

    giocatore_selezionato = opzioni_disponibili[
        giocatore_da_aggiungere
    ]

    ruoli_stagione = [
        "— Nessun ruolo —",
        "Portiere",
        "Difensore centrale",
        "Terzino",
        "Esterno",
        "Centrocampista",
        "Trequartista",
        "Attaccante",
    ]

    ruolo_stagione = st.selectbox(
        "Ruolo nella stagione",
        ruoli_stagione,
        key=f"ruolo_aggiunta_{stagione_id}",
    )

    numero_stagione_testo = st.text_input(
        "Numero maglia nella stagione",
        placeholder="Facoltativo",
        key=f"numero_aggiunta_{stagione_id}",
    )

    attivo_stagione = st.checkbox(
        "Giocatore attivo",
        value=True,
        key=f"attivo_aggiunta_{stagione_id}",
    )

    if st.button(
        "Aggiungi alla rosa",
        key=f"conferma_aggiunta_{stagione_id}",
    ):

        ruolo_da_salvare = (
            None
            if ruolo_stagione == "— Nessun ruolo —"
            else ruolo_stagione
        )

        if numero_stagione_testo.strip():

            try:
                numero_da_salvare = int(
                    numero_stagione_testo.strip()
                )

            except ValueError:
                st.error(
                    "Il numero di maglia deve essere numerico."
                )
                st.stop()

            if not 1 <= numero_da_salvare <= 99:
                st.error(
                    "Il numero di maglia deve essere "
                    "compreso tra 1 e 99."
                )
                st.stop()

        else:
            numero_da_salvare = None

        add_player_to_season(
            giocatore_id=int(
                giocatore_selezionato["id"]
            ),
            stagione_id=stagione_id,
            numero_maglia=numero_da_salvare,
            ruolo=ruolo_da_salvare,
            attivo=1 if attivo_stagione else 0,
        )

        st.success(
            "Giocatore aggiunto alla stagione selezionata."
        )

        st.rerun()


# =========================
# ROSA GIOCATORI
# =========================

st.subheader("📋 Rosa giocatori")


giocatori = get_players_by_season(
    stagione_id
)


df = pd.DataFrame(giocatori)


if df.empty:
    st.info(
        "Nessun giocatore associato a questa stagione."
    )

else:

    colonne = [
        colonna
        for colonna in [
            "id",
            "cognome",
            "nome",
            "ruolo",
            "numero_maglia",
            "attivo",
        ]
        if colonna in df.columns
    ]

    df = df[colonne]

    df = df.rename(
        columns={
            "id": "ID",
            "cognome": "Cognome",
            "nome": "Nome",
            "ruolo": "Ruolo",
            "numero_maglia": "Numero maglia",
            "attivo": "Attivo",
        }
    )

    if "Attivo" in df.columns:
        df["Attivo"] = df["Attivo"].map(
            {
                1: "Sì",
                0: "No",
            }
        )

    st.write(
        f"Giocatori in rosa: {len(df)}"
    )

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )


    # =========================
    # MODIFICA GIOCATORE
    # =========================

    st.subheader("✏️ Gestione giocatore in rosa")


    opzioni_giocatori = {
        (
            f"{riga['Cognome']} "
            f"{riga['Nome']} | "
            f"ID {riga['ID']}"
        ): riga
        for _, riga in df.iterrows()
    }


    giocatore_scelto = st.selectbox(
        "Seleziona giocatore",
        list(opzioni_giocatori.keys()),
        key=f"giocatore_{stagione_id}",
    )


    giocatore = opzioni_giocatori[
        giocatore_scelto
    ]


    ruoli = [
        "— Nessun ruolo —",
        "Portiere",
        "Difensore centrale",
        "Terzino",
        "Esterno",
        "Centrocampista",
        "Trequartista",
        "Attaccante",
    ]


    ruolo_attuale = giocatore["Ruolo"]

    if pd.isna(ruolo_attuale) or not ruolo_attuale:
        indice_ruolo = 0

    elif ruolo_attuale in ruoli:
        indice_ruolo = ruoli.index(
            ruolo_attuale
        )

    else:
        indice_ruolo = 0


    numero_attuale = (
        str(int(giocatore["Numero maglia"]))
        if pd.notna(giocatore["Numero maglia"])
        else ""
    )


    with st.form("modifica_giocatore_stagione"):

        nuovo_ruolo = st.selectbox(
            "Ruolo",
            ruoli,
            index=indice_ruolo,
        )

        nuovo_numero_testo = st.text_input(
            "Numero maglia",
            value=numero_attuale,
            placeholder=(
                "Lascia vuoto se non assegnato"
            ),
        )

        attivo = st.checkbox(
            "Giocatore attivo nella rosa",
            value=giocatore["Attivo"] == "Sì",
        )

        aggiorna = st.form_submit_button(
            "Aggiorna giocatore"
        )


    if aggiorna:

        ruolo_da_salvare = (
            None
            if nuovo_ruolo == "— Nessun ruolo —"
            else nuovo_ruolo
        )

        if nuovo_numero_testo.strip():

            try:
                numero_da_salvare = int(
                    nuovo_numero_testo.strip()
                )

            except ValueError:
                st.error(
                    "Il numero di maglia deve essere un numero."
                )
                st.stop()

            if not 1 <= numero_da_salvare <= 99:
                st.error(
                    "Il numero di maglia deve essere "
                    "compreso tra 1 e 99."
                )
                st.stop()

        else:
            numero_da_salvare = None


        update_player_season_data(
            giocatore_id=int(
                giocatore["ID"]
            ),
            stagione_id=stagione_id,
            numero_maglia=numero_da_salvare,
            ruolo=ruolo_da_salvare,
        )


        update_player_season_status(
            giocatore_id=int(
                giocatore["ID"]
            ),
            stagione_id=stagione_id,
            attivo=1 if attivo else 0,
        )


        st.success("Giocatore aggiornato")

        st.rerun()


    # =========================
    # RIMOZIONE DALLA ROSA
    # =========================

    st.subheader("🗑️ Rimuovi dalla rosa")

    st.warning(
        "Il giocatore verrà rimosso solo dalla "
        "stagione selezionata. I dati storici e "
        "GPS non verranno cancellati."
    )


    conferma_rimozione = st.checkbox(
        "Confermo la rimozione del giocatore dalla rosa",
        key=(
            f"conferma_rimozione_"
            f"{stagione_id}_"
            f"{giocatore['ID']}"
        ),
    )


    if st.button(
        "Rimuovi giocatore dalla rosa",
        type="secondary",
        disabled=not conferma_rimozione,
        key=(
            f"rimuovi_giocatore_"
            f"{stagione_id}_"
            f"{giocatore['ID']}"
        ),
    ):

        remove_player_from_season(
            giocatore_id=int(
                giocatore["ID"]
            ),
            stagione_id=stagione_id,
        )

        st.success(
            "Giocatore rimosso dalla rosa "
            "della stagione selezionata."
        )

        st.rerun()