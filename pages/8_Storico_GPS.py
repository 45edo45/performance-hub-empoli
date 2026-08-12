"""
=========================================
Performance Hub
8 - Storico GPS & Cardio
Import batch + analisi storica multi-seduta
=========================================
"""

import re
import copy
import warnings
import datetime
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import StringIO

from utils.database import (
    get_connection,
    get_sessions,
    get_sessions_data_status,
    get_all_players,
    get_active_season_players,
    get_active_season_id,
    get_seasons,
    count_gps_by_session,
    delete_gps_by_session,
    add_gps,
    count_cardio_by_session,
    delete_cardio_by_session,
    add_cardio,
    ensure_cardio_table,
    get_gps_storico,
    get_gps_mean_by_session,
)

st.set_page_config(page_title="Storico GPS & Cardio", page_icon="📂", layout="wide")
st.title("📂 Storico GPS & Cardio")

# Migrazione DB: crea tabella cardio se non esiste
ensure_cardio_table()

tab_import, tab_analisi, tab_export = st.tabs(["⬆️ Importa sessioni", "📈 Analisi storica", "📥 Esporta Report"])

# ──────────────────────────────────────────
# COSTANTI
# ──────────────────────────────────────────

GPEXE_COLS = {
    "durata":       ("duration (mm:ss)", "mmss"),
    "distanza":     ("distance (m)", "float"),
    "max_speed":    ("max speed (km/h)", "float"),
    "z2":           ("distance/speed Z2 (m)", "float"),
    "z3":           ("distance/speed Z3 (m)", "float"),
    "z4":           ("distance/speed Z4 (m)", "float"),
    "speed_events": ("speed events", "int"),
    "bursts":       ("bursts", "int"),
    "brakes":       ("brakes", "int"),
}

GPS_LABELS = {
    "distanza":     "Distanza (m)",
    "max_speed":    "Velocità max (km/h)",
    "z2":           "Z2 (m)",
    "z3":           "Z3 (m)",
    "z4":           "Z4 (m)",
    "speed_events": "Speed Events",
    "bursts":       "Accelerazioni",
    "brakes":       "Decelerazioni",
    "durata":       "Durata (min)",
    "meters_min":   "Metri/min",
    "hsr":          "HSR (m)",
}

HR_LABELS = {
    "fc_media":      "FC media (bpm)",
    "fc_media_pct":  "FC media (%FCmax)",
    "fc_max":        "FC max (bpm)",
    "fc_max_pct":    "FC max (%FCmax)",
    "trimp":         "TRIMP",
    "trimp_min":     "TRIMP/min",
    "te_aerobico":   "TE aerobico",
    "te_anaerobico": "TE anaerobico",
    "epoc":          "EPOC (ml/kg)",
    "calorie":       "Calorie (kcal)",
    "vo2_medio":     "VO₂ medio (ml/kg/min)",
    "vo2_picco":     "VO₂ picco (ml/kg/min)",
    "hr_z_recupero": "HR Zona recupero (min)",
    "hr_z1":         "HR Z1 aerobica 1 (min)",
    "hr_z2":         "HR Z2 aerobica 2 (min)",
    "hr_z3":         "HR Z3 soglia anaer. (min)",
    "hr_z4":         "HR Z4 alta int. (min)",
    "hrr_30":        "HRR 30s (bpm)",
    "hrr_60":        "HRR 60s (bpm)",
    "hrr_120":       "HRR 120s (bpm)",
}

ALL_LABELS = {**GPS_LABELS, **HR_LABELS}

# ──────────────────────────────────────────
# UTILS
# ──────────────────────────────────────────

def _norm_name(raw: str) -> str:
    """
    GPEXE (tutto maiuscolo): COGNOME [COGNOME2] NOME → l'ultimo token è il nome.
    Es: 'DE VITA MARCO' → 'marco de vita', 'DI PEDE ANDREA' → 'andrea di pede'
    FirstBeat (title case): 'Marco De Vita' → 'marco de vita'
    """
    cleaned = re.sub(r"\*", "", str(raw)).strip()
    parts = cleaned.lower().split()
    if not parts:
        return cleaned.lower()
    if cleaned == cleaned.upper() and len(parts) >= 2:
        # Ultimo token = nome; resto = cognome (anche composto con De/Di/Del…)
        return parts[-1] + " " + " ".join(parts[:-1])
    return cleaned.lower()


def _mmss_to_min(val):
    s = str(val).strip()
    parts = s.split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) + int(parts[1]) / 60
    except Exception:
        pass
    return None


def _hms_to_min(val):
    if pd.isnull(val):
        return None
    if isinstance(val, pd.Timedelta):
        return val.total_seconds() / 60
    s = str(val).strip()
    parts = s.split(":")
    try:
        if len(parts) == 3:
            h, m, sec = int(parts[0]), int(parts[1]), float(parts[2])
            return h * 60 + m + sec / 60
        if len(parts) == 2:
            m, sec = int(parts[0]), float(parts[1])
            return m + sec / 60
    except Exception:
        pass
    return None


def _parse_gpexe(file):
    content = file.read().decode("utf-8", errors="replace")
    df = pd.read_csv(StringIO(content), sep=";")
    df.columns = [c.strip() for c in df.columns]

    data_seduta = None
    if "start date/time" in df.columns:
        try:
            data_seduta = pd.to_datetime(df["start date/time"].iloc[0]).strftime("%Y-%m-%d")
        except Exception:
            pass

    out = pd.DataFrame()
    out["giocatore_raw"] = df["athlete"].astype(str).str.strip()
    out["parziale"] = out["giocatore_raw"].str.contains(r"\*", regex=True)
    out["giocatore_key"] = out["giocatore_raw"].apply(_norm_name)
    out["giocatore_label"] = out["giocatore_raw"].apply(
        lambda x: re.sub(r"\*", "", x).strip().title()
    )

    for col_out, (col_in, tipo) in GPEXE_COLS.items():
        if col_in in df.columns:
            out[col_out] = df[col_in].apply(_mmss_to_min) if tipo == "mmss" else pd.to_numeric(df[col_in], errors="coerce")
        else:
            out[col_out] = None

    return out.reset_index(drop=True), data_seduta


def _parse_firstbeat(file):
    """
    Legge Excel FirstBeat, filtra 'Team Session', restituisce (DataFrame, data_seduta).
    data_seduta è None se non rilevabile dal file.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            xl = pd.read_excel(file, sheet_name="Summary")
        except Exception as e:
            return pd.DataFrame(), None, str(e)

    xl.columns = [c.strip() for c in xl.columns]

    mask = xl["Analysis period"].astype(str).str.strip().str.lower() == "team session"
    df = xl[mask].copy().reset_index(drop=True)

    if df.empty:
        periodi = xl["Analysis period"].dropna().unique().tolist()
        periodi_str = ", ".join(f'"{p}"' for p in periodi[:10])
        return pd.DataFrame(), None, (
            f"Nessuna riga 'Team Session' trovata. "
            f"Valori trovati in 'Analysis period': {periodi_str}"
        )

    out = pd.DataFrame()
    out["giocatore_raw"] = df["Athlete name"].astype(str).str.strip()
    out["giocatore_key"] = out["giocatore_raw"].apply(_norm_name)
    out["giocatore_label"] = out["giocatore_raw"]

    out["fc_media"]      = pd.to_numeric(df.get("Average HR (bpm)"), errors="coerce")
    out["fc_media_pct"]  = pd.to_numeric(df.get("Average %HRmax (%)"), errors="coerce").mul(100).round(1)
    out["fc_max"]        = pd.to_numeric(df.get("Peak HR (bpm)"), errors="coerce")
    out["fc_max_pct"]    = pd.to_numeric(df.get("Peak %HRmax (%)"), errors="coerce").mul(100).round(1)
    out["trimp"]         = pd.to_numeric(df.get("TRIMP (Index)"), errors="coerce").round(1)
    out["trimp_min"]     = pd.to_numeric(df.get("TRIMP/min (Index)"), errors="coerce").round(3)
    out["te_aerobico"]   = pd.to_numeric(df.get("Aerobic TE (0.0 - 5.0)"), errors="coerce").round(2)
    out["te_anaerobico"] = pd.to_numeric(df.get("Anaerobic TE (0.0 - 5.0)"), errors="coerce").round(2)
    out["epoc"]          = pd.to_numeric(df.get("EPOC (ml/kg)"), errors="coerce").round(1)
    out["calorie"]       = pd.to_numeric(df.get("EE Total (kcal)"), errors="coerce").round(0)
    out["vo2_medio"]     = pd.to_numeric(df.get("Average VO2 (ml/kg/min)"), errors="coerce").round(1)
    out["vo2_picco"]     = pd.to_numeric(df.get("Peak VO2 (ml/kg/min)"), errors="coerce").round(1)

    zone_map = {
        "hr_z_recupero": "Recovery training (hh:mm:ss)",
        "hr_z1":         "Aerobic zone 1 (hh:mm:ss)",
        "hr_z2":         "Aerobic zone 2 (hh:mm:ss)",
        "hr_z3":         "Anaerobic threshold zone (hh:mm:ss)",
        "hr_z4":         "High intensity training (hh:mm:ss)",
    }
    for col_out, col_in in zone_map.items():
        if col_in in df.columns:
            out[col_out] = df[col_in].apply(_hms_to_min).round(1)
        else:
            out[col_out] = None

    # Heart Rate Recovery — prova nomi colonna alternativi FirstBeat
    def _find_col(df, *candidates):
        col_lower = {c.lower(): c for c in df.columns}
        for cand in candidates:
            if cand in df.columns:
                return cand
            if cand.lower() in col_lower:
                return col_lower[cand.lower()]
        return None

    hrr_map = {
        "hrr_30":  ["Heart Rate Recovery (bpm) 30s", "HR recovery 30 s (bpm)",
                    "HR recovery 30s (bpm)", "HRR 30s", "HRR30s"],
        "hrr_60":  ["Heart Rate Recovery (bpm) 60s", "HR recovery 60 s (bpm)",
                    "HR recovery 60s (bpm)", "HRR 60s", "HRR60s"],
        "hrr_120": ["Heart Rate Recovery (bpm) 120s", "HR recovery 120 s (bpm)",
                    "HR recovery 120s (bpm)", "HRR 120s", "HRR120s"],
    }
    for col_out, candidates in hrr_map.items():
        found = _find_col(df, *candidates)
        if found:
            out[col_out] = pd.to_numeric(df[found], errors="coerce").round(0)
        else:
            out[col_out] = None

    return out.reset_index(drop=True), None, None


def _parse_cardio_df(df_group):
    """
    Dato un DataFrame già filtrato su 'team session' per una singola data,
    restituisce il DataFrame cardio normalizzato (stesso formato di _parse_firstbeat).
    """
    out = pd.DataFrame()
    out["giocatore_raw"]   = df_group["Athlete name"].astype(str).str.strip()
    out["giocatore_key"]   = out["giocatore_raw"].apply(_norm_name)
    out["giocatore_label"] = out["giocatore_raw"]

    out["fc_media"]      = pd.to_numeric(df_group.get("Average HR (bpm)"),         errors="coerce")
    out["fc_media_pct"]  = pd.to_numeric(df_group.get("Average %HRmax (%)"),       errors="coerce").mul(100).round(1)
    out["fc_max"]        = pd.to_numeric(df_group.get("Peak HR (bpm)"),             errors="coerce")
    out["fc_max_pct"]    = pd.to_numeric(df_group.get("Peak %HRmax (%)"),           errors="coerce").mul(100).round(1)
    out["trimp"]         = pd.to_numeric(df_group.get("TRIMP (Index)"),             errors="coerce").round(1)
    out["trimp_min"]     = pd.to_numeric(df_group.get("TRIMP/min (Index)"),         errors="coerce").round(3)
    out["te_aerobico"]   = pd.to_numeric(df_group.get("Aerobic TE (0.0 - 5.0)"),   errors="coerce").round(2)
    out["te_anaerobico"] = pd.to_numeric(df_group.get("Anaerobic TE (0.0 - 5.0)"), errors="coerce").round(2)
    out["epoc"]          = pd.to_numeric(df_group.get("EPOC (ml/kg)"),              errors="coerce").round(1)
    out["calorie"]       = pd.to_numeric(df_group.get("EE Total (kcal)"),           errors="coerce").round(0)
    out["vo2_medio"]     = pd.to_numeric(df_group.get("Average VO2 (ml/kg/min)"),   errors="coerce").round(1)
    out["vo2_picco"]     = pd.to_numeric(df_group.get("Peak VO2 (ml/kg/min)"),      errors="coerce").round(1)

    zone_map = {
        "hr_z_recupero": "Recovery training (hh:mm:ss)",
        "hr_z1":         "Aerobic zone 1 (hh:mm:ss)",
        "hr_z2":         "Aerobic zone 2 (hh:mm:ss)",
        "hr_z3":         "Anaerobic threshold zone (hh:mm:ss)",
        "hr_z4":         "High intensity training (hh:mm:ss)",
    }
    for col_out, col_in in zone_map.items():
        out[col_out] = df_group[col_in].apply(_hms_to_min).round(1) if col_in in df_group.columns else None

    def _find_col(df, *candidates):
        col_lower = {c.lower(): c for c in df.columns}
        for cand in candidates:
            if cand in df.columns: return cand
            if cand.lower() in col_lower: return col_lower[cand.lower()]
        return None

    hrr_map = {
        "hrr_30":  ["Heart Rate Recovery (bpm) 30s", "HR recovery 30 s (bpm)", "HR recovery 30s (bpm)"],
        "hrr_60":  ["Heart Rate Recovery (bpm) 60s", "HR recovery 60 s (bpm)", "HR recovery 60s (bpm)"],
        "hrr_120": ["Heart Rate Recovery (bpm) 120s", "HR recovery 120 s (bpm)", "HR recovery 120s (bpm)"],
    }
    for col_out, candidates in hrr_map.items():
        found = _find_col(df_group, *candidates)
        out[col_out] = pd.to_numeric(df_group[found], errors="coerce").round(0) if found else None

    return out.reset_index(drop=True)


def _parse_firstbeat_multi(file):
    """
    Legge un report FirstBeat multi-seduta (es. 30 giorni).
    Raggruppa per data (colonna 'Start date (dd.mm.yyyy)') e filtra 'team session'.
    Restituisce:
        - date_map: dict {'YYYY-MM-DD': DataFrame cardio}
        - errore:   str o None
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            xl = pd.read_excel(file, sheet_name="Summary")
        except Exception as e:
            return {}, str(e)

    xl.columns = [c.strip() for c in xl.columns]

    mask = xl["Analysis period"].astype(str).str.strip().str.lower() == "team session"
    df = xl[mask].copy().reset_index(drop=True)

    if df.empty:
        periodi = xl["Analysis period"].dropna().unique().tolist()
        periodi_str = ", ".join(f'"{p}"' for p in periodi[:10])
        return {}, f"Nessuna riga 'Team Session' trovata. Valori trovati: {periodi_str}"

    # Estrai data da 'Start date (dd.mm.yyyy)'
    date_col = None
    for cname in ["Start date (dd.mm.yyyy)", "Start date", "Date"]:
        if cname in df.columns:
            date_col = cname
            break

    if date_col is None:
        return {}, "Colonna data non trovata. Cercavo: 'Start date (dd.mm.yyyy)'."

    def _parse_date(val):
        if pd.isnull(val):
            return None
        # openpyxl spesso legge le date come datetime/Timestamp
        if isinstance(val, (pd.Timestamp, datetime.datetime, datetime.date)):
            return pd.Timestamp(val).strftime("%Y-%m-%d")
        s = str(val).strip()
        for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%y"):
            try:
                return pd.to_datetime(s, format=fmt).strftime("%Y-%m-%d")
            except Exception:
                pass
        # Fallback: lascia a pandas inferire il formato
        try:
            return pd.to_datetime(s, dayfirst=True).strftime("%Y-%m-%d")
        except Exception:
            return None

    df["_data_iso"] = df[date_col].apply(_parse_date)

    date_map = {}
    for data_iso, group in df.groupby("_data_iso"):
        if data_iso is None:
            continue
        date_map[data_iso] = _parse_cardio_df(group.drop(columns=["_data_iso"]))

    return date_map, None


def _build_player_map():
    players = get_all_players()
    result = {}
    for p in players:
        result[f"{p['nome']} {p['cognome']}".lower()] = p["id"]
        result[f"{p['cognome']} {p['nome']}".lower()] = p["id"]
    return result


def _lookup_player(row, player_map):
    key1 = row["giocatore_key"]
    key2 = row["giocatore_label"].lower()
    parts = key2.split()
    key3 = " ".join(parts[1:] + [parts[0]]) if len(parts) >= 2 else key2
    return player_map.get(key1) or player_map.get(key2) or player_map.get(key3)


# ══════════════════════════════════════════
# TAB 1 — IMPORTA SESSIONI
# ══════════════════════════════════════════

def _render_import_tab():
    sessions = get_sessions()
    if not sessions:
        st.warning("Nessuna seduta nel database. Creane una nella pagina Allenamenti prima di importare.")
        return

    # ── PANNELLO DI STATO ─────────────────
    st.subheader("📋 Stato sessioni")

    stagione_attiva_id = get_active_season_id()
    all_status_rows = get_sessions_data_status()
    # Filtra per stagione attiva direttamente qui
    if stagione_attiva_id is not None:
        # get_sessions_data_status non ha il filtro stagione nella versione cache →
        # usiamo get_sessions() che già abbiamo in memoria per ottenere gli id validi
        ids_stagione = {s[0] for s in sessions if len(s) > 7 and s[7] == stagione_attiva_id}
        status_rows = [r for r in all_status_rows if r["id"] in ids_stagione]
        st.caption("Mostrate solo le sedute della stagione attiva.")
    else:
        status_rows = all_status_rows
        st.caption("ℹ️ Nessuna stagione attiva — mostrate tutte le sedute.")
    if status_rows:
        rows_ui = []
        for r in status_rows:
            gps_ok    = r["n_gps"] > 0
            cardio_ok = r["n_cardio"] > 0
            rows_ui.append({
                "Data":        r["data"],
                "Tipo":        r["tipo"] or "—",
                "MD":          r["md"]   or "—",
                "Avversario":  r["avversario"] or "—",
                "GPS":         f"✅ {r['n_gps']} atleti" if gps_ok    else "❌ mancante",
                "Cardio":      f"✅ {r['n_cardio']} atleti" if cardio_ok else "❌ mancante",
                "Stato":       (
                    "✅ Completa"  if gps_ok and cardio_ok else
                    "⚠️ Solo GPS"  if gps_ok else
                    "⚠️ Solo Cardio" if cardio_ok else
                    "🔴 Vuota"
                ),
            })

        df_status = pd.DataFrame(rows_ui)

        def _color_stato(val):
            if val.startswith("✅"):
                return "color: #2ECC71; font-weight: bold"
            if val.startswith("⚠️"):
                return "color: #F4B400; font-weight: bold"
            return "color: #E74C3C; font-weight: bold"

        st.dataframe(
            df_status.style.map(_color_stato, subset=["GPS", "Cardio", "Stato"]),
            use_container_width=True,
            hide_index=True,
        )

        n_complete = sum(1 for r in status_rows if r["n_gps"] > 0 and r["n_cardio"] > 0)
        n_gps_only = sum(1 for r in status_rows if r["n_gps"] > 0 and r["n_cardio"] == 0)
        n_cardio_only = sum(1 for r in status_rows if r["n_gps"] == 0 and r["n_cardio"] > 0)
        n_vuote = sum(1 for r in status_rows if r["n_gps"] == 0 and r["n_cardio"] == 0)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("✅ Complete",    n_complete)
        c2.metric("⚠️ Solo GPS",    n_gps_only)
        c3.metric("⚠️ Solo Cardio", n_cardio_only)
        c4.metric("🔴 Vuote",       n_vuote)

    st.divider()

    session_map = {}
    for s in sessions:
        sid, data, md, tipo = s[0], s[1], s[2], s[3]
        label = f"{data} — {tipo or ''} {md or ''}".strip(" —")
        session_map[label] = sid
    session_labels = list(session_map.keys())

    # ── GPS ──────────────────────────────
    st.subheader("📡 Dati GPS — GPEXE (CSV)")
    uploaded_gps = st.file_uploader(
        "File CSV GPEXE (puoi selezionarne più di uno)",
        type=["csv"],
        accept_multiple_files=True,
        key="batch_upload_gps",
    )

    gps_configs = []
    if uploaded_gps:
        st.markdown("**Abbina ogni file GPS alla seduta corrispondente:**")
        for i, f in enumerate(uploaded_gps):
            df_parsed, data_rilevata = _parse_gpexe(f)
            f.seek(0)

            default_idx = 0
            if data_rilevata:
                for j, lbl in enumerate(session_labels):
                    if data_rilevata in lbl:
                        default_idx = j
                        break

            col_a, col_b, col_c = st.columns([3, 4, 1])
            with col_a:
                st.markdown(f"**{f.name}**")
                st.caption(
                    f"Data rilevata: {data_rilevata} · {len(df_parsed)} atleti"
                    if data_rilevata else f"{len(df_parsed)} atleti · data non rilevata"
                )
            with col_b:
                seduta_label = st.selectbox(
                    "Seduta GPS", session_labels, index=default_idx,
                    key=f"gps_sed_{i}", label_visibility="collapsed",
                )
                seduta_id = session_map[seduta_label]
            with col_c:
                existing = count_gps_by_session(seduta_id)
                if existing > 0:
                    st.warning(f"⚠️ {existing} GPS già presenti")

            gps_configs.append({
                "file": f, "df": df_parsed,
                "seduta_id": seduta_id, "nome_file": f.name, "existing": existing,
            })

    st.divider()

    # ── CARDIO ───────────────────────────
    st.subheader("❤️ Dati cardio — FirstBeat (XLSX)")
    uploaded_hr = st.file_uploader(
        "File Excel FirstBeat (puoi selezionarne più di uno)",
        type=["xlsx"],
        accept_multiple_files=True,
        key="batch_upload_hr",
    )

    cardio_configs = []
    if uploaded_hr:
        st.markdown("**Abbina ogni file cardio alla seduta corrispondente:**")
        for i, f in enumerate(uploaded_hr):
            df_parsed, _, errore = _parse_firstbeat(f)
            f.seek(0)

            if errore or df_parsed.empty:
                st.error(f"❌ {f.name}: {errore or 'File vuoto o formato non riconosciuto'}")
                continue

            col_a, col_b, col_c = st.columns([3, 4, 1])
            with col_a:
                st.markdown(f"**{f.name}**")
                st.caption(f"{len(df_parsed)} atleti trovati")
            with col_b:
                seduta_label = st.selectbox(
                    "Seduta HR", session_labels, index=0,
                    key=f"hr_sed_{i}", label_visibility="collapsed",
                )
                seduta_id = session_map[seduta_label]
            with col_c:
                existing = count_cardio_by_session(seduta_id)
                if existing > 0:
                    st.warning(f"⚠️ {existing} HR già presenti")

            cardio_configs.append({
                "file": f, "df": df_parsed,
                "seduta_id": seduta_id, "nome_file": f.name, "existing": existing,
            })

    st.divider()

    # ── CARDIO MULTI-SEDUTA ───────────────
    st.subheader("❤️ Dati cardio — Report multi-seduta FirstBeat (XLSX)")
    st.caption("Carica un report FirstBeat che copre più giorni (es. 30 gg): le sedute vengono abbinate automaticamente per data.")

    uploaded_multi = st.file_uploader(
        "File Excel FirstBeat multi-seduta",
        type=["xlsx"],
        key="batch_upload_multi",
    )

    if uploaded_multi:
        date_map, errore_multi = _parse_firstbeat_multi(uploaded_multi)

        if errore_multi:
            st.error(f"❌ {errore_multi}")
        elif not date_map:
            st.warning("Nessuna seduta trovata nel file.")
        else:
            # Mappa data → seduta_id dal DB
            date_to_session = {}
            for s in sessions:
                sid, data_s = s[0], s[1]
                date_to_session[data_s] = sid   # data_s già in formato YYYY-MM-DD

            st.markdown("**Abbinamento automatico per data:**")
            header = st.columns([2, 4, 1, 1])
            header[0].markdown("**Data**")
            header[1].markdown("**Seduta nel DB**")
            header[2].markdown("**Atleti**")
            header[3].markdown("**Cardio esistenti**")

            for data_iso, df_card in sorted(date_map.items()):
                sid = date_to_session.get(data_iso)
                row_cols = st.columns([2, 4, 1, 1])
                row_cols[0].write(data_iso)
                row_cols[2].write(str(len(df_card)))

                if sid is None:
                    row_cols[1].warning("⚠️ Nessuna seduta trovata")
                    row_cols[3].write("—")
                    continue

                # Trova label della seduta
                sed_label = next(
                    (lbl for lbl, s_id in session_map.items() if s_id == sid), data_iso
                )
                row_cols[1].success(f"✅ {sed_label}")

                existing_c = count_cardio_by_session(sid)
                row_cols[3].write(f"{existing_c} {'⚠️' if existing_c > 0 else ''}")

                # Aggiunge ai cardio_configs
                cardio_configs.append({
                    "file": None, "df": df_card,
                    "seduta_id": sid, "nome_file": f"multi / {data_iso}",
                    "existing": existing_c,
                })

            n_matched   = sum(1 for d in date_map if d in date_to_session)
            n_unmatched = len(date_map) - n_matched
            st.caption(
                f"{n_matched} sedute abbinate su {len(date_map)} date nel file"
                + (f" · {n_unmatched} date senza seduta corrispondente" if n_unmatched else "")
            )

    if not gps_configs and not cardio_configs:
        st.info("Carica almeno un file GPS (CSV) o cardio (XLSX) per iniziare.")
        return

    st.divider()
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        overwrite = st.checkbox("Sostituisci i dati esistenti (GPS + Cardio)", value=False)
    with col_opt2:
        skip_parziali = st.checkbox("Escludi atleti parziali GPS (*)", value=False)

    if st.button("💾 Salva tutte le sessioni", type="primary"):
        player_map = _build_player_map()
        tot_gps = 0
        tot_cardio = 0
        tot_non_trovati = []
        errori = []
        n_total = len(gps_configs) + len(cardio_configs)
        progress = st.progress(0)
        stato = st.empty()

        # ── Salva GPS ──
        for idx, cfg in enumerate(gps_configs):
            stato.text(f"GPS: {cfg['nome_file']}…")
            progress.progress(idx / n_total)

            seduta_id = cfg["seduta_id"]
            df = cfg["df"]

            if overwrite and cfg["existing"] > 0:
                delete_gps_by_session(seduta_id)

            for _, row in df.iterrows():
                if skip_parziali and row.get("parziale"):
                    continue

                giocatore_id = _lookup_player(row, player_map)
                if giocatore_id is None:
                    tot_non_trovati.append(f"GPS / {cfg['nome_file']} → {row['giocatore_label']}")
                    continue

                try:
                    add_gps(
                        seduta_id=seduta_id,
                        giocatore_id=giocatore_id,
                        durata=row.get("durata"),
                        distanza=row.get("distanza"),
                        meters_min=None,
                        max_speed=row.get("max_speed"),
                        z2=row.get("z2"),
                        z3=row.get("z3"),
                        z4=row.get("z4"),
                        hsr=None, vhsr=None,
                        speed_events=row.get("speed_events"),
                        bursts=row.get("bursts"),
                        brakes=row.get("brakes"),
                        high_ext_work_plus=None, high_ext_work_minus=None,
                        eccentric_index=None, energy=None,
                        eq_distance_index=None, avg_metabolic_power=None,
                        met_power_events=None, mpe_rec_avg_time=None,
                        mpe_rec_avg_power=None,
                        hr_z2=None, hr_z3=None,
                        hsr_min=None, sprint_min=None,
                        accel_min=None, decel_min=None,
                        valido=0 if row.get("parziale") else 1,
                        escluso_motivo="parziale" if row.get("parziale") else None,
                    )
                    tot_gps += 1
                except Exception as e:
                    errori.append(f"GPS / {cfg['nome_file']} / {row['giocatore_label']}: {e}")

        # ── Salva Cardio ──
        for idx, cfg in enumerate(cardio_configs):
            stato.text(f"Cardio: {cfg['nome_file']}…")
            progress.progress((len(gps_configs) + idx) / n_total)

            seduta_id = cfg["seduta_id"]
            df = cfg["df"]

            if overwrite and cfg["existing"] > 0:
                delete_cardio_by_session(seduta_id)

            for _, row in df.iterrows():
                giocatore_id = _lookup_player(row, player_map)
                if giocatore_id is None:
                    tot_non_trovati.append(f"Cardio / {cfg['nome_file']} → {row['giocatore_label']}")
                    continue

                try:
                    add_cardio(
                        seduta_id=seduta_id,
                        giocatore_id=giocatore_id,
                        fc_media=row.get("fc_media"),
                        fc_media_pct=row.get("fc_media_pct"),
                        fc_max=row.get("fc_max"),
                        fc_max_pct=row.get("fc_max_pct"),
                        trimp=row.get("trimp"),
                        trimp_min=row.get("trimp_min"),
                        te_aerobico=row.get("te_aerobico"),
                        te_anaerobico=row.get("te_anaerobico"),
                        epoc=row.get("epoc"),
                        calorie=row.get("calorie"),
                        vo2_medio=row.get("vo2_medio"),
                        vo2_picco=row.get("vo2_picco"),
                        hr_z_recupero=row.get("hr_z_recupero"),
                        hr_z1=row.get("hr_z1"),
                        hr_z2=row.get("hr_z2"),
                        hr_z3=row.get("hr_z3"),
                        hr_z4=row.get("hr_z4"),
                        hrr_30=row.get("hrr_30"),
                        hrr_60=row.get("hrr_60"),
                        hrr_120=row.get("hrr_120"),
                    )
                    tot_cardio += 1
                except Exception as e:
                    errori.append(f"Cardio / {cfg['nome_file']} / {row['giocatore_label']}: {e}")

        progress.progress(1.0)
        stato.empty()

        parti = []
        if tot_gps:
            parti.append(f"{tot_gps} record GPS")
        if tot_cardio:
            parti.append(f"{tot_cardio} record cardio")
        st.success(f"✅ Importazione completata — {' e '.join(parti)} salvati.")

        if tot_non_trovati:
            with st.expander(f"⚠️ {len(tot_non_trovati)} atleti non trovati nel DB"):
                for n in tot_non_trovati:
                    st.write(f"• {n}")
                st.caption("Verifica che i nomi corrispondano a quelli nella pagina Giocatori.")

        if errori:
            with st.expander(f"❌ {len(errori)} errori"):
                for e in errori:
                    st.write(f"• {e}")

    # ── GESTIONE / CANCELLAZIONE ─────────
    st.divider()
    with st.expander("🗑️ Elimina dati GPS o Cardio di una seduta"):
        # Mostra solo sedute che hanno almeno qualcosa
        rows_con_dati = [r for r in get_sessions_data_status() if r["n_gps"] > 0 or r["n_cardio"] > 0]
        if not rows_con_dati:
            st.info("Nessuna seduta ha dati GPS o cardio.")
        else:
            del_opts = {
                f"{r['data']} — {r['tipo'] or ''} {r['md'] or ''}  ·  GPS: {r['n_gps']}  Cardio: {r['n_cardio']}".strip(): r["id"]
                for r in rows_con_dati
            }
            seduta_del = st.selectbox("Seleziona seduta", list(del_opts.keys()), key="del_sed")
            sid_del = del_opts[seduta_del]

            col_d1, col_d2 = st.columns(2)
            with col_d1:
                if st.button("🗑️ Elimina Cardio", key="del_cardio", use_container_width=True):
                    n = count_cardio_by_session(sid_del)
                    if n == 0:
                        st.warning("Nessun dato cardio da eliminare per questa seduta.")
                    else:
                        delete_cardio_by_session(sid_del)
                        st.success(f"✅ Eliminati {n} record cardio.")
                        st.rerun()
            with col_d2:
                if st.button("🗑️ Elimina GPS", key="del_gps", use_container_width=True):
                    n = count_gps_by_session(sid_del)
                    if n == 0:
                        st.warning("Nessun dato GPS da eliminare per questa seduta.")
                    else:
                        delete_gps_by_session(sid_del)
                        st.success(f"✅ Eliminati {n} record GPS.")
                        st.rerun()


# ══════════════════════════════════════════
# TAB 2 — ANALISI STORICA
# ══════════════════════════════════════════

def _get_season_players_ui():
    """
    Restituisce i giocatori per i selettori UI:
    - se c'è una stagione attiva → solo i giocatori attivi in rosa
    - altrimenti → tutti i giocatori del DB
    """
    players = get_active_season_players()
    if players:
        return players, True
    return get_all_players(), False


def _render_analisi_tab():
    st.subheader("Analisi storica GPS & Cardio")

    players, filtered_by_season = _get_season_players_ui()
    if not players:
        st.warning("Nessun giocatore disponibile. Verifica la rosa nella pagina Giocatori.")
        return

    if not filtered_by_season:
        st.caption("ℹ️ Nessuna stagione attiva — vengono mostrati tutti i giocatori del database.")

    player_opts = {f"{p['cognome']} {p['nome']}": p["id"] for p in players}

    col_f1, col_f2, col_f3, col_f4 = st.columns([2, 2, 2, 2])

    with col_f1:
        atleti_sel = st.multiselect("Atleti", list(player_opts.keys()), placeholder="Tutti gli atleti")
    with col_f2:
        data_da = st.date_input("Dal", value=None, key="stor_da")
    with col_f3:
        data_a = st.date_input("Al", value=None, key="stor_a")
    with col_f4:
        # Gruppo separato GPS / Cardio nella selectbox
        param_sel = st.selectbox(
            "Parametro principale",
            ["── GPS ──"] + list(GPS_LABELS.values()) + ["── Cardio ──"] + list(HR_LABELS.values()),
            index=1,
        )

    # Salta i separatori
    if param_sel.startswith("──"):
        st.info("Seleziona un parametro dal menu.")
        return

    label_to_col = {v: k for k, v in ALL_LABELS.items()}
    param_col = label_to_col[param_sel]

    giocatore_ids = [player_opts[n] for n in atleti_sel] if atleti_sel else None

    storico = get_gps_storico(
        giocatore_ids=giocatore_ids,
        data_da=str(data_da) if data_da else None,
        data_a=str(data_a) if data_a else None,
    )

    if not storico:
        st.info("Nessun dato GPS trovato. Importa prima le sessioni o modifica i filtri.")
        return

    df_stor = pd.DataFrame(storico)
    df_stor["atleta"] = df_stor["cognome"] + " " + df_stor["nome"]
    df_stor["data_seduta"] = pd.to_datetime(df_stor["data_seduta"])
    df_stor["data_label"] = df_stor["data_seduta"].dt.strftime("%d/%m/%y")

    # Per param cardio: avvisa se nessun dato HR disponibile
    is_hr_param = param_col in HR_LABELS
    if is_hr_param and (param_col not in df_stor.columns or df_stor[param_col].isna().all()):
        st.warning(f"Il parametro cardio '{param_sel}' non è ancora disponibile. Importa i file FirstBeat per questa seduta.")
        return

    if param_col not in df_stor.columns or df_stor[param_col].isna().all():
        st.warning(f"Il parametro '{param_sel}' non è disponibile nei dati caricati.")
        return

    modalita = st.radio(
        "Tipo di analisi",
        ["📈 Trend atleta", "👥 Confronto atleti per seduta",
         "🔁 Stesso atleta, più sedute", "📊 Media squadra per seduta"],
        horizontal=True,
    )

    st.divider()

    # ── 1) TREND ATLETA ──
    if modalita == "📈 Trend atleta":
        if not atleti_sel:
            st.info("Seleziona almeno un atleta nei filtri.")
            return

        fig = px.line(
            df_stor[df_stor[param_col].notna()].sort_values("data_seduta"),
            x="data_seduta", y=param_col, color="atleta", markers=True,
            labels={"data_seduta": "Data", param_col: param_sel, "atleta": "Atleta"},
            title=f"Trend — {param_sel}",
        )
        fig.update_xaxes(tickformat="%d/%m/%y")
        st.plotly_chart(fig, use_container_width=True)

        pivot = df_stor.groupby(["atleta", "data_seduta", "data_label"])[param_col].mean().reset_index()
        pivot = pivot.sort_values("data_seduta", ascending=False)
        date_order = pivot["data_label"].unique().tolist()  # più recente prima
        pivot_wide = pivot.pivot(index="atleta", columns="data_label", values=param_col).round(1)
        pivot_wide = pivot_wide[date_order]
        st.dataframe(pivot_wide, use_container_width=True)

    # ── 2) CONFRONTO ATLETI PER SEDUTA ──
    elif modalita == "👥 Confronto atleti per seduta":
        sessions_avail = (
            df_stor[["seduta_id", "data_seduta", "data_label", "tipo_seduta"]]
            .drop_duplicates()
            .sort_values("data_seduta")
        )
        sed_opts = {
            f"{r['data_label']} — {r['tipo_seduta'] or ''}": r["seduta_id"]
            for _, r in sessions_avail.iterrows()
        }
        sed_labels = list(sed_opts.keys())

        sed_scelte = st.multiselect(
            "Seleziona una o più sedute da confrontare",
            sed_labels,
            default=sed_labels[:1],
        )

        if not sed_scelte:
            st.info("Seleziona almeno una seduta.")
            return

        sed_ids_scelti = [sed_opts[l] for l in sed_scelte]
        df_sed = df_stor[df_stor["seduta_id"].isin(sed_ids_scelti)].copy()
        df_sed = df_sed[df_sed[param_col].notna()]

        if df_sed.empty:
            st.warning("Nessun dato per le sedute selezionate.")
            return

        id_to_label = {sed_opts[l]: l for l in sed_scelte}
        df_sed["seduta_label"] = df_sed["seduta_id"].map(id_to_label)

        if len(sed_scelte) == 1:
            df_sed = df_sed.sort_values(param_col, ascending=False)
            fig = px.bar(
                df_sed, x="atleta", y=param_col,
                color=param_col, color_continuous_scale="Blues",
                title=f"{param_sel} — {sed_scelte[0]}", text_auto=".1f",
            )
            fig.update_layout(showlegend=False, coloraxis_showscale=False)
        else:
            df_sed = df_sed.sort_values(["atleta", "data_seduta"])
            fig = px.bar(
                df_sed, x="atleta", y=param_col,
                color="seduta_label", barmode="group",
                title=f"{param_sel} — confronto sedute",
                text_auto=".1f",
                labels={"seduta_label": "Seduta", param_col: param_sel, "atleta": "Atleta"},
            )

        st.plotly_chart(fig, use_container_width=True)

        pivot = df_sed.pivot_table(
            index="atleta", columns="seduta_label", values=param_col, aggfunc="mean"
        ).round(1)
        col_order = [id_to_label[i] for i in sed_ids_scelti if id_to_label[i] in pivot.columns]
        pivot = pivot[col_order]
        st.dataframe(pivot, use_container_width=True)

    # ── 3) STESSO ATLETA PIÙ SEDUTE ──
    elif modalita == "🔁 Stesso atleta, più sedute":
        atleti_avail = sorted(df_stor["atleta"].unique())
        atleta_scelto = st.selectbox("Atleta", atleti_avail)
        df_atl = df_stor[df_stor["atleta"] == atleta_scelto].copy()

        # Parametri aggiuntivi: sia GPS che HR
        altri_params = st.multiselect(
            "Parametri aggiuntivi da sovrapporre",
            [v for k, v in ALL_LABELS.items() if k in df_atl.columns and k != param_col and not df_atl[k].isna().all()],
            default=[], max_selections=3,
        )

        all_params = [param_sel] + altri_params
        all_cols = [label_to_col[l] for l in all_params if label_to_col[l] in df_atl.columns]

        df_plot = df_atl[["data_seduta", "data_label"] + all_cols].dropna(subset=[all_cols[0]])
        df_plot = df_plot.sort_values("data_seduta")  # grafico: ascendente (trend storico)

        if df_plot.empty:
            st.warning("Nessun dato per questo atleta.")
            return

        colors = ["#00AEEF", "#F4B400", "#2ECC71", "#E74C3C"]
        fig = go.Figure()
        for i, (col, label) in enumerate(zip(all_cols, all_params)):
            fig.add_trace(go.Scatter(
                x=df_plot["data_seduta"], y=df_plot[col],
                mode="lines+markers", name=label,
                line=dict(color=colors[i % len(colors)], width=2),
                marker=dict(size=7),
                yaxis="y1" if i == 0 else "y2",
            ))

        layout_kwargs = dict(
            title=f"{atleta_scelto} — andamento nel tempo",
            xaxis=dict(tickformat="%d/%m/%y"),
            yaxis=dict(title=all_params[0]),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        if len(all_cols) > 1:
            layout_kwargs["yaxis2"] = dict(
                title=", ".join(all_params[1:]), overlaying="y", side="right",
            )
        fig.update_layout(**layout_kwargs)
        st.plotly_chart(fig, use_container_width=True)

        rename_map = {"data_label": "Data"}
        rename_map.update({c: ALL_LABELS[c] for c in all_cols if c in ALL_LABELS})
        tab = df_plot[["data_label"] + all_cols].sort_values("data_seduta", ascending=False).rename(columns=rename_map) if "data_seduta" in df_plot.columns else df_plot[["data_label"] + all_cols].iloc[::-1].rename(columns=rename_map)
        numeric_cols = [ALL_LABELS[c] for c in all_cols if c in ALL_LABELS and pd.api.types.is_numeric_dtype(tab[ALL_LABELS[c]])]
        st.dataframe(
            tab.style.format({col: "{:.1f}" for col in numeric_cols}, na_rep="—"),
            use_container_width=True, hide_index=True,
        )

    # ── 4) MEDIA SQUADRA PER SEDUTA ──
    elif modalita == "📊 Media squadra per seduta":
        medie = get_gps_mean_by_session()
        if not medie:
            st.info("Nessun dato GPS nel database.")
            return

        df_med = pd.DataFrame(medie)
        df_med["data_seduta"] = pd.to_datetime(df_med["data_seduta"])
        df_med["data_label"] = df_med["data_seduta"].dt.strftime("%d/%m/%y")

        if data_da:
            df_med = df_med[df_med["data_seduta"] >= pd.to_datetime(str(data_da))]
        if data_a:
            df_med = df_med[df_med["data_seduta"] <= pd.to_datetime(str(data_a))]

        if param_col not in df_med.columns or df_med[param_col].isna().all():
            st.warning(f"'{param_sel}' non disponibile nelle medie di squadra.")
            return

        fig = px.bar(
            df_med.sort_values("data_seduta"),
            x="data_label", y=param_col,
            color=param_col, color_continuous_scale="Blues",
            title=f"Media squadra — {param_sel} per seduta",
            text_auto=".1f",
            hover_data=["n_giocatori", "tipo_seduta"],
        )
        fig.update_layout(xaxis_title="Seduta", coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

        # Tabella riepilogo: GPS + cardio disponibili
        gps_cols_avail = [c for c in GPS_LABELS if c in df_med.columns and not df_med[c].isna().all()]
        hr_cols_avail  = [c for c in HR_LABELS if c in df_med.columns and not df_med[c].isna().all()]

        base_cols = ["data_label", "tipo_seduta", "n_giocatori"]
        all_data_cols = gps_cols_avail + hr_cols_avail
        df_tab = df_med.sort_values("data_seduta", ascending=False)[base_cols + all_data_cols].copy()
        rename = {"data_label": "Data", "tipo_seduta": "Tipo", "n_giocatori": "N. atleti"}
        rename.update({c: ALL_LABELS.get(c, c) for c in all_data_cols})
        df_tab = df_tab.rename(columns=rename)
        numeric_label_cols = [ALL_LABELS.get(c, c) for c in all_data_cols]
        st.dataframe(
            df_tab.style.format({col: "{:.1f}" for col in numeric_label_cols}, na_rep="—"),
            use_container_width=True, hide_index=True,
        )


EXPORT_COLORS = [
    "#00AEEF", "#F4B400", "#2ECC71", "#E74C3C",
    "#9B59B6", "#F39C12", "#1ABC9C", "#E67E22",
]

# ══════════════════════════════════════════
# TAB 3 — ESPORTA REPORT
# ══════════════════════════════════════════

def _build_storico_html(df_stor, df_med, label_da, label_a, titolo, params_chart):
    """
    Genera un report HTML self-contained con:
    - Riepilogo periodo
    - Grafici barre per seduta (parametri selezionati)
    - Tabella medie squadra
    - Tabella dettaglio atleti per seduta
    """
    import plotly.io as pio

    BG       = "#0e1117"
    BG2      = "#1a1a2e"
    FG       = "#e8e8e8"
    GOLD     = "#F4B400"
    ACCENT   = "#00AEEF"

    def _style_fig(fig):
        """Applica tema dark + colori espliciti e restituisce HTML del grafico."""
        fig2 = copy.deepcopy(fig)
        traces_colored = [t for t in fig2.data if hasattr(t, "marker")]
        for i, t in enumerate(traces_colored):
            if hasattr(t.marker, "color") and not isinstance(t.marker.color, list):
                t.marker.color = EXPORT_COLORS[i % len(EXPORT_COLORS)]
            if hasattr(t, "line") and hasattr(t.line, "color"):
                t.line.color = EXPORT_COLORS[i % len(EXPORT_COLORS)]
        fig2.update_layout(
            paper_bgcolor=BG2, plot_bgcolor=BG2,
            font=dict(color=FG, family="Arial"),
            margin=dict(t=50, b=40, l=50, r=30),
        )
        return pio.to_html(fig2, include_plotlyjs=False, full_html=False, config={"displayModeBar": False})

    charts_html = ""
    label_to_col = {v: k for k, v in ALL_LABELS.items()}

    for param_label in params_chart:
        pcol = label_to_col.get(param_label)
        if not pcol:
            continue
        src = df_med if pcol in df_med.columns and not df_med[pcol].isna().all() else None
        if src is None:
            continue
        fig = px.bar(
            src.sort_values("data_seduta"),
            x="data_label", y=pcol,
            title=f"Media squadra — {param_label}",
            text_auto=".1f",
            labels={"data_label": "Seduta", pcol: param_label},
        )
        fig.update_traces(marker_color=ACCENT)
        charts_html += f'<div class="chart">{_style_fig(fig)}</div>\n'

    # Tabella medie squadra
    gps_avail = [c for c in GPS_LABELS if c in df_med.columns and not df_med[c].isna().all()]
    hr_avail  = [c for c in HR_LABELS  if c in df_med.columns and not df_med[c].isna().all()]
    tab_cols  = gps_avail + hr_avail
    df_tab    = df_med[["data_label", "tipo_seduta", "n_giocatori"] + tab_cols].copy()
    col_rename = {"data_label": "Data", "tipo_seduta": "Tipo", "n_giocatori": "N."}
    col_rename.update({c: ALL_LABELS.get(c, c) for c in tab_cols})
    df_tab = df_tab.rename(columns=col_rename)
    medie_html = df_tab.to_html(index=False, border=0, classes="data-table", na_rep="—",
                                float_format=lambda x: f"{x:.1f}")

    # Tabella dettaglio atleti (pivot per seduta)
    atleti_rows = []
    for atleta, grp in df_stor.groupby("atleta"):
        row = {"Atleta": atleta}
        for _, r in grp.sort_values("data_seduta").iterrows():
            col_key = r["data_label"]
            vals = []
            for c in gps_avail[:4]:  # max 4 GPS per leggibilità
                v = r.get(c)
                if pd.notna(v):
                    vals.append(f"{ALL_LABELS[c][:8]}: {v:.1f}")
            row[col_key] = " | ".join(vals) if vals else "—"
        atleti_rows.append(row)
    df_atleti = pd.DataFrame(atleti_rows)
    atleti_html = df_atleti.to_html(index=False, border=0, classes="data-table", na_rep="—")

    n_sedute  = df_med["data_seduta"].nunique()
    n_atleti  = df_stor["atleta"].nunique()
    oggi      = datetime.date.today().strftime("%d/%m/%Y")

    html = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<title>{titolo}</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: {BG}; color: {FG}; font-family: Arial, sans-serif; padding: 32px; }}
  h1 {{ color: {GOLD}; font-size: 26px; margin-bottom: 4px; }}
  h2 {{ color: {ACCENT}; font-size: 18px; margin: 28px 0 10px; border-bottom: 1px solid #333; padding-bottom: 6px; }}
  .meta {{ color: #aaa; font-size: 13px; margin-bottom: 24px; }}
  .kpi-row {{ display: flex; gap: 16px; margin-bottom: 28px; }}
  .kpi {{ background: {BG2}; border-radius: 8px; padding: 16px 24px; text-align: center; flex: 1; }}
  .kpi .val {{ font-size: 32px; font-weight: bold; color: {GOLD}; }}
  .kpi .lbl {{ font-size: 12px; color: #aaa; margin-top: 4px; }}
  .chart {{ background: {BG2}; border-radius: 8px; padding: 12px; margin-bottom: 20px; }}
  .data-table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 8px; }}
  .data-table th {{ background: #222; color: {GOLD}; padding: 8px; text-align: left; white-space: nowrap; }}
  .data-table td {{ padding: 7px 8px; border-bottom: 1px solid #2a2a2a; }}
  .data-table tr:hover td {{ background: #1e2030; }}
  .footer {{ margin-top: 32px; color: #555; font-size: 11px; text-align: center; }}
</style>
</head>
<body>
<h1>🏟️ {titolo}</h1>
<div class="meta">Periodo: <b>{label_da} → {label_a}</b> &nbsp;|&nbsp; Generato il {oggi}</div>

<div class="kpi-row">
  <div class="kpi"><div class="val">{n_sedute}</div><div class="lbl">Sedute</div></div>
  <div class="kpi"><div class="val">{n_atleti}</div><div class="lbl">Atleti</div></div>
  <div class="kpi"><div class="val">{label_da}</div><div class="lbl">Dal</div></div>
  <div class="kpi"><div class="val">{label_a}</div><div class="lbl">Al</div></div>
</div>

<h2>📊 Andamento per seduta</h2>
{charts_html}

<h2>📋 Medie squadra per seduta</h2>
{medie_html}

<h2>👥 Dettaglio atleti</h2>
{atleti_html}

<div class="footer">Performance Hub — Empoli Primavera — {oggi}</div>
</body>
</html>"""
    return html


def _render_export_tab():
    st.subheader("Esporta report storico")

    oggi = datetime.date.today()

    col1, col2 = st.columns(2)
    with col1:
        preset = st.selectbox("Periodo rapido", [
            "Personalizzato", "Oggi", "Ultima settimana", "Ultime 2 settimane",
            "Ultimo mese", "Ultimi 3 mesi",
        ])
    with col2:
        exp_players, exp_filtered = _get_season_players_ui()
        if not exp_filtered:
            st.caption("ℹ️ Nessuna stagione attiva — tutti i giocatori disponibili.")
        atleti_export = st.multiselect(
            "Filtra atleti (vuoto = tutti)",
            [f"{p['cognome']} {p['nome']}" for p in exp_players],
            placeholder="Tutti gli atleti",
        )

    # Calcola date da preset
    if preset == "Oggi":
        d_da, d_a = oggi, oggi
    elif preset == "Ultima settimana":
        d_da, d_a = oggi - datetime.timedelta(days=7), oggi
    elif preset == "Ultime 2 settimane":
        d_da, d_a = oggi - datetime.timedelta(days=14), oggi
    elif preset == "Ultimo mese":
        d_da, d_a = oggi - datetime.timedelta(days=30), oggi
    elif preset == "Ultimi 3 mesi":
        d_da, d_a = oggi - datetime.timedelta(days=90), oggi
    else:
        d_da, d_a = None, None

    col_da, col_a = st.columns(2)
    with col_da:
        data_da = st.date_input("Dal", value=d_da, key="exp_da")
    with col_a:
        data_a_sel = st.date_input("Al", value=d_a, key="exp_a")

    st.divider()

    # Parametri da includere nei grafici
    st.markdown("**Parametri da includere nei grafici:**")
    col_g, col_h = st.columns(2)
    with col_g:
        gps_sel = st.multiselect(
            "GPS", list(GPS_LABELS.values()),
            default=["Distanza (m)", "Velocità max (km/h)", "Accelerazioni"],
        )
    with col_h:
        hr_sel = st.multiselect(
            "Cardio", list(HR_LABELS.values()),
            default=["FC media (bpm)", "TRIMP", "EPOC (ml/kg)"],
        )
    params_chart = gps_sel + hr_sel

    titolo = st.text_input("Titolo del report", value="Report Storico GPS & Cardio — Empoli Primavera")

    if st.button("📥 Genera e scarica report HTML", type="primary"):
        if not data_da or not data_a_sel:
            st.error("Seleziona un intervallo di date.")
            return

        player_map = {f"{p['cognome']} {p['nome']}": p["id"] for p in exp_players}
        giocatore_ids = [player_map[n] for n in atleti_export] if atleti_export else None

        storico = get_gps_storico(
            giocatore_ids=giocatore_ids,
            data_da=str(data_da),
            data_a=str(data_a_sel),
        )
        medie = get_gps_mean_by_session()

        if not storico:
            st.warning("Nessun dato GPS nel periodo selezionato.")
            return

        df_stor = pd.DataFrame(storico)
        df_stor["atleta"] = df_stor["cognome"] + " " + df_stor["nome"]
        df_stor["data_seduta"] = pd.to_datetime(df_stor["data_seduta"])
        df_stor["data_label"]  = df_stor["data_seduta"].dt.strftime("%d/%m/%y")

        df_med = pd.DataFrame(medie)
        df_med["data_seduta"] = pd.to_datetime(df_med["data_seduta"])
        df_med["data_label"]  = df_med["data_seduta"].dt.strftime("%d/%m/%y")
        # Filtra per periodo
        df_med = df_med[
            (df_med["data_seduta"] >= pd.to_datetime(str(data_da))) &
            (df_med["data_seduta"] <= pd.to_datetime(str(data_a_sel)))
        ]

        if df_med.empty:
            st.warning("Nessuna seduta con dati nel periodo selezionato.")
            return

        label_da  = data_da.strftime("%d/%m/%Y")
        label_a   = data_a_sel.strftime("%d/%m/%Y")

        with st.spinner("Generazione report…"):
            html = _build_storico_html(
                df_stor, df_med, label_da, label_a, titolo, params_chart
            )

        periodo_str = f"{data_da.strftime('%Y%m%d')}_{data_a_sel.strftime('%Y%m%d')}"
        st.download_button(
            label="⬇️ Scarica Report HTML",
            data=html.encode("utf-8"),
            file_name=f"report_storico_{periodo_str}.html",
            mime="text/html",
        )
        st.success(f"Report pronto — {len(df_med)} sedute, {df_stor['atleta'].nunique()} atleti.")


# ── Render dei tab ──
with tab_import:
    _render_import_tab()

with tab_analisi:
    _render_analisi_tab()

with tab_export:
    _render_export_tab()
