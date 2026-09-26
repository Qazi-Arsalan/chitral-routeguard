import json
import os
import folium
from folium import Icon, Marker
from pydantic import BaseModel, Field
import streamlit as st
from streamlit_folium import st_folium
from google import genai
from google.genai import types

import db

# ---------------------------------------------------------------------------
# 1. Page Configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Chitral RouteGuard",
    page_icon="🏔️",
    layout="wide",
)

db.init_db()

# ---------------------------------------------------------------------------
# 2. Pydantic Schema & Gemini AI Parser
# ---------------------------------------------------------------------------


class RoadReport(BaseModel):
    location: str = Field(
        description="The specific road, pass, or village mentioned (e.g., Kuragh, Lowari Tunnel, Drosh, Booni, Shandur)."
    )
    status: str = Field(
        description="Road status. MUST be one of: 'BLOCKED', 'ONE_WAY', 'HAZARD', or 'CLEAR'."
    )
    cause: str = Field(
        description="Reason for blockage or hazard (e.g., Landslide, Rockfall, Avalanche, Snow, Flooding, Clear)."
    )
    severity: str = Field(
        description="Severity level. MUST be one of: 'HIGH', 'MEDIUM', 'LOW'."
    )
    estimated_clearance: str = Field(
        description="Estimated time to clear, or 'Unknown' if not mentioned."
    )
    summary_urdu: str = Field(
        description="A concise 1-sentence summary of the report written in plain Urdu for SMS broadcasts."
    )


def process_report_with_ai(raw_text: str) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        st.error(
            "API Key missing! Set GEMINI_API_KEY in terminal or hardcode it in app.py."
        )
        return None

    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
        You are an emergency traffic and hazard coordination AI for Chitral, Pakistan.
        Analyze the following crowd-sourced report from a driver, traveler, or checkpost guard.
        Extract the route information accurately into the structured format.

        Report Input: "{raw_text}"
        """

        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=RoadReport,
                temperature=0.1,
            ),
        )

        data = json.loads(response.text)
        return data
    except Exception as e:
        st.error(f"AI Processing Error: {e}")
        return None


# ---------------------------------------------------------------------------
# 3. User Interface (Streamlit Dashboard)
# ---------------------------------------------------------------------------

st.title("🏔️ Chitral RouteGuard")
st.caption("Low-Bandwidth AI Road & Landslide Advisory System | Emergency Portal")

reports = db.get_all_reports()

# Sidebar Stats
st.sidebar.header("📍 Corridor Overview")
total_routes = len(reports)
blocked_routes = sum(1 for r in reports if r["status"] == "BLOCKED")
st.sidebar.metric("Monitored Passes", total_routes)
st.sidebar.metric("Active Blockages / Hazards", blocked_routes)

# Main Navigation Tabs
tab1, tab2, tab3 = st.tabs([
    "📢 Public Road Status (2G View)",
    "🗺️ Interactive Corridor Map",
    "📱 Dispatch / Driver Input Portal",
])

# --- TAB 1: PUBLIC VIEW ---
with tab1:
    st.subheader("Live Pass & Route Advisories")
    st.info("💡 Light-weight mode enabled for 2G / weak mobile connections.")

    for r in reports:
        status_color = "🔴" if r["status"] == "BLOCKED" else ("🟡" if r["status"] == "ONE_WAY" else "🟢")

        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.markdown(f"### {status_color} {r['location']}")
                st.markdown(f"**Urdu Summary:** {r['summary_urdu']}")
            with col2:
                st.markdown(f"**Status:** `{r['status']}`")
                st.markdown(f"**Cause:** {r['cause']}")
            with col3:
                st.markdown(f"**Est. Clearance:** {r['estimated_clearance']}")
                st.markdown(f"**Reported At:** {r['timestamp']}")

# --- TAB 2: INTERACTIVE MAP ---
with tab2:
    st.subheader("Chitral Emergency Route Map")
    st.caption("Live map visualizer showing hazard locations and status pins.")

    # Initialize Folium Map centered near Chitral
    m = folium.Map(location=[35.8510, 71.7869], zoom_start=8)

    for r in reports:
        coords = db.get_coords_for_location(r["location"])

        # Determine Marker Color based on Status
        if r["status"] == "BLOCKED":
            color = "red"
            icon_type = "exclamation-sign"
        elif r["status"] in ["ONE_WAY", "HAZARD"]:
            color = "orange"
            icon_type = "warning-sign"
        else:
            color = "green"
            icon_type = "ok-sign"

        popup_html = f"""
        <b>Location:</b> {r['location']}<br>
        <b>Status:</b> {r['status']}<br>
        <b>Cause:</b> {r['cause']}<br>
        <b>Est. Clearance:</b> {r['estimated_clearance']}
        """

        Marker(
            location=coords,
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{r['location']} ({r['status']})",
            icon=Icon(color=color, icon=icon_type),
        ).add_to(m)

    st_folium(m, width="100%", height=500)

# --- TAB 3: INPUT PORTAL ---
with tab3:
    st.subheader("Submit Road Report / Simulate SMS Gateway")
    st.markdown(
        "Simulate an incoming SMS or transcribed voice note from a driver or Rescue 1122 personnel."
    )

    preset = st.selectbox(
        "Choose a Quick Test Scenario (for demo convenience):",
        [
            "Custom Input",
            "Lowari Tunnel snow blockage report",
            "Kuragh road opened for one-way traffic",
            "Shandur pass clear report",
        ],
    )

    default_text = ""
    if preset == "Lowari Tunnel snow blockage report":
        default_text = "Heavy snow near Lowari Tunnel north portal. Multiple vehicles stranded and pass is completely BLOCKED. Clearance expected in 4 hours."
    elif preset == "Kuragh road opened for one-way traffic":
        default_text = "کورغ کے مقام پر ملبہ ہٹا دیا گیا ہے، سڑک اب ایک طرفہ ٹریفک کے لیے کھلی ہے۔"
    elif preset == "Shandur pass clear report":
        default_text = "Shandur top weather is clear and road is fully open for all light vehicles."

    user_input = st.text_area(
        "Raw Report Text / SMS Payload:",
        value=default_text,
        placeholder="Type or paste report here...",
        height=100,
    )

    if st.button("🚀 Process Report via Gemini AI"):
        if user_input.strip():
            with st.spinner("AI analyzing report & saving to database..."):
                parsed_result = process_report_with_ai(user_input)
                if parsed_result:
                    db.add_report(
                        parsed_result, reporter_phone="+923001112233"
                    )
                    st.success("✅ AI Structured and Saved Report to SQLite Database!")
                    st.json(parsed_result)
                    st.rerun()
        else:
            st.warning("Please enter a report or select a scenario first.")