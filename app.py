import streamlit as st
from utils.database import create_database

create_database()

st.set_page_config(
    page_title="Football GPS Analytics",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ Football GPS Analytics")

st.write(
    """
    Software di monitoraggio GPS per il calcio.

    Utilizza il menu laterale per navigare tra i moduli.
    """
)

