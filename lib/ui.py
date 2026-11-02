"""Shared page furniture, colours and chart helpers."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import data

# Status palette: always shown with a text label, never colour alone.
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b",
          "none": "#898781"}
RAG = {"GREEN": STATUS["good"], "AMBER": STATUS["warning"], "RED": STATUS["critical"], "GREY": STATUS["none"]}
RAG_LABEL = {"GREEN": "All results passed", "AMBER": "Some results qualified",
             "RED": "Some results held", "GREY": "No data"}
SEVERITY = {"CRITICAL": STATUS["critical"], "WARNING": STATUS["warning"], "INFO": "#2a78d6"}
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]           # categorical slots 1-3
MUTED_INK = "#52514e"
BAND = {">10x": STATUS["critical"], "1-10x": STATUS["serious"], "Inconclusive": STATUS["none"],
        "Below criterion": STATUS["good"], "No data": "#c3c2b7"}
BAND_ORDER = [">10x", "1-10x", "Inconclusive", "Below criterion", "No data"]


def page(title: str, intro: str = "") -> None:
    """Title, fictional-data banner and data freshness. Stops the page if the snapshot is unusable."""
    st.title(title)
    m = data.manifest()
    st.caption(f"Fictional site and simulated laboratory data; screening criteria are illustrative. "
               f"Data as of {m.get('generated_utc', 'unknown')}"
               + (f", pipeline commit {m['pipeline_commit']}." if m.get("pipeline_commit") else "."))
    issues = data.problems()
    if issues:
        for msg in issues:
            st.error(msg)
        st.stop()
    if warn := data.schema_warning():
        st.warning(warn)
    if intro:
        st.markdown(intro)


def site_map(df: pd.DataFrame, colour_col: str, colours: dict, labels: dict, order: list,
             hover: dict, height: int = 520) -> go.Figure:
    """Point map in WGS84 (lat/lon added by the refresh script from British National Grid)."""
    fig = go.Figure()
    for key in order:
        sub = df[df[colour_col] == key]
        if sub.empty:
            continue
        fig.add_trace(go.Scattermap(
            lat=sub.lat, lon=sub.lon, mode="markers+text", name=labels.get(key, key),
            marker=dict(size=14, color=colours[key]), text=sub.location_code, textposition="top right",
            customdata=sub[list(hover)].values,
            hovertemplate="<b>%{text}</b><br>" + "<br>".join(
                f"{label}: %{{customdata[{i}]}}" for i, label in enumerate(hover.values())) + "<extra></extra>"))
    fig.update_layout(map=dict(style="carto-positron", center=dict(lat=df.lat.mean(), lon=df.lon.mean()), zoom=15.3),
                      height=height, margin=dict(l=0, r=0, t=0, b=0),
                      legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0))
    return fig
