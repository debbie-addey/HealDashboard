import requests
import pandas as pd
import streamlit as st
import plotly.express as px
from datetime import datetime
import os
import streamlit as st
from pandas.tseries.offsets import DateOffset
import plotly.graph_objects as go

# -------------------------------
# REDCap API Config 
# -------------------------------
API_URL = 'https://redcap.bccrc.ca/api/'
API_TOKEN = st.secrets ["REDCAP_API_TOKEN"]

# -------------------------------
# Fetch data from REDCap
# -------------------------------
@st.cache_data(ttl=1800)  # cache for 0.5 hour
def fetch_redcap_data():
    payload = {
        "token": API_TOKEN,
        "content": "record",
        "format": "json",
        "type": "flat"
    }
    response = requests.post(API_URL, data=payload)
    response.raise_for_status()
    return pd.DataFrame(response.json())

df = fetch_redcap_data()

st.image(
    "https://raw.githubusercontent.com/debbie-addey/HealDashboard/main/images/Atlantic%20PATH%20LOGO%20MASTER1.jpg",
    use_container_width=True
)
st.markdown("""
    <style>
        div[data-testid="stMetricLabel"] > div {
            white-space: normal;
            text-align: center;
            line-height: 1.1em;
        }
    </style>
""", unsafe_allow_html=True)


# -------------------------------
# KPIs
# -------------------------------

invited_count = (df["administrative_complete"]=="2").sum()

# Ensure consent_complete is string type
df["consent_complete"] = df["consent_complete"].astype(str)

# Filter for participants who have completed consent
df_consented = df[df["consent_complete"] == "2"].copy()

# Exclude blank/null participation_status
df_consented = df_consented[df_consented["participation_status"].astype(str).str.strip() != ""]


# Count total consented participants
consented_count = df_consented.shape[0]


# Recall 1 invited = HEAL completed
heal_completed_natural = (
    (df["heal_qx_complete"] == "2") &
    (df["hlq_status"] != "force_complete")
).sum()

heal_completed_forced = (
    (df["heal_qx_complete"] != "2") &
    (df["hlq_status"] == "force_complete")
).sum()

heal_completed_total = heal_completed_natural + heal_completed_forced
heal_completed_total = int(heal_completed_total)



# Recall 2 invited = enrolment arm flag
#recall2_invited = ((df["redcap_event_name"] == "enrolment_arm_1") & (df["asa_act_complete"] == "1")).sum()

# Recall 3 invited = followup arm flag
#recall3_invited = ((df["redcap_event_name"] == "followup_arm_1") & (df["asa_act_complete"] == "1")).sum()

# Recall 4 invited = followup2 arm flag
#recall4_invited = ((df["redcap_event_name"] == "followup2_arm_1") & (df["asa_act_complete"] == "1")).sum()



# Total invited across all recalls
total_invited = invited_count

# Layout: 6 KPIs in one row
col1, col6, col7, col8 = st.columns(4)
col1.metric("Invited", total_invited)
col7.metric("HEAL QX Completed", heal_completed_total)
col8.metric("Force Complete", heal_completed_forced)
#col2.metric("Recall1 Invited", heal_completed_total)
#col3.metric("Recall2 Invited", recall2_invited)
#col4.metric("Recall3 Invited", recall3_invited)
#col5.metric("Recall4 Invited", recall4_invited)
col6.metric("Consented", consented_count)

# Ensure hlq_status exists
if "hlq_status" in df.columns:
    df["hlq_status"] = df["hlq_status"].astype(str)
else:
    df["hlq_status"] = ""


# -------------------------------
# Participation Status Breakdown
# -------------------------------
# Map participation status
if "participation_status" in df_consented.columns:
    df_consented["participation_status"] = df_consented["participation_status"].astype(str)
    participation_map = {"0": "Declined to Participate", "1": "Agreed to Participate"}
    df_consented["participation_status_label"] = df_consented["participation_status"].map(participation_map)
else:
    df_consented["participation_status_label"] = "Unknown"
    
# Count Agreed vs Declined
participation_counts = df_consented["participation_status_label"].value_counts().reset_index()
participation_counts.columns = ["Status", "Count"]

if not participation_counts.empty:
    fig1 = px.bar(
        participation_counts,
        x="Status",
        y="Count",
        title="Consent Status",
        text="Count",
        color="Status"
    )
    fig1.update_layout(yaxis_title="Number of Participants", xaxis_title="Consent Status")
    st.plotly_chart(fig1)


# ======================================================
# HEAL Qx Status Breakdown (final, reconciled version)
# ======================================================

# Safety check
required_cols = {
    "study_id",
    "heal_qx_complete",
    "hlq_status",
    "today_date",
    "participation_status",
    "redcap_event_name"
}

if required_cols.issubset(df.columns):

  # --------------------------------------------------
    # 1. Scope to HEAL Qx event (CRITICAL)
    # --------------------------------------------------
    heal_df = df[df["redcap_event_name"] == "enrolment_arm_1"].copy()

    # --------------------------------------------------
    # 2. Normalize data types
    # --------------------------------------------------
    heal_df["heal_qx_complete"] = heal_df["heal_qx_complete"].astype(str)
    heal_df["participation_status"] = heal_df["participation_status"].astype(str)
    heal_df["today_date"] = pd.to_datetime(heal_df["today_date"], errors="coerce")

    # --------------------------------------------------
    # 3. Assign status labels (ordered, exclusive)
    # --------------------------------------------------
    heal_df["heal_qx_complete_label"] = None

    # 1️⃣ Force Complete
    heal_df.loc[
        heal_df["hlq_status"] == "force_complete",
        "heal_qx_complete_label"
    ] = "Force Complete"

    # 2️⃣ Complete (natural)
    heal_df.loc[
        (heal_df["heal_qx_complete"] == "2") &
        (heal_df["hlq_status"] != "force_complete"),
        "heal_qx_complete_label"
    ] = "Complete"

    # 3️⃣ In Progress
    heal_df.loc[
        (heal_df["heal_qx_complete"] == "0") &
        (heal_df["hlq_status"] != "force_complete") &
        (heal_df["today_date"].notna()),
        "heal_qx_complete_label"
    ] = "In Progress"

    # 4️⃣ Not Started ✅ FIXED LOGIC
    heal_df.loc[
        (heal_df["participation_status"] == "1") &
        (heal_df["today_date"].isna()),
        "heal_qx_complete_label"
    ] = "Not Started"

    # --------------------------------------------------
    # 4. Aggregate counts (UNIQUE participants)
    # --------------------------------------------------
    heal_counts = (
        heal_df
        .dropna(subset=["heal_qx_complete_label"])  # safety
        .groupby("heal_qx_complete_label")["study_id"]
        .nunique()
        .reset_index(name="Count")
    )

    # --------------------------------------------------
    # 5. Plot
    # --------------------------------------------------
    fig = px.bar(
        heal_counts,
        x="heal_qx_complete_label",
        y="Count",
        title="HEAL Qx Status",
        text="Count",
        color="heal_qx_complete_label",
        color_discrete_map={
            "Complete": "#2ca02c",
            "Force Complete": "#1f77b4",
            "In Progress": "#ff7f0e",
            "Not Started": "#d62728",
        }
    )

    fig.update_traces(
        textposition="outside",
        cliponaxis=False
    )

    fig.update_layout(
        xaxis_title="Status",
        yaxis_title="Number of Participants"
    )

    st.plotly_chart(fig)

else:
    st.warning("Required HEAL Qx columns are missing from the dataset.")
# ============================================================
# recalls
# ============================================================

EVENT_ENROL = "enrolment_arm_1"
EVENT_FU1 = "followup_arm_1"
EVENT_FU2 = "followup2_arm_1"
EVENT_FU3 = "followup3_arm_1"

RECALL1_DELAY_DAYS = 14
RECALL2_DELAY_DAYS = 10
RECALL3_DELAY_MONTHS = 6
RECALL4_DELAY_DAYS = 10

today_ts = pd.Timestamp.now().normalize()

# ============================================================
# STEP 1: EXPORT RECORD DATA (ALL EVENTS)
# ============================================================
payload_records = {
    "token": API_TOKEN,
    "content": "record",
    "format": "json",
    "type": "flat",
    "fields[0]": "study_id",
    "fields[1]": "heal_qx_complete",
    "fields[2]": "hlq_status",
    "fields[3]": "asa_act_complete",
    "events[0]": EVENT_ENROL,
    "events[1]": EVENT_FU1,
    "events[2]": EVENT_FU2,
    "events[3]": EVENT_FU3,
    "returnFormat": "json"
}

records = pd.DataFrame(
    requests.post(API_URL, data=payload_records).json()
)

# ============================================================
# STEP 2: SPLIT BY EVENT
# ============================================================
enrol_df = records[records["redcap_event_name"] == EVENT_ENROL].copy()
fu1_df = records[records["redcap_event_name"] == EVENT_FU1].copy()
fu2_df = records[records["redcap_event_name"] == EVENT_FU2].copy()
fu3_df = records[records["redcap_event_name"] == EVENT_FU3].copy()

# ============================================================
# STEP 3: EXPORT LOGS
# ============================================================
payload_log = {
    "token": API_TOKEN,
    "content": "log",
    "format": "json",
    "logtype": "record",
    "returnFormat": "json"
}

logs = pd.DataFrame(
    requests.post(API_URL, data=payload_log).json()
)

logs["timestamp"] = pd.to_datetime(logs["timestamp"], errors="coerce")

# ============================================================
# STEP 4: COMPLETION TIMESTAMPS
# ============================================================
heal_complete = (
    logs[logs["details"].str.contains("heal_qx_complete = '2'", na=False)]
    .sort_values("timestamp")
    .drop_duplicates("record", keep="last")
    [["record", "timestamp"]]
    .rename(columns={"record": "study_id", "timestamp": "heal_complete_time"})
)

recall1_complete = (
    logs[logs["details"].str.contains("asa_act_complete = '1'", na=False)]
    .sort_values("timestamp")
    .drop_duplicates("record", keep="last")
    [["record", "timestamp"]]
    .rename(columns={"record": "study_id", "timestamp": "recall1_complete_time"})
)

# ============================================================
# STEP 5: BUILD PARTICIPANT-LEVEL TABLE
# ============================================================
combined = (
    enrol_df[["study_id", "heal_qx_complete", "hlq_status", "asa_act_complete"]]
    .rename(columns={"asa_act_complete": "recall1_complete_flag"})
    .merge(heal_complete, on="study_id", how="left")
    .merge(recall1_complete, on="study_id", how="left")
    .merge(
        fu1_df[["study_id", "asa_act_complete"]]
        .rename(columns={"asa_act_complete": "recall2_complete_flag"}),
        on="study_id", how="left"
    )
    .merge(
        fu2_df[["study_id", "asa_act_complete"]]
        .rename(columns={"asa_act_complete": "recall3_complete_flag"}),
        on="study_id", how="left"
    )
    .merge(
        fu3_df[["study_id", "asa_act_complete"]]
        .rename(columns={"asa_act_complete": "recall4_complete_flag"}),
        on="study_id", how="left"
    )
    .drop_duplicates("study_id")
)

# ============================================================
# STEP 6: RECALL LOGIC
# ============================================================
# ---- Recall 1 ----
combined["recall1_scheduled"] = (
    (combined["heal_qx_complete"] == "2") |
    (combined["hlq_status"] == "force_complete")
)

combined["recall1_invited"] = (
    combined["recall1_scheduled"] &
    ((today_ts - combined["heal_complete_time"]).dt.days >= RECALL1_DELAY_DAYS)
)

combined["recall1_completed"] = combined["recall1_complete_flag"] == "1"

# ---- Recall 2 ----
combined["recall2_scheduled"] = combined["recall1_completed"]

combined["recall2_invited"] = (
    combined["recall2_scheduled"] &
    ((today_ts - combined["recall1_complete_time"]).dt.days >= RECALL2_DELAY_DAYS)
)

combined["recall2_completed"] = combined["recall2_complete_flag"] == "1"

# ---- Recall 3 ----
combined["recall3_scheduled"] = combined["recall2_completed"]

combined["recall3_invited"] = (
    combined["recall3_scheduled"] &
    (today_ts >= combined["recall1_complete_time"] + DateOffset(months=RECALL3_DELAY_MONTHS))
)

combined["recall3_completed"] = combined["recall3_complete_flag"] == "1"

# ---- Recall 4 ----
combined["recall4_scheduled"] = combined["recall3_completed"]

combined["recall4_invited"] = (
    combined["recall4_scheduled"] &
    ((today_ts - combined["recall1_complete_time"]).dt.days >= RECALL4_DELAY_DAYS)
)

combined["recall4_completed"] = combined["recall4_complete_flag"] == "1"

# ============================================================
# STEP 7: SUMMARY TABLE
# ============================================================
recall_summary = pd.DataFrame([
    {"Recall": "Recall 1", "Scheduled": combined["recall1_scheduled"].sum(),
     "Invited": combined["recall1_invited"].sum(), "Completed": combined["recall1_completed"].sum()},
    {"Recall": "Recall 2", "Scheduled": combined["recall2_scheduled"].sum(),
     "Invited": combined["recall2_invited"].sum(), "Completed": combined["recall2_completed"].sum()},
    {"Recall": "Recall 3", "Scheduled": combined["recall3_scheduled"].sum(),
     "Invited": combined["recall3_invited"].sum(), "Completed": combined["recall3_completed"].sum()},
    {"Recall": "Recall 4", "Scheduled": combined["recall4_scheduled"].sum(),
     "Invited": combined["recall4_invited"].sum(), "Completed": combined["recall4_completed"].sum()},
])

# ============================================================
# STEP 8: CHARTS (2×2 LAYOUT)
# ============================================================
#st.header("Recall Progress Overview")

COLOR_MAP = {
    "Scheduled": "#6c757d",
    "Invited": "#f0ad4e",
    "Completed": "#5cb85c",
}

def plot_recall(row):
    df = pd.DataFrame({
        "Status": ["Scheduled", "Invited", "Completed"],
        "Count": [row["Scheduled"], row["Invited"], row["Completed"]],
    })

    fig = px.bar(
        df,
        x="Status",
        y="Count",
        color="Status",
        text="Count",
        title=row.name,
        color_discrete_map=COLOR_MAP
    )

    fig.update_traces(textposition="outside")

    fig.update_layout(
        yaxis_title="Participants",
        xaxis_title="",
        showlegend=False,   # 🔑 turn off per-chart legend
        uniformtext_minsize=10,
        uniformtext_mode="hide"
    )

    return fig



import plotly.graph_objects as go

def legend_only():
    fig = go.Figure()

    for label, color in COLOR_MAP.items():
        fig.add_trace(
            go.Scatter(
                x=[None],            # <-- critical
                y=[None],            # <-- critical
                mode="markers",
                marker=dict(
                    size=14,
                    color=color,
                    opacity=1          # legend uses this
                ),
                name=label,
                showlegend=True,
                hoverinfo="skip"
            )
        )

    fig.update_layout(
        legend_title_text="Stage",
        xaxis_visible=False,
        yaxis_visible=False,
        margin=dict(l=0, r=0, t=10, b=0),
        height=180
    )

    return fig






st.header("Recall Progress Overview")

# Index for easy lookup
r = recall_summary.set_index("Recall")

# Main layout: charts + legend
main_col, legend_col = st.columns([4, 1])

with main_col:
    # ---- ROW 1 ----
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(plot_recall(r.loc["Recall 1"]), use_container_width=True)
    with col2:
        st.plotly_chart(plot_recall(r.loc["Recall 2"]), use_container_width=True)

    # ---- ROW 2 ----
    col3, col4 = st.columns(2)
    with col3:
        st.plotly_chart(plot_recall(r.loc["Recall 3"]), use_container_width=True)
    with col4:
        st.plotly_chart(plot_recall(r.loc["Recall 4"]), use_container_width=True)

with legend_col:
    st.markdown("### Legend")
    st.plotly_chart(legend_only(), use_container_width=True)
























































