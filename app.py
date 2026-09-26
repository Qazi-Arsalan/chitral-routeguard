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
        description="Specific road, pass, or village mentioned (e.g., Kuragh, Lowari Tunnel, Drosh, Booni, Shandur)."
    )
    status: str = Field(
        description="Road status. MUST be one of: 'BLOCKED', 'ONE_WAY', 'HAZARD', or 'CLEAR'."
    )
    cause: str = Field(
        description="Reason for hazard (e.g., Landslide, Rockfall, Avalanche, Snow, Flooding, Clear)."
    )
    severity: str = Field(
        description="Severity level. MUST be one of: 'HIGH', 'MEDIUM', 'LOW'."
    )
    estimated_clearance: str = Field(
        description="Estimated time to clear, or 'Unknown' if not mentioned."
    )
    summary_urdu: str = Field(
        description="A concise 1-sentence summary written in plain Urdu for SMS broadcasts."
    )


def process_report_with_ai(raw_text: str) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY", "")

    if not api_key:
        st.error(
            "Gemini API key missing. Please set GEMINI_API_KEY in your environment!"
        )
        return None

    client = genai.Client(api_key=api_key)
    prompt = f"""
    You are an emergency traffic and hazard coordination AI for Chitral, Pakistan.
    Analyze the following crowd-sourced report from a driver, traveler, or checkpost guard.
    Extract the route information accurately into the structured format.

    Report Input: "{raw_text}"
    """

    models_to_try = [
        "gemini-2.5-flash",
        "gemini-1.5-flash",
        "gemini-3.8-flash",
    ]

    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=RoadReport,
                    temperature=0.1,
                ),
            )
            data = json.loads(response.text)
            return data
        except Exception:
            continue

    st.error("AI service temporarily unavailable. Please try again.")
    return None


# Helper function to select marker icon based on hazard cause
def get_marker_icon(status: str, cause: str):
    cause_clean = cause.lower()
    if status == "BLOCKED":
        color = "red"
        icon_name = "remove-sign" if "snow" in cause_clean else "exclamation-sign"
    elif status in ["ONE_WAY", "HAZARD"]:
        color = "orange"
        icon_name = "warning-sign"
    else:
        color = "green"
        icon_name = "ok-sign"

    return Icon(color=color, icon=icon_name)


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
hazard_routes = sum(1 for r in reports if r["status"] in ["ONE_WAY", "HAZARD"])
clear_routes = sum(1 for r in reports if r["status"] == "CLEAR")

st.sidebar.metric("Monitored Reports", total_routes)
st.sidebar.metric("🔴 Completely Blocked", blocked_routes)
st.sidebar.metric("🟡 Partial Hazards / One-Way", hazard_routes)
st.sidebar.metric("🟢 Clear Corridors", clear_routes)

# Dashboard Navigation Tabs
tab1, tab2, tab3 = st.tabs([
    "📢 Public Road Status (2G View)",
    "🗺️ Interactive Corridor Map",
    "📱 Dispatch / Driver Input Portal",
])

# --- TAB 1: PUBLIC VIEW ---
with tab1:
    st.subheader("Live Pass & Route Advisories")
    st.info("💡 Light-weight text mode enabled for 2G / weak cellular connections.")

    if not reports:
        st.warning("No road advisories currently recorded.")

    for r in reports:
        status_color = "🔴" if r["status"] == "BLOCKED" else ("🟡" if r["status"] in ["ONE_WAY", "HAZARD"] else "🟢")

        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.markdown(f"### {status_color} {r['location']}")
                st.markdown(f"**Urdu Summary:** {r['summary_urdu']}")
            with col2:
                st.markdown(f"**Status:** `{r['status']}`")
                st.markdown(f"**Cause:** {r['cause']}")
                st.markdown(f"**Severity:** `{r['severity']}`")
            with col3:
                st.markdown(f"**Est. Clearance:** {r['estimated_clearance']}")
                st.markdown(f"**Reported At:** {r['timestamp']}")

# --- TAB 2: INTERACTIVE MAP ---
with tab2:
    st.subheader("Chitral Emergency Route Map")
    st.caption("Filter active incidents and inspect corridor map pins.")

    # Filter Controls
    col_f1, col_f2 = st.columns([3, 1])
    with col_f1:
        selected_statuses = st.multiselect(
            "Filter Map by Status:",
            options=["BLOCKED", "ONE_WAY", "HAZARD", "CLEAR"],
            default=["BLOCKED", "ONE_WAY", "HAZARD", "CLEAR"],
        )

    filtered_reports = [r for r in reports if r["status"] in selected_statuses]

    with col_f2:
        st.write("")
        st.metric("Visible Pins", len(filtered_reports))

    # Base Folium Map
    m = folium.Map(location=[35.8510, 71.7869], zoom_start=8)

    for r in filtered_reports:
        coords = db.get_coords_for_location(r["location"])
        icon = get_marker_icon(r["status"], r["cause"])

        popup_html = f"""
        <div style="font-family: sans-serif; width: 200px;">
            <h4 style="margin-bottom: 5px;">{r['location']}</h4>
            <b>Status:</b> {r['status']}<br>
            <b>Cause:</b> {r['cause']}<br>
            <b>Clearance:</b> {r['estimated_clearance']}<br>
            <hr style="margin: 8px 0;">
            <small>{r['summary_urdu']}</small>
        </div>
        """

        Marker(
            location=coords,
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=f"{r['location']} — {r['status']}",
            icon=icon,
        ).add_to(m)

    st_folium(m, width="100%", height=520)

# --- TAB 3: INPUT PORTAL ---
with tab3:
    st.subheader("Submit Road Report / Simulate SMS Gateway")
    st.markdown("Simulate crowd-sourced text reports from drivers, police checkposts, or Rescue 1122.")

    preset = st.selectbox(
        "Choose a Quick Test Scenario:",
        [
            "Custom Input",
            "Lowari Tunnel snow blockage report",
            "Kuragh road opened for one-way traffic",
            "Shandur pass clear report",
            "Drosh flash flood hazard",
        ],
    )

    default_text = ""
    if preset == "Lowari Tunnel snow blockage report":
        default_text = "Heavy snow near Lowari Tunnel north portal. Multiple vehicles stranded and pass is completely BLOCKED. Clearance expected in 4 hours."
    elif preset == "Kuragh road opened for one-way traffic":
        default_text = "کورغ کے مقام پر ملبہ ہٹا دیا گیا ہے، سڑک اب ایک طرفہ ٹریفک کے لیے کھلی ہے۔"
    elif preset == "Shandur pass clear report":
        default_text = "Shandur top weather is clear and road is fully open for all light vehicles."
    elif preset == "Drosh flash flood hazard":
        default_text = "Flash flood near Drosh stream causing rockfall. Road single lane HAZARD. Clearance unknown."

    user_input = st.text_area(
        "Raw Report Text / SMS Payload:",
        value=default_text,
        placeholder="Type or paste report here...",
        height=100,
    )

    if st.button("🚀 Process Report via Gemini AI"):
        if user_input.strip():
            with st.spinner("AI analyzing report & updating database..."):
                parsed_result = process_report_with_ai(user_input)
                if parsed_result:
                    db.add_report(
                        parsed_result, reporter_phone="+923001112233"
                    )
                    st.success("✅ AI Structured and Saved Report to Database!")
                    st.json(parsed_result)
                    st.rerun()
        else:
            st.warning("Please enter a report or select a scenario first.")