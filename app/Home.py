from dotenv import load_dotenv

load_dotenv()
import streamlit as st

from wm_prediction.db.connection import check_database_connection


st.set_page_config(
    page_title="WM Prediction",
    page_icon="⚽",
    layout="wide",
)

st.title("⚽ WM Prediction")
st.write("Projekt-Skeleton läuft.")

st.subheader("System Status")

try:
    db_ok = check_database_connection()

    if db_ok:
        st.success("Postgres connection: OK")
    else:
        st.error("Postgres connection: failed")

except Exception as error:
    st.error("Postgres connection: failed")
    st.code(str(error))