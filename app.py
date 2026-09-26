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
# 1. Page Configuration & External CSS Injection
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Chitral RouteGuard",
    page_icon="🏔️",
    layout="wide",
)

# Helper function to load external CSS
def load_css(file_name: str):
    if os.path.exists(file_name):
        with open(file_name, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css("style.css")

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
        st.error("Gemini API key missing. Please set GEMINI_API_KEY in your environment!")
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
# 3. Dashboard UI & Layout
# ---------------------------------------------------------------------------

# Hero Header Banner
st.markdown(
    """
    <div class="hero-header">
        <h1 class="hero-title">🏔️ Chitral RouteGuard</h1>
        <p class="hero-subtitle">Low-Bandwidth AI Road & Landslide Advisory System | Emergency Portal</p>
    </div>
    """,
    unsafe_allow_html=True,
)

reports = db.get_all_reports()

# Sidebar Overview
st.sidebar.markdown("### 📍 Corridor Overview")
total_routes = len(reports)
blocked_routes = sum(1 for r in reports if r["status"] == "BLOCKED")
hazard_routes = sum(1 for r in reports if r["status"] in ["ONE_WAY", "HAZARD"])
clear_routes = sum(1 for r in reports if r["status"] == "CLEAR")

st.sidebar.metric("Monitored Reports", total_routes)
st.sidebar.metric("🔴 Blocked Routes", blocked_routes)
st.sidebar.metric("🟡 Partial Hazards", hazard_routes)
st.sidebar.metric("🟢 Clear Corridors", clear_routes)

st.sidebar.divider()
st.sidebar.caption("System Status: **Active (2G Optimized)**")

# Navigation Tabs
tab1, tab2, tab3 = st.tabs([
    "📢 Public Road Status (2G View)",
    "🗺️ Interactive Corridor Map",
    "📱 Dispatch / Driver Input Portal",
])

# --- TAB 1: PUBLIC VIEW ---
with tab1:
    st.subheader("Live Pass & Route Advisories")
    st.info("💡 Light-weight mode enabled for 2G / weak mobile connections.")

    if not reports:
        st.warning("No road advisories currently recorded.")

    for r in reports:
        status = r["status"]
        card_class = (
            "advisory-card-blocked"
            if status == "BLOCKED"
            else (
                "advisory-card-hazard"
                if status in ["ONE_WAY", "HAZARD"]
                else "advisory-card-clear"
            )
        )
        badge_class = (
            "badge-blocked"
            if status == "BLOCKED"
            else (
                "badge-hazard"
                if status in ["ONE_WAY", "HAZARD"]
                else "badge-clear"
            )
        )
        status_icon = "🔴" if status == "BLOCKED" else ("🟡" if status in ["ONE_WAY", "HAZARD"] else "🟢")

        # Clean HTML Structure referencing style.css
        st.markdown(
            f"""
            <div class="{card_class}">
                <div class="card-header">
                    <h3 class="card-title">{status_icon} {r['location']}</h3>
                    <span class="badge-status {badge_class}">{status}</span>
                </div>
                <div class="card-urdu"><b>Urdu Summary:</b> {r['summary_urdu']}</div>
                <div class="card-meta">
                    <div><b>Cause:</b> {r['cause']}</div>
                    <div><b>Severity:</b> {r['severity']}</div>
                    <div><b>Est. Clearance:</b> {r['estimated_clearance']}</div>
                    <div><b>Reported At:</b> {r['timestamp']}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# --- TAB 2: INTERACTIVE MAP ---
with tab2:
    st.subheader("Chitral Emergency Route Map")
    st.caption("Filter active incidents and inspect corridor map pins.")

    st.markdown('<div class="control-card">', unsafe_allow_html=True)
    col_f1, col_f2 = st.columns([3, 1])
    with col_f1:
        selected_statuses = st.multiselect(
            "Filter Map by Status:",
            options=["BLOCKED", "ONE_WAY", "HAZARD", "CLEAR"],
            default=["BLOCKED", "ONE_WAY", "HAZARD", "CLEAR"],
        )

    filtered_reports = [r for r in reports if r["status"] in selected_statuses]

    with col_f2:
        st.metric("Visible Pins", len(filtered_reports))
    st.markdown('</div>', unsafe_allow_html=True)

    m = folium.Map(location=[35.8510, 71.7869], zoom_start=8)

    for r in filtered_reports:
        coords = db.get_coords_for_location(r["location"])
        icon = get_marker_icon(r["status"], r["cause"])

        popup_html = f"""
        <div style="font-family: sans-serif; width: 200px;">
            <h4 style="margin-bottom: 5px; color: #0F172A;">{r['location']}</h4>
            <b>Status:</b> {r['status']}<br>
            <b>Cause:</b> {r['cause']}<br>
            <b>Clearance:</b> {r['estimated_clearance']}<br>
            <hr style="margin: 8px 0;">
            <small style="color: #334155;">{r['summary_urdu']}</small>
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
    st.caption("Simulate crowd-sourced text reports from drivers, police checkposts, or Rescue 1122.")

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
        height=120,
    )

    if st.button("🚀 Process Report via Gemini AI", type="primary"):
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