import streamlit as st
if "gps_df" not in st.session_state:
    st.session_state.gps_df = None

from utils.gps_import import (
    load_gpexe_file,
    validate_gpexe,
    prepare_gpexe,
    import_gps
)

from utils.backup import create_backup

from utils.database import (
    get_sessions,
    count_gps_by_session,
    delete_gps_by_session
)
st.title("📥 Importa dati GPEXE")


# ==========================
# SCELTA SEDUTA
# ==========================

st.subheader("1) Seleziona seduta")


sessions = get_sessions()


if not sessions:

    st.warning(
        "Nessuna seduta presente. "
        "Crea prima una seduta nella pagina Allenamenti."
    )

    st.stop()


session_options = {}


for s in sessions:

    session_id = s[0]

    descrizione = (
        f"{s[1]} - {s[2]} - {s[3]}"
    )

    session_options[descrizione] = session_id


selected = st.selectbox(
    "Seduta",
    list(session_options.keys())
)


seduta_id = session_options[selected]



# ==========================
# UPLOAD CSV
# ==========================

st.subheader("2) Carica file GPEXE")


file = st.file_uploader(
    "CSV GPEXE",
    type="csv"
)



if file:

    df = load_gpexe_file(file)

    st.session_state.gps_df = df


    st.subheader(
        "Anteprima"
    )

    st.dataframe(df)


    ok, message = validate_gpexe(df)


    if not ok:

        st.error(message)

        st.stop()


    st.success(message)


    df = prepare_gpexe(df)

    st.session_state.gps_df = df


    st.subheader(
        "Dati pronti per importazione"
    )

    st.dataframe(df)


# ==========================
# IMPORTAZIONE
# ==========================

st.subheader(
    "3) Importazione"
)


gps_existing = count_gps_by_session(
    seduta_id
)


if gps_existing > 0:

    st.warning(
        f"Questa seduta contiene già {gps_existing} record GPS."
    )


    action = st.radio(
        "Come vuoi procedere?",
        [
            "Sostituisci dati esistenti",
            "Mantieni entrambi",
            "Annulla importazione"
        ]
    )


else:

    action = "Mantieni entrambi"

if st.session_state.gps_df is None:

    st.warning(
        "Carica prima un file GPEXE."
    )

    st.stop()

if st.button("🚀 Importa dati GPS"):

    if action == "Annulla importazione":
        st.info("Importazione annullata.")
        st.stop()

    backup = create_backup()

    if action == "Sostituisci dati esistenti":
        delete_gps_by_session(seduta_id)

    try:
        risultato = import_gps(
            st.session_state.gps_df,
            seduta_id
        )

    except Exception as e:
        st.error(f"Errore durante l'importazione: {e}")
        st.stop()

    st.success("Importazione completata")

    st.write(
        f"Giocatori importati: {risultato['importati']}"
    )

    if risultato["non_trovati"]:
        st.warning("Giocatori non trovati:")
        st.write(risultato["non_trovati"])

    if backup:
        st.info(f"Backup creato: {backup}")