"""
=========================================
Performance Hub
7 - Report Seduta
Upload GPEXE + FirstBeat → report unificato + grafici
=========================================
"""

import re
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import StringIO

# ──────────────────────────────────────────
# CONFIGURAZIONE PAGINA
# ──────────────────────────────────────────

st.set_page_config(
    page_title="Report Seduta",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Report Seduta")
st.caption("Carica il file GPEXE e/o il file FirstBeat per generare il report della seduta.")

# ──────────────────────────────────────────
# COSTANTI — COLONNE DISPONIBILI
# ──────────────────────────────────────────

GPS_COLS = {
    "Distanza (m)":          "distanza",
    "Velocità max (km/h)":   "vel_max",
    "Z2 velocità (m)":       "z2",
    "Z3 velocità (m)":       "z3",
    "Z4 velocità (m)":       "z4",
    "Speed Events":          "speed_events",
    "Accelerazioni":         "bursts",
    "Decelerazioni":         "brakes",
    "Durata GPS (min)":      "durata_gps",
}

HR_COLS = {
    "FC media (bpm)":              "fc_media",
    "FC media (%FCmax)":           "fc_media_pct",
    "FC max (bpm)":                "fc_max",
    "FC max (%FCmax)":             "fc_max_pct",
    "TRIMP":                       "trimp",
    "TRIMP/min":                   "trimp_min",
    "Training Effect aerobico":    "te_aerobico",
    "Training Effect anaerobico":  "te_anaerobico",
    "EPOC (ml/kg)":                "epoc",
    "Calorie totali (kcal)":       "calorie",
    "VO2 medio (ml/kg/min)":       "vo2_medio",
    "VO2 picco (ml/kg/min)":       "vo2_picco",
    "Zona recupero (min)":         "hr_z_recupero",
    "Zona aerobica 1 (min)":       "hr_z1",
    "Zona aerobica 2 (min)":       "hr_z2",
    "Zona soglia anaerobica (min)":"hr_z3",
    "Zona alta intensità (min)":   "hr_z4",
    "HRR 30s (bpm)":               "hrr_30",
    "HRR 60s (bpm)":               "hrr_60",
    "HRR 120s (bpm)":              "hrr_120",
}

# ──────────────────────────────────────────
# FUNZIONI PARSING
# ──────────────────────────────────────────

def _norm_name(raw: str) -> str:
    """
    Normalizza un nome giocatore per il matching.
    GPEXE:     'ANGIOLINI GIANMARCO *'  → 'gianmarco angiolini'
               'DE VITA MARCO *'        → 'marco de vita'
    FirstBeat: 'Gianmarco Angiolini'    → 'gianmarco angiolini'
               'Marco De Vita'          → 'marco de vita'

    Convenzione GPEXE: tutto maiuscolo, formato COGNOME [COGNOME2] NOME
    → l'ultimo token è sempre il nome; il resto è il cognome (anche composto).
    """
    cleaned = re.sub(r"\*", "", str(raw)).strip()
    parts = cleaned.lower().split()
    if not parts:
        return cleaned.lower()
    if cleaned == cleaned.upper() and len(parts) >= 2:
        # Ultimo token = nome, tutto il resto = cognome (gestisce "DE VITA", "DI PEDE", ecc.)
        return parts[-1] + " " + " ".join(parts[:-1])
    return cleaned.lower()


def _hms_to_min(val) -> float | None:
    """Converte 'hh:mm:ss' o Timedelta in minuti float."""
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


def _mmss_to_min(val) -> float | None:
    """Converte 'mm:ss' in minuti float."""
    if pd.isnull(val):
        return None
    s = str(val).strip()
    parts = s.split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) + int(parts[1]) / 60
    except Exception:
        pass
    return None


def parse_gpexe(file) -> pd.DataFrame:
    """Legge il CSV GPEXE (separatore ;) e restituisce DataFrame normalizzato."""
    content = file.read().decode("utf-8", errors="replace")
    df = pd.read_csv(StringIO(content), sep=";")

    df.columns = [c.strip() for c in df.columns]

    out = pd.DataFrame()
    out["giocatore_raw"] = df["athlete"].astype(str).str.strip()
    # Flag parziale: presenza del * nel nome GPEXE
    out["parziale"] = out["giocatore_raw"].str.contains(r"\*", regex=True)
    out["giocatore_key"] = out["giocatore_raw"].apply(_norm_name)
    out["giocatore"] = out["giocatore_raw"].apply(
        lambda x: re.sub(r"\*", "", x).strip().title()
    )
    out["durata_gps"] = df["duration (mm:ss)"].apply(_mmss_to_min)
    out["distanza"]   = pd.to_numeric(df["distance (m)"], errors="coerce")
    out["vel_max"]    = pd.to_numeric(df["max speed (km/h)"], errors="coerce")
    out["z2"]         = pd.to_numeric(df["distance/speed Z2 (m)"], errors="coerce")
    out["z3"]         = pd.to_numeric(df["distance/speed Z3 (m)"], errors="coerce")
    out["z4"]         = pd.to_numeric(df["distance/speed Z4 (m)"], errors="coerce")
    out["speed_events"] = pd.to_numeric(df["speed events"], errors="coerce")
    out["bursts"]     = pd.to_numeric(df["bursts"], errors="coerce")
    out["brakes"]     = pd.to_numeric(df["brakes"], errors="coerce")

    return out.reset_index(drop=True)


def parse_firstbeat(file) -> pd.DataFrame:
    """
    Legge l'Excel FirstBeat, filtra 'Team Session',
    e restituisce DataFrame normalizzato.
    """
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        xl = pd.read_excel(file, sheet_name="Summary")

    xl.columns = [c.strip() for c in xl.columns]

    # Filtra solo Team Session
    mask = xl["Analysis period"].astype(str).str.strip().str.lower() == "team session"
    df = xl[mask].copy().reset_index(drop=True)

    if df.empty:
        st.error("Nessuna riga 'Team Session' trovata nel file FirstBeat.")
        return pd.DataFrame()

    out = pd.DataFrame()
    out["giocatore_raw"] = df["Athlete name"].astype(str).str.strip()
    out["giocatore_key"] = out["giocatore_raw"].apply(_norm_name)
    out["giocatore"]     = out["giocatore_raw"]

    out["fc_media"]     = pd.to_numeric(df["Average HR (bpm)"], errors="coerce")
    out["fc_media_pct"] = pd.to_numeric(df["Average %HRmax (%)"], errors="coerce").mul(100).round(1)
    out["fc_max"]       = pd.to_numeric(df["Peak HR (bpm)"], errors="coerce")
    out["fc_max_pct"]   = pd.to_numeric(df["Peak %HRmax (%)"], errors="coerce").mul(100).round(1)
    out["trimp"]        = pd.to_numeric(df["TRIMP (Index)"], errors="coerce").round(1)
    out["trimp_min"]    = pd.to_numeric(df["TRIMP/min (Index)"], errors="coerce").round(3)
    out["te_aerobico"]  = pd.to_numeric(df["Aerobic TE (0.0 - 5.0)"], errors="coerce").round(2)
    out["te_anaerobico"]= pd.to_numeric(df["Anaerobic TE (0.0 - 5.0)"], errors="coerce").round(2)
    out["epoc"]         = pd.to_numeric(df["EPOC (ml/kg)"], errors="coerce").round(1)
    out["calorie"]      = pd.to_numeric(df["EE Total (kcal)"], errors="coerce").round(0)
    out["vo2_medio"]    = pd.to_numeric(df["Average VO2 (ml/kg/min)"], errors="coerce").round(1)
    out["vo2_picco"]    = pd.to_numeric(df["Peak VO2 (ml/kg/min)"], errors="coerce").round(1)

    # Zone HR → minuti
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

    return out.reset_index(drop=True)


def merge_data(gps_df: pd.DataFrame, hr_df: pd.DataFrame) -> pd.DataFrame:
    """
    Unisce GPS e HR sul campo giocatore_key.
    Giocatori presenti in uno solo dei file vengono comunque inclusi.
    """
    merged = pd.merge(
        gps_df,
        hr_df,
        on="giocatore_key",
        how="outer",
        suffixes=("_gps", "_hr"),
    )

    # Nome visualizzato: preferisce GPS, poi HR
    merged["giocatore"] = merged["giocatore_gps"].combine_first(
        merged["giocatore_hr"]
    )

    cols_to_drop = [c for c in merged.columns if c.endswith(("_gps", "_hr", "_raw"))]
    merged = merged.drop(columns=cols_to_drop, errors="ignore")

    return merged.reset_index(drop=True)


# ──────────────────────────────────────────
# UI — UPLOAD FILE
# ──────────────────────────────────────────

col_up1, col_up2 = st.columns(2)

with col_up1:
    st.subheader("📡 File GPEXE")
    file_gps = st.file_uploader(
        "Carica CSV GPEXE",
        type=["csv"],
        key="upload_gps",
    )

with col_up2:
    st.subheader("❤️ File FirstBeat")
    file_hr = st.file_uploader(
        "Carica Excel FirstBeat",
        type=["xlsx", "xls"],
        key="upload_hr",
    )

if not file_gps and not file_hr:
    st.info("Carica almeno uno dei due file per iniziare.")
    st.stop()

# ──────────────────────────────────────────
# PARSING
# ──────────────────────────────────────────

gps_df = None
hr_df  = None

if file_gps:
    try:
        gps_df = parse_gpexe(file_gps)
    except Exception as e:
        st.error(f"Errore lettura GPEXE: {e}")

if file_hr:
    try:
        hr_df = parse_firstbeat(file_hr)
    except Exception as e:
        st.error(f"Errore lettura FirstBeat: {e}")

# ──────────────────────────────────────────
# MERGE
# ──────────────────────────────────────────

if gps_df is None and hr_df is None:
    st.info("Carica almeno un file GPS (CSV) o FirstBeat (XLSX) per generare il report.")
    st.stop()

if gps_df is not None and hr_df is not None:
    df = merge_data(gps_df, hr_df)
    fonte = "GPS + Cardio"
elif gps_df is not None:
    df = gps_df.rename(columns={"giocatore_raw": "giocatore"}) if "giocatore" not in gps_df.columns else gps_df
    fonte = "Solo GPS"
else:
    df = hr_df.rename(columns={"giocatore_raw": "giocatore"}) if "giocatore" not in hr_df.columns else hr_df
    fonte = "Solo Cardio"

# Pulisci colonne interne
for c in ["giocatore_key", "giocatore_raw", "giocatore_gps", "giocatore_hr"]:
    if c in df.columns:
        df = df.drop(columns=c)

# NaN in parziale (giocatori solo FirstBeat) → False
if "parziale" in df.columns:
    df["parziale"] = df["parziale"].fillna(False).astype(bool)

# Lista figure generate durante la sessione (per l'export HTML)
# Ogni elemento: {"fig": Figure, "label": str}
generated_figs: list = []

def _add_fig(fig, label: str):
    generated_figs.append({"fig": fig, "label": label})

n_giocatori = len(df)
n_parziali = int(df["parziale"].sum()) if "parziale" in df.columns else 0
msg = f"✅ Dati caricati — **{fonte}** | **{n_giocatori} giocatori**"
if n_parziali:
    msg += f" | ⚠️ **{n_parziali} parziali** (esclusi dalla media squadra)"
st.success(msg)

# ──────────────────────────────────────────
# SELEZIONE PARAMETRI
# ──────────────────────────────────────────

st.divider()
st.subheader("⚙️ Seleziona parametri")

all_labels = {}
if gps_df is not None:
    all_labels.update(GPS_COLS)
if hr_df is not None:
    all_labels.update(HR_COLS)

# Filtra solo colonne effettivamente presenti nel df
available = {
    label: col
    for label, col in all_labels.items()
    if col in df.columns
}

default_labels = list(available.keys())[:8]  # prime 8 come default

selected_labels = st.multiselect(
    "Parametri da visualizzare nel report",
    options=list(available.keys()),
    default=default_labels,
)

if not selected_labels:
    st.warning("Seleziona almeno un parametro.")
    st.stop()

selected_cols = [available[l] for l in selected_labels]

# ──────────────────────────────────────────
# TABELLA REPORT
# ──────────────────────────────────────────

st.divider()
st.subheader("📋 Report seduta")

# Colonna parziale disponibile?
has_parziale = "parziale" in df.columns

display_cols = ["giocatore"] + selected_cols
if has_parziale:
    display_cols = ["giocatore", "parziale"] + selected_cols

display_df = df[display_cols].copy()

if has_parziale:
    display_df.columns = ["Giocatore", "Parziale"] + selected_labels
    # Simbolo visivo nella colonna nome
    display_df["Giocatore"] = display_df.apply(
        lambda r: r["Giocatore"] + " *" if r["Parziale"] else r["Giocatore"],
        axis=1,
    )
    display_df = display_df.drop(columns=["Parziale"])
else:
    display_df.columns = ["Giocatore"] + selected_labels

# ── Riga media squadra (solo giocatori NON parziali) ──
numeric_labels = [l for l in selected_labels if display_df[l].dtype in ["float64", "float32", "int64"]]

if has_parziale:
    df_full = df[~df["parziale"]]
else:
    df_full = df

if len(df_full) > 0 and numeric_labels:
    mean_row = {"Giocatore": "📊 Media squadra"}
    for l, c in zip(selected_labels, selected_cols):
        if l in numeric_labels and c in df_full.columns:
            mean_row[l] = round(df_full[c].mean(), 1)
        else:
            mean_row[l] = None
    mean_df = pd.DataFrame([mean_row])
    display_df = pd.concat([display_df, mean_df], ignore_index=True)

# Formattazione numerica
float_fmt = {col: "{:.1f}" for col in selected_labels if display_df[col].dtype in ["float64", "float32"]}

def _highlight_mean(row):
    if row["Giocatore"] == "📊 Media squadra":
        return ["font-weight: bold; background-color: #1a1a2e"] * len(row)
    if str(row["Giocatore"]).endswith(" *"):
        return ["color: #aaaaaa; font-style: italic"] * len(row)
    return [""] * len(row)

st.dataframe(
    display_df.style
        .format(float_fmt, na_rep="—")
        .apply(_highlight_mean, axis=1),
    use_container_width=True,
    hide_index=True,
)

# Download CSV
csv_bytes = display_df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="⬇️ Scarica report CSV",
    data=csv_bytes,
    file_name="report_seduta.csv",
    mime="text/csv",
)

# ──────────────────────────────────────────
# GRAFICI
# ──────────────────────────────────────────

st.divider()
st.subheader("📈 Grafici personalizzati")

# Tutti i parametri disponibili dai file caricati (non solo quelli in tabella)
all_available = {}
if gps_df is not None:
    # GPS: solo se ha almeno un dato valido
    all_available.update({
        lbl: col for lbl, col in GPS_COLS.items()
        if col in df.columns and df[col].notna().any()
    })
if hr_df is not None:
    # HR: includi sempre se la colonna esiste (anche se tutta NaN — es. HRR non presente nel file)
    all_available.update({
        lbl: col for lbl, col in HR_COLS.items()
        if col in df.columns
    })
all_labels_list = list(all_available.keys())

# DataFrame completo per i grafici (tutti i parametri, senza la riga media)
plot_df = df.copy()
if "parziale" in plot_df.columns:
    plot_df = plot_df.drop(columns=["parziale"])
# Rinomina giocatore per display
plot_df = plot_df.rename(columns={"giocatore": "Giocatore"})
# Rinomina colonne interne → label leggibili
col_to_label = {v: k for k, v in all_available.items()}
plot_df = plot_df.rename(columns=col_to_label)
# Aggiungi suffisso * ai parziali
if "parziale" in df.columns:
    parziali_mask = df["parziale"].fillna(False).values
    plot_df["Giocatore"] = [
        name + " *" if p else name
        for name, p in zip(plot_df["Giocatore"], parziali_mask)
    ]

st.caption("Puoi scegliere qualsiasi parametro GPS o cardio disponibile, indipendentemente da quelli selezionati nella tabella.")

col_g1, col_g2 = st.columns([1, 3])

with col_g1:
    chart_type = st.selectbox(
        "Tipo di grafico",
        ["Barre singolo param", "Barre doppie (doppio asse)", "Scatter X vs Y", "Radar"],
        key="chart_type_main",
    )

# ── Barre singolo parametro ──
if chart_type == "Barre singolo param":
    with col_g2:
        param_a = st.selectbox("Parametro", all_labels_list, key="bar1_param")

    orient = st.radio("Orientamento", ["Verticale", "Orizzontale"], horizontal=True, key="bar1_orient")

    sort_df = plot_df[["Giocatore", param_a]].dropna().sort_values(
        param_a, ascending=(orient == "Orizzontale")
    )
    if orient == "Verticale":
        fig = px.bar(
            sort_df, x="Giocatore", y=param_a,
            color=param_a, color_continuous_scale="Blues",
            title=param_a, text_auto=".1f",
        )
    else:
        fig = px.bar(
            sort_df, y="Giocatore", x=param_a, orientation="h",
            color=param_a, color_continuous_scale="Blues",
            title=param_a, text_auto=".1f",
        )
    fig.update_layout(showlegend=False, coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)
    _add_fig(fig, f"Barre — {param_a}")

# ── Barre doppie su doppio asse Y ──
elif chart_type == "Barre doppie (doppio asse)":
    with col_g2:
        c1, c2 = st.columns(2)
        with c1:
            param_a = st.selectbox("Parametro asse sinistra (barre)", all_labels_list, key="dual_a")
        with c2:
            param_b = st.selectbox(
                "Parametro asse destra (linea)",
                [l for l in all_labels_list if l != param_a],
                key="dual_b",
            )

    dual_df = plot_df[["Giocatore", param_a, param_b]].dropna(subset=[param_a]).sort_values(param_a, ascending=False)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=dual_df["Giocatore"],
        y=dual_df[param_a],
        name=param_a,
        marker_color="#005BAC",
        yaxis="y1",
        text=dual_df[param_a].round(1),
        textposition="outside",
    ))
    fig.add_trace(go.Scatter(
        x=dual_df["Giocatore"],
        y=dual_df[param_b],
        name=param_b,
        mode="lines+markers+text",
        line=dict(color="#F4B400", width=2),
        marker=dict(size=8),
        text=dual_df[param_b].round(1),
        textposition="top center",
        yaxis="y2",
    ))
    fig.update_layout(
        title=f"{param_a}  vs  {param_b}",
        yaxis=dict(title=param_a, showgrid=False),
        yaxis2=dict(title=param_b, overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        barmode="group",
    )
    st.plotly_chart(fig, use_container_width=True)
    _add_fig(fig, f"Doppio asse — {param_a} (barre, asse sx) · {param_b} (linea, asse dx)")

# ── Scatter X vs Y ──
elif chart_type == "Scatter X vs Y":
    with col_g2:
        c1, c2 = st.columns(2)
        with c1:
            param_x = st.selectbox("Asse X", all_labels_list, key="sc_x")
        with c2:
            param_y = st.selectbox(
                "Asse Y",
                [l for l in all_labels_list if l != param_x],
                key="sc_y",
            )

    scatter_df = plot_df[["Giocatore", param_x, param_y]].dropna()
    fig = px.scatter(
        scatter_df,
        x=param_x, y=param_y,
        text="Giocatore",
        title=f"{param_x}  vs  {param_y}",
        trendline="ols",
        trendline_color_override="#F4B400",
    )
    fig.update_traces(
        selector=dict(mode="markers+text"),
        textposition="top center",
        marker=dict(size=10, color="#005BAC"),
    )
    st.plotly_chart(fig, use_container_width=True)
    _add_fig(fig, f"Scatter — asse X: {param_x} · asse Y: {param_y}")

# ── Radar ──
elif chart_type == "Radar":
    with col_g2:
        radar_params = st.multiselect(
            "Parametri radar (min 3)",
            all_labels_list,
            default=all_labels_list[:5],
            key="radar_params",
        )

    if len(radar_params) >= 3:
        radar_df = plot_df[["Giocatore"] + radar_params].copy().dropna()
        for col in radar_params:
            mn, mx = radar_df[col].min(), radar_df[col].max()
            radar_df[col] = (radar_df[col] - mn) / (mx - mn) if mx > mn else 0.5

        fig = go.Figure()
        for _, row in radar_df.iterrows():
            vals = [row[p] for p in radar_params] + [row[radar_params[0]]]
            cats = radar_params + [radar_params[0]]
            fig.add_trace(go.Scatterpolar(
                r=vals, theta=cats, fill="toself",
                name=row["Giocatore"], opacity=0.55,
            ))
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=False, range=[0, 1])),
            title="Radar — valori normalizzati 0-1",
        )
        st.plotly_chart(fig, use_container_width=True)
        _add_fig(fig, f"Radar — parametri: {', '.join(radar_params)}")
    else:
        st.info("Seleziona almeno 3 parametri.")

# ── Grafico zone cardiache (sempre visibile se disponibile) ──
st.divider()
st.subheader("📊 Confronto multi-parametro (barre raggruppate)")
compare_params = st.multiselect(
    "Scegli i parametri da confrontare",
    all_labels_list,
    default=all_labels_list[:3],
    key="compare_multi",
)
if len(compare_params) >= 2:
    melt_df = plot_df[["Giocatore"] + compare_params].melt(
        id_vars="Giocatore", var_name="Parametro", value_name="Valore",
    )
    fig_multi = px.bar(
        melt_df, x="Giocatore", y="Valore",
        color="Parametro", barmode="group",
        title="Confronto parametri multipli",
    )
    st.plotly_chart(fig_multi, use_container_width=True)
    _add_fig(fig_multi, f"Confronto multiplo — {', '.join(compare_params)}")
else:
    st.info("Seleziona almeno 2 parametri.")

# ──────────────────────────────────────────
# ZONE HR — grafico stacked (se disponibile)
# ──────────────────────────────────────────

hr_zone_labels = {
    "Zona recupero (min)":         "hr_z_recupero",
    "Zona aerobica 1 (min)":       "hr_z1",
    "Zona aerobica 2 (min)":       "hr_z2",
    "Zona soglia anaerobica (min)":"hr_z3",
    "Zona alta intensità (min)":   "hr_z4",
}

zone_disponibili = [
    lbl for lbl, col in hr_zone_labels.items()
    if col in df.columns and df[col].notna().any()
]

if zone_disponibili and hr_df is not None:
    st.divider()
    st.subheader("❤️ Distribuzione zone cardiache")

    zone_cols_internal = [hr_zone_labels[l] for l in zone_disponibili]
    zone_df = df[["giocatore"] + zone_cols_internal].copy()
    zone_df.columns = ["Giocatore"] + zone_disponibili

    zone_melt = zone_df.melt(
        id_vars="Giocatore",
        var_name="Zona",
        value_name="Minuti",
    )

    colors = ["#4CAF50", "#8BC34A", "#FFC107", "#FF5722", "#F44336"]
    fig3 = px.bar(
        zone_melt,
        x="Giocatore",
        y="Minuti",
        color="Zona",
        barmode="stack",
        title="Tempo in zona cardiaca (minuti)",
        color_discrete_sequence=colors,
    )
    st.plotly_chart(fig3, use_container_width=True)
    _add_fig(fig3, f"Zone cardiache — {', '.join(zone_disponibili)}")

# ──────────────────────────────────────────
# EXPORT HTML (tabella + grafici)
# ──────────────────────────────────────────

st.divider()
st.subheader("⬇️ Scarica report completo")

def _build_html_report(table_df: pd.DataFrame, figs: list, fonte: str) -> str:
    """
    Genera un file HTML auto-contenuto con:
    - intestazione seduta
    - tabella dati
    - tutti i grafici interattivi (plotly embedded)
    figs: lista di dict {"fig": Figure, "label": str}
    """
    import plotly.io as pio
    import copy
    from datetime import datetime

    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    # Tabella HTML
    table_html = table_df.to_html(
        index=False,
        border=0,
        classes="report-table",
        na_rep="—",
        float_format=lambda x: f"{x:.1f}",
    )

    # Palette colori vivaci per l'export
    EXPORT_COLORS = [
        "#00AEEF", "#F4B400", "#2ECC71", "#E74C3C", "#9B59B6",
        "#FF6692", "#FFA15A", "#19D3F3", "#B6E880", "#FF97FF",
    ]

    # Grafici HTML — sfondo scuro + colori tracce espliciti
    charts_html = ""
    for i, entry in enumerate(figs):
        fig_copy = copy.deepcopy(entry["fig"])

        # Assegna colori vivaci alle tracce che non li hanno già espliciti
        for t_idx, trace in enumerate(fig_copy.data):
            color = EXPORT_COLORS[t_idx % len(EXPORT_COLORS)]
            # Bar traces
            if hasattr(trace, "marker") and trace.marker is not None:
                if not getattr(trace.marker, "color", None) or \
                   str(getattr(trace.marker, "color", "")).startswith(("#0", "#1", "#2", "#3", "rgb(0", "rgb(1", "rgb(2")):
                    trace.marker.color = color
            # Scatter/line traces
            if hasattr(trace, "line") and trace.line is not None:
                if not getattr(trace.line, "color", None):
                    trace.line.color = color

        fig_copy.update_layout(
            paper_bgcolor="#0e1117",
            plot_bgcolor="#1a1a2e",
            colorway=EXPORT_COLORS,
            font=dict(color="#fafafa"),
            xaxis=dict(
                gridcolor="#333",
                zerolinecolor="#555",
                tickfont=dict(color="#fafafa"),
                title_font=dict(color="#fafafa"),
            ),
            yaxis=dict(
                gridcolor="#333",
                zerolinecolor="#555",
                tickfont=dict(color="#fafafa"),
                title_font=dict(color="#fafafa"),
            ),
            legend=dict(
                bgcolor="#1a1a2e",
                font=dict(color="#fafafa"),
            ),
            title_font=dict(color="#fafafa"),
        )
        label = entry["label"]
        chart_div = pio.to_html(
            fig_copy,
            full_html=False,
            include_plotlyjs="cdn" if i == 0 else False,
            config={"responsive": True},
        )
        charts_html += f"""
        <div class="chart-block">
            <div class="chart-label">📊 Grafico {i+1} — {label}</div>
            {chart_div}
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Report Seduta — Performance Hub</title>
<style>
  body {{
    font-family: 'Segoe UI', Arial, sans-serif;
    background: #0e1117;
    color: #fafafa;
    margin: 0;
    padding: 24px 32px;
  }}
  h1 {{ color: #00AEEF; margin-bottom: 4px; }}
  .meta {{ color: #aaa; font-size: 13px; margin-bottom: 32px; }}
  .section-title {{
    font-size: 16px;
    font-weight: 600;
    color: #00AEEF;
    border-bottom: 1px solid #333;
    padding-bottom: 6px;
    margin: 32px 0 16px;
  }}
  .report-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }}
  .report-table th {{
    background: #1a1a2e;
    color: #00AEEF;
    padding: 8px 12px;
    text-align: left;
    border-bottom: 2px solid #00AEEF;
  }}
  .report-table td {{
    padding: 7px 12px;
    border-bottom: 1px solid #222;
  }}
  .report-table tr:last-child td {{
    font-weight: bold;
    background: #1a1a2e;
    color: #F4B400;
  }}
  .report-table tr:hover td {{ background: #1c2333; }}
  .chart-block {{ margin: 40px 0; }}
  .chart-label {{
    font-size: 14px;
    font-weight: 600;
    color: #00AEEF;
    background: #1a1a2e;
    padding: 8px 14px;
    border-left: 3px solid #00AEEF;
    margin-bottom: 8px;
    border-radius: 0 4px 4px 0;
  }}
  @media print {{
    body {{ background: white; color: black; padding: 16px; }}
    h1 {{ color: #005BAC; }}
    .section-title {{ color: #005BAC; }}
    .report-table th {{ background: #005BAC; color: white; }}
    .report-table tr:last-child td {{ background: #eee; color: #333; }}
  }}
</style>
</head>
<body>
<h1>⚽ Performance Hub — Report Seduta</h1>
<div class="meta">Fonte dati: {fonte} &nbsp;|&nbsp; Generato il {now}</div>

<div class="section-title">📋 Dati seduta</div>
{table_html}

<div class="section-title">📈 Grafici</div>
{charts_html if charts_html else "<p style='color:#aaa'>Nessun grafico generato.</p>"}

</body>
</html>"""
    return html


col_exp1, col_exp2 = st.columns([2, 1])

with col_exp1:
    st.write("Esporta tabella + tutti i grafici visualizzati in questa sessione in un unico file HTML interattivo. Aprilo nel browser e usa **Stampa → Salva come PDF** per ottenere un PDF.")

with col_exp2:
    html_report = _build_html_report(display_df, generated_figs, fonte)  # generated_figs = lista di dict
    st.download_button(
        label="⬇️ Scarica Report HTML",
        data=html_report.encode("utf-8"),
        file_name="report_seduta.html",
        mime="text/html",
        use_container_width=True,
    )
