
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st


st.set_page_config(
    page_title="EcoLoop | AI Energy Optimization Dashboard",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

COMPARISON_PATH = Path(__file__).resolve().parent.parent / "results" / "comparison.json"

PRIMARY_GREEN = "#0F9D58"
DEEP_GREEN = "#0B6E4F"
ACCENT_BLUE = "#1A73E8"
DEEP_BLUE = "#0B4F9E"
BG_DARK = "#0E1B18"
CARD_BG = "#132A24"
CARD_BORDER = "rgba(15, 157, 88, 0.25)"
TEXT_MUTED = "#9FB8AF"
SUCCESS = "#22C55E"
WARNING = "#F59E0B"
ERROR = "#EF4444"

CUSTOM_CSS = f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Inter', sans-serif;
    }}

    .stApp {{
        background: radial-gradient(circle at top left, #10231e 0%, {BG_DARK} 55%, #081412 100%);
        color: #EAF6F1;
    }}

    #MainMenu, footer, header {{visibility: hidden;}}

    .hero {{
        padding: 1.6rem 2rem;
        border-radius: 20px;
        background: linear-gradient(120deg, rgba(15,157,88,0.18), rgba(26,115,232,0.12));
        border: 1px solid {CARD_BORDER};
        margin-bottom: 1.6rem;
        box-shadow: 0 8px 32px rgba(0,0,0,0.35);
    }}

    .hero h1 {{
        font-size: 2.1rem;
        font-weight: 800;
        margin: 0;
        background: linear-gradient(90deg, {PRIMARY_GREEN}, {ACCENT_BLUE});
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }}

    .hero p {{
        color: {TEXT_MUTED};
        margin-top: 0.35rem;
        font-size: 0.98rem;
    }}

    .badge {{
        display: inline-block;
        padding: 0.28rem 0.85rem;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 700;
        margin-right: 0.5rem;
        letter-spacing: 0.02em;
    }}
    .badge-success {{ background: rgba(34,197,94,0.16); color: {SUCCESS}; border: 1px solid rgba(34,197,94,0.4); }}
    .badge-warning {{ background: rgba(245,158,11,0.16); color: {WARNING}; border: 1px solid rgba(245,158,11,0.4); }}
    .badge-error {{ background: rgba(239,68,68,0.16); color: {ERROR}; border: 1px solid rgba(239,68,68,0.4); }}
    .badge-info {{ background: rgba(26,115,232,0.16); color: {ACCENT_BLUE}; border: 1px solid rgba(26,115,232,0.4); }}

    .kpi-card {{
        background: linear-gradient(160deg, {CARD_BG}, #0d211c);
        border: 1px solid {CARD_BORDER};
        border-radius: 18px;
        padding: 1.15rem 1.3rem;
        height: 100%;
        box-shadow: 0 6px 22px rgba(0,0,0,0.28);
        transition: transform 0.15s ease;
    }}
    .kpi-card:hover {{ transform: translateY(-3px); }}

    .kpi-label {{
        color: {TEXT_MUTED};
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 0.3rem;
    }}

    .kpi-value {{
        font-size: 1.9rem;
        font-weight: 800;
        color: #FFFFFF;
        line-height: 1.1;
    }}

    .kpi-sub {{
        font-size: 0.82rem;
        margin-top: 0.35rem;
        font-weight: 600;
    }}

    .section-title {{
        font-size: 1.15rem;
        font-weight: 700;
        color: #EAF6F1;
        margin: 1.6rem 0 0.7rem 0;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }}

    .panel {{
        background: linear-gradient(160deg, {CARD_BG}, #0d211c);
        border: 1px solid {CARD_BORDER};
        border-radius: 18px;
        padding: 1.2rem 1.4rem;
        box-shadow: 0 6px 22px rgba(0,0,0,0.28);
    }}

    .rec-panel {{
        background: linear-gradient(120deg, rgba(15,157,88,0.14), rgba(26,115,232,0.10));
        border: 1px solid rgba(15,157,88,0.35);
        border-radius: 16px;
        padding: 1rem 1.3rem;
    }}

    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, #0B1D18, #081412);
        border-right: 1px solid {CARD_BORDER};
    }}

    .sidebar-stat {{
        background: rgba(255,255,255,0.03);
        border: 1px solid {CARD_BORDER};
        border-radius: 12px;
        padding: 0.7rem 0.9rem;
        margin-bottom: 0.6rem;
    }}
    .sidebar-stat-label {{ color: {TEXT_MUTED}; font-size: 0.75rem; text-transform: uppercase; }}
    .sidebar-stat-value {{ color: #FFFFFF; font-size: 1.15rem; font-weight: 700; }}

    hr {{ border-color: {CARD_BORDER}; }}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def load_comparison(path: Path):
    if not path.exists():
        return None, f"comparison.json not found at `{path}`. Run the simulation pipeline first."
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        return None, f"Failed to read comparison.json: {exc}"
    if not isinstance(data, dict):
        return None, "comparison.json is malformed (expected a JSON object)."
    return data, None


def safe_get(d: dict, *keys, default=None):
    
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur if cur is not None else default


def fmt_num(value, decimals=2, suffix=""):
    if value is None:
        return "N/A"
    try:
        return f"{float(value):,.{decimals}f}{suffix}"
    except (TypeError, ValueError):
        return "N/A"


data, load_error = load_comparison(COMPARISON_PATH)


st.markdown(
    """
    <div class="hero">
        <h1>🌿 EcoLoop — AI Energy Optimization Dashboard</h1>
        <p>Closed-loop building simulation • Baseline vs. AI-Optimized performance comparison</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if load_error:
    st.markdown(
        f'<span class="badge badge-error">⚠ DATA UNAVAILABLE</span>'
        f'<span class="badge badge-info"> Last Updated:{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</span>',
        unsafe_allow_html=True,
    )
    st.error(load_error)
    st.info("Once `results/comparison.json` is generated by the simulation pipeline, this dashboard will populate automatically.")
    st.stop()


baseline_energy = safe_get(data, "baseline", "total_energy_kwh")
optimized_energy = safe_get(data, "optimized", "total_energy_kwh")
baseline_hvac = safe_get(data, "baseline", "hvac_energy_kwh")
optimized_hvac = safe_get(data, "optimized", "hvac_energy_kwh")
baseline_temp = safe_get(data, "baseline", "average_temperature")
optimized_temp = safe_get(data, "optimized", "average_temperature")
baseline_pmv = safe_get(data, "baseline", "average_pmv")
optimized_pmv = safe_get(data, "optimized", "average_pmv")

energy_saved_pct = safe_get(data, "savings", "energy_saved_percent")
hvac_saved_pct = safe_get(data, "savings", "hvac_saved_percent")
comfort_change = safe_get(data, "savings", "comfort_change")

runtime_seconds = safe_get(data, "optimized", "duration_seconds", default=safe_get(data, "duration_seconds"))
timestamp = safe_get(data, "timestamp", default=safe_get(data, "optimized", "timestamp"))
sim_status = safe_get(data, "status", default="Completed" if optimized_energy is not None else "Unknown")

energy_saved_kwh = None
if baseline_energy is not None and optimized_energy is not None:
    try:
        energy_saved_kwh = float(baseline_energy) - float(optimized_energy)
    except (TypeError, ValueError):
        energy_saved_kwh = None

comfort_ok = None
if optimized_temp is not None:
    try:
        comfort_ok = 22.0 <= float(optimized_temp) <= 25.0
    except (TypeError, ValueError):
        comfort_ok = None

has_core_data = baseline_energy is not None and optimized_energy is not None


status_badge = '<span class="badge badge-success"> SIMULATION COMPLETE</span>' if has_core_data \
    else '<span class="badge badge-warning">⚠ PARTIAL DATA</span>'
health_badge = '<span class="badge badge-success"> SYSTEM HEALTHY</span>' if has_core_data \
    else '<span class="badge badge-warning"> CHECK PIPELINE</span>'
ts_display = timestamp if timestamp else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
ts_badge = f'<span class="badge badge-info"> Last Updated:{ts_display}</span>'

st.markdown(f"{status_badge}{health_badge}{ts_badge}", unsafe_allow_html=True)


with st.sidebar:
    st.markdown("### 🌿 EcoLoop")
    st.markdown(
        "AI-driven closed-loop control system that optimizes HVAC and "
        "lighting setpoints against an EnergyPlus baseline simulation, "
        "cutting energy use while preserving occupant comfort."
    )
    st.markdown("---")
    st.markdown("#### Quick Statistics")

    st.markdown(
        f"""
        <div class="sidebar-stat">
            <div class="sidebar-stat-label">Energy Saved</div>
            <div class="sidebar-stat-value">{fmt_num(energy_saved_pct, 1, "%")}</div>
        </div>
        <div class="sidebar-stat">
            <div class="sidebar-stat-label">HVAC Energy Saved</div>
            <div class="sidebar-stat-value">{fmt_num(hvac_saved_pct, 1, "%")}</div>
        </div>
        <div class="sidebar-stat">
            <div class="sidebar-stat-label">Comfort (PMV) Change</div>
            <div class="sidebar-stat-value">{fmt_num(comfort_change, 2)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown("#### ℹ️ About")
    st.caption(
        "Data source: `results/comparison.json`\n\n"
        "This dashboard reads simulation output only — no synthetic "
        "or placeholder values are displayed."
    )
    st.markdown("---")
    st.caption("Built for sustainable, AI-optimized building operations. 💚")

st.markdown('<div class="section-title"> Key Performance Indicators</div>', unsafe_allow_html=True)

kpi_cols = st.columns(6)

kpi_defs = [
    (" Baseline Energy", fmt_num(baseline_energy, 1, " kWh"), None, TEXT_MUTED),
    (" Optimized Energy", fmt_num(optimized_energy, 1, " kWh"), None, PRIMARY_GREEN),
    (" Energy Saved (kWh)", fmt_num(energy_saved_kwh, 1, " kWh"),
     ("▲" if (energy_saved_kwh or 0) > 0 else "▼") if energy_saved_kwh is not None else None,
     SUCCESS if (energy_saved_kwh or 0) > 0 else ERROR),
    (" Energy Saved (%)", fmt_num(energy_saved_pct, 1, "%"), None,
     SUCCESS if (energy_saved_pct or 0) > 0 else ERROR),
    ("⏱ Runtime", fmt_num(runtime_seconds, 2, " s") if runtime_seconds is not None else "N/A", None, ACCENT_BLUE),
    ("🌡 Comfort Status",
     "Maintained" if comfort_ok else ("Out of Range" if comfort_ok is False else "N/A"),
     None, SUCCESS if comfort_ok else (ERROR if comfort_ok is False else TEXT_MUTED)),
]

for col, (label, value, arrow, color) in zip(kpi_cols, kpi_defs):
    with col:
        arrow_html = f'<div class="kpi-sub" style="color:{color};">{arrow}</div>' if arrow else ""
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">{label}</div>
                <div class="kpi-value" style="color:{color if color != TEXT_MUTED else '#FFFFFF'};">{value}</div>
                {arrow_html}
            </div>
            """,
            unsafe_allow_html=True,
        )


st.markdown('<div class="section-title"> Energy Performance</div>', unsafe_allow_html=True)
chart_col1, chart_col2 = st.columns([1.3, 1])

with chart_col1:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    if baseline_energy is not None and optimized_energy is not None:
        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            x=["Total Energy", "HVAC Energy"],
            y=[baseline_energy, baseline_hvac if baseline_hvac is not None else 0],
            name="Baseline",
            marker_color=DEEP_BLUE,
            text=[fmt_num(baseline_energy, 1), fmt_num(baseline_hvac, 1)],
            textposition="outside",
        ))
        fig_bar.add_trace(go.Bar(
            x=["Total Energy", "HVAC Energy"],
            y=[optimized_energy, optimized_hvac if optimized_hvac is not None else 0],
            name="Optimized",
            marker_color=PRIMARY_GREEN,
            text=[fmt_num(optimized_energy, 1), fmt_num(optimized_hvac, 1)],
            textposition="outside",
        ))
        fig_bar.update_layout(
            barmode="group",
            title="Baseline vs. Optimized Energy Consumption (kWh)",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#EAF6F1"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(t=60, b=30, l=10, r=10),
            height=380,
        )
        fig_bar.update_yaxes(gridcolor="rgba(255,255,255,0.08)")
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.warning("Energy comparison data unavailable in comparison.json.")
    st.markdown("</div>", unsafe_allow_html=True)

with chart_col2:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    if energy_saved_pct is not None:
        remaining_pct = max(0.0, 100.0 - float(energy_saved_pct))
        fig_donut = go.Figure(data=[go.Pie(
            labels=["Energy Saved", "Remaining Consumption"],
            values=[max(0.0, float(energy_saved_pct)), remaining_pct],
            hole=0.65,
            marker=dict(colors=[PRIMARY_GREEN, "#1E3A34"]),
            textinfo="label+percent",
            sort=False,
        )])
        fig_donut.update_layout(
            title="Energy Savings Share",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#EAF6F1"),
            showlegend=False,
            margin=dict(t=60, b=10, l=10, r=10),
            height=380,
            annotations=[dict(
                text=f"{fmt_num(energy_saved_pct, 1)}%",
                x=0.5, y=0.5, font_size=28, showarrow=False, font_color=PRIMARY_GREEN,
            )],
        )
        st.plotly_chart(fig_donut, use_container_width=True)
    else:
        st.warning("Savings percentage unavailable in comparison.json.")
    st.markdown("</div>", unsafe_allow_html=True)


st.markdown('<div class="section-title">🌡 Comfort & Environmental Indicators</div>', unsafe_allow_html=True)
gauge_col1, gauge_col2 = st.columns(2)

with gauge_col1:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    if optimized_temp is not None:
        fig_temp = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=float(optimized_temp),
            delta={"reference": float(baseline_temp) if baseline_temp is not None else float(optimized_temp),
                   "increasing": {"color": ERROR}, "decreasing": {"color": SUCCESS}},
            title={"text": "Optimized Avg. Zone Temperature (°C)", "font": {"color": "#EAF6F1", "size": 15}},
            number={"suffix": " °C", "font": {"color": "#FFFFFF"}},
            gauge={
                "axis": {"range": [15, 32], "tickcolor": "#EAF6F1"},
                "bar": {"color": PRIMARY_GREEN},
                "bgcolor": "rgba(0,0,0,0)",
                "steps": [
                    {"range": [15, 22], "color": "rgba(245,158,11,0.35)"},
                    {"range": [22, 25], "color": "rgba(34,197,94,0.35)"},
                    {"range": [25, 32], "color": "rgba(239,68,68,0.35)"},
                ],
                "threshold": {"line": {"color": "#FFFFFF", "width": 3}, "value": float(optimized_temp)},
            },
        ))
        fig_temp.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#EAF6F1"),
            margin=dict(t=50, b=10, l=30, r=30), height=320,
        )
        st.plotly_chart(fig_temp, use_container_width=True)
    else:
        st.warning("Temperature data unavailable in comparison.json.")
    st.markdown("</div>", unsafe_allow_html=True)

with gauge_col2:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    if optimized_pmv is not None:
        fig_pmv = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=float(optimized_pmv),
            delta={"reference": float(baseline_pmv) if baseline_pmv is not None else float(optimized_pmv),
                   "increasing": {"color": ERROR}, "decreasing": {"color": SUCCESS}},
            title={"text": "Optimized Avg. PMV Comfort Index", "font": {"color": "#EAF6F1", "size": 15}},
            number={"font": {"color": "#FFFFFF"}},
            gauge={
                "axis": {"range": [-3, 3], "tickcolor": "#EAF6F1"},
                "bar": {"color": ACCENT_BLUE},
                "bgcolor": "rgba(0,0,0,0)",
                "steps": [
                    {"range": [-3, -1], "color": "rgba(239,68,68,0.35)"},
                    {"range": [-1, 1], "color": "rgba(34,197,94,0.35)"},
                    {"range": [1, 3], "color": "rgba(239,68,68,0.35)"},
                ],
                "threshold": {"line": {"color": "#FFFFFF", "width": 3}, "value": float(optimized_pmv)},
            },
        ))
        fig_pmv.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#EAF6F1"),
            margin=dict(t=50, b=10, l=30, r=30), height=320,
        )
        st.plotly_chart(fig_pmv, use_container_width=True)
    else:
        st.warning("PMV data unavailable in comparison.json.")
    st.markdown("</div>", unsafe_allow_html=True)


st.markdown('<div class="section-title"> AI Recommendations</div>', unsafe_allow_html=True)

recommendations = safe_get(data, "recommendations", default=safe_get(data, "ai_recommendations"))

with st.expander(" View AI-Generated Insights", expanded=True):
    st.markdown('<div class="rec-panel">', unsafe_allow_html=True)
    if recommendations:
        if isinstance(recommendations, list):
            for rec in recommendations:
                st.markdown(f"- {rec}")
        else:
            st.markdown(str(recommendations))
    else:
        insights = []
        if energy_saved_pct is not None:
            if energy_saved_pct > 0:
                insights.append(
                    f" The AI-optimized control loop reduced total energy consumption by "
                    f"**{fmt_num(energy_saved_pct, 1)}%** compared to the baseline simulation."
                )
            else:
                insights.append(
                    " Optimized run did not achieve energy savings over baseline — "
                    "review control policy and rule thresholds."
                )
        if hvac_saved_pct is not None:
            insights.append(f"HVAC-specific energy usage changed by **{fmt_num(hvac_saved_pct, 1)}%**.")
        if comfort_ok is True:
            insights.append(" Occupant thermal comfort was **maintained** within the 22–25°C target band.")
        elif comfort_ok is False:
            insights.append(" Optimized average temperature fell **outside** the comfort band — consider retuning setpoints.")
        if comfort_change is not None:
            insights.append(f" Comfort (PMV) shifted by **{fmt_num(comfort_change, 2)}** relative to baseline.")

        if insights:
            for line in insights:
                st.markdown(line)
        else:
            st.info("No recommendation data available in comparison.json.")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")
st.caption(
    f"EcoLoop Dashboard • Data source: `results/comparison.json` • "
    f"Rendered {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)