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

# -------------------------------
# KPIs
# -------------------------------
invited_count = (df["administrative_complete"] == "2").sum()
consented_count = (df["consent_complete"] == "2").sum()

col1, col2 = st.columns(2)
col1.metric("Total Invited", invited_count)
col2.metric("Total Completed Consent", consented_count)

# -------------------------------
# Participation Status Breakdown
# -------------------------------
if "participation_status" in df.columns:
    # Map values to labels
    participation_map = {
        "0": "Declined to Participate",
        "1": "Agreed to Participate"
    }
    df["participation_status_label"] = df["participation_status"].map(participation_map)

    participation_counts = df["participation_status_label"].value_counts().reset_index()
    participation_counts.columns = ["Status", "Count"]

    fig1 = px.bar(
        participation_counts,
        x="Status",
        y="Count",
        title="Participation Status Breakdown",
        text="Count",
        color="Status"  # legend
    )
    st.plotly_chart(fig1)

# -------------------------------
# HEAL Completion Status Breakdown
# -------------------------------
if "heal_qx_complete" in df.columns:
    # Map values to labels
    heal_map = {
        "0": "Incomplete / Not Started",
        "2": "Complete"
    }
    df["heal_qx_complete_label"] = df["heal_qx_complete"].map(heal_map)

    heal_counts = df["heal_qx_complete_label"].value_counts().reset_index()
    heal_counts.columns = ["Status", "Count"]

    fig2 = px.bar(
        heal_counts,
        x="Status",
        y="Count",
        title="HEAL Questionnaire Completion",
        text="Count",
        color="Status"  # legend
    )
    st.plotly_chart(fig2)

# -------------------------------
# Last updated time
# -------------------------------

st.caption(f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
