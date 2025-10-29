import requests
import pandas as pd
import streamlit as st
import plotly.express as px
from datetime import datetime
import os

# -------------------------------
# REDCap API Config
# -------------------------------
API_URL = 'https://redcap.bccrc.ca/api/'
API_TOKEN = st.secrets ["REDCAP_API_TOKEN"]

# -------------------------------
# Fetch data from REDCap
# -------------------------------
@st.cache_data(ttl=3600)  # cache for 1 hour
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
df["consent_complete"] = df["consent_complete"].astype(str)
invited_count = (df["administrative_complete"]=="2").sum()

# Filter for participants who have completed consent
df_consented = df[df["consent_complete"] == "2"].copy()

# Count total consented participants
consented_count = df_consented.shape[0]



# Recall 1 invited = HEAL completed
recall1_invited = (df["heal_qx_complete"] == "2").sum() if "heal_qx_complete" in df.columns else 0

# Recall 2 invited = enrolment arm flag
recall2_invited = ((df["redcap_event_name"] == "enrolment_arm_1") & (df["asa_act_complete"] == "1")).sum()

# Recall 3 invited = followup arm flag
recall3_invited = ((df["redcap_event_name"] == "followup_arm_1") & (df["asa_act_complete"] == "1")).sum()

# Recall 4 invited = followup2 arm flag
recall4_invited = ((df["redcap_event_name"] == "followup2_arm_1") & (df["asa_act_complete"] == "1")).sum()

# Total invited across all recalls
total_invited = invited_count

# Layout: 6 KPIs in one row
col1, col6, col2, col3, col4, col5 = st.columns(6)
col1.metric("Invited", total_invited)
col2.metric("Recall1 Invited", recall1_invited)
col3.metric("Recall2 Invited", recall2_invited)
col4.metric("Recall3 Invited", recall3_invited)
col5.metric("Recall4 Invited", recall4_invited)
col6.metric("Consented", consented_count)


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

    fig1 = px.bar(
        participation_counts,
        x="Status",
        y="Count",
        title="Consent Status",
        text="Count",
        color="Status"
    )
    st.plotly_chart(fig1)


# -------------------------------
# HEAL Completion Status Breakdown
# -------------------------------
if "heal_qx_complete" in df.columns:
    heal_map = {"0": "Incomplete / Not Started", "2": "Complete"}
    df["heal_qx_complete_label"] = df["heal_qx_complete"].map(heal_map)

    heal_counts = df["heal_qx_complete_label"].value_counts().reset_index()
    heal_counts.columns = ["Status", "Count"]

    fig2 = px.bar(heal_counts, x="Status", y="Count",
                  title="HEAL_QX Status", text="Count", color="Status")
    st.plotly_chart(fig2)

# -------------------------------
# Define Event Name Mapping and Order
# -------------------------------
event_map = {
    "enrolment_arm_1": "Recall 1",
    "followup_arm_1": "Recall 2",
    "followup2_arm_1": "Recall 3",
    "followup3_arm_1": "Recall 4"
}
event_order = ["Recall 1", "Recall 2", "Recall 3", "Recall 4"]

# -------------------------------
# ASA24 Completion Status by Event + Invited
# -------------------------------
if "asa_qx_date" in df.columns and "redcap_event_name" in df.columns:
    df["asa_status"] = df["asa_qx_date"].apply(
        lambda x: "Complete" if pd.notnull(x) and str(x).strip() != "" else "Not Complete"
    )
    df["asa_event_label"] = df["redcap_event_name"].map(event_map).fillna(df["redcap_event_name"])

    # Count completions
    asa_counts = (
        df.groupby(["asa_event_label", "asa_status"])
        .size()
        .reset_index(name="Count")
    )

    # Add invited counts for recalls 2+
    invited_rows = []
    for ev in event_map.keys():
        label = event_map[ev]
        if label != "Recall 1":
            invited_var = f"{ev}___asa_act_complete"
            if invited_var in df.columns:
                invited_count = (df[invited_var] == "1").sum()
                invited_rows.append({"asa_event_label": label, "asa_status": "Invited", "Count": invited_count})

    asa_counts = pd.concat([asa_counts, pd.DataFrame(invited_rows)], ignore_index=True)

    # Plot
    fig_asa = px.bar(
        asa_counts,
        x="asa_event_label",
        y="Count",
        color="asa_status",
        category_orders={"asa_event_label": event_order},
        barmode="group",
        title="ASA24 Recall",
        text="Count"
    )
    fig_asa.update_layout(xaxis_title="Recall", yaxis_title="Number of Participants")
    st.plotly_chart(fig_asa)

# -------------------------------
# ACT Completion Status by Event + Invited
# -------------------------------
if "act_qx_date" in df.columns and "redcap_event_name" in df.columns:
    df["act_status"] = df["act_qx_date"].apply(
        lambda x: "Complete" if pd.notnull(x) and str(x).strip() != "" else "Not Complete"
    )
    df["act_event_label"] = df["redcap_event_name"].map(event_map).fillna(df["redcap_event_name"])

    # Count completions
    act_counts = (
        df.groupby(["act_event_label", "act_status"])
        .size()
        .reset_index(name="Count")
    )

    # Add invited counts for recalls 2+
    invited_rows = []
    for ev in event_map.keys():
        label = event_map[ev]
        if label != "Recall 1":
            invited_var = f"{ev}___asa_act_complete"
            if invited_var in df.columns:
                invited_count = (df[invited_var] == "1").sum()
                invited_rows.append({"act_event_label": label, "act_status": "Invited", "Count": invited_count})

    act_counts = pd.concat([act_counts, pd.DataFrame(invited_rows)], ignore_index=True)

    # Plot
    fig_act = px.bar(
        act_counts,
        x="act_event_label",
        y="Count",
        color="act_status",
        category_orders={"act_event_label": event_order},
        barmode="group",
        title="ACT24 Recall",
        text="Count"
    )
    fig_act.update_layout(xaxis_title="Recall", yaxis_title="Number of Participants")
    st.plotly_chart(fig_act)































