import plotly.graph_objects as go
import streamlit as st

from lib import data, maps, ui

ui.page("Results explorer", "Validated concentrations over the monitoring rounds. Rejected (R) results are excluded.")

maps.embed("results", height=700)

ts = data.table("result_timeseries")
f1, f2, f3 = st.columns([1, 2, 1])
locations = sorted(ts.location_code.unique())
location = f1.selectbox("Location", locations, index=locations.index("MW03") if "MW03" in locations else 0)
at_loc = ts[ts.location_code == location]
analytes = sorted(at_loc.chemical_name.unique())
default = analytes.index("Benzene") if "Benzene" in analytes else 0
analyte = f2.selectbox("Analyte", analytes, index=default)
log_y = f3.toggle("Log scale")

sel = at_loc[at_loc.chemical_name == analyte].sort_values("sample_datetime")
unit = sel.unit.iloc[0]
fig = go.Figure()
fig.add_scatter(x=sel.sample_datetime, y=sel.plot_value, mode="lines", line=dict(color="#c3c2b7", width=2),
                hoverinfo="skip", showlegend=False)
styles = {"Detect": dict(color=ui.SERIES[0], symbol="circle"),
          "Qualified": dict(color=ui.SERIES[1], symbol="diamond"),
          "Non-detect": dict(color=ui.SERIES[0], symbol="circle-open")}
names = {"Detect": "Detected", "Qualified": "Detected, qualified", "Non-detect": "Not detected (plotted at RL)"}
for cls, style in styles.items():
    sub = sel[sel.point_class == cls]
    if sub.empty:
        continue
    fig.add_scatter(x=sub.sample_datetime, y=sub.plot_value, mode="markers", name=names[cls],
                    marker=dict(size=11, line=dict(width=2, color=style["color"]), **style),
                    customdata=sub[["sys_sample_code", "validator_qualifier"]].fillna("").values,
                    hovertemplate="%{x|%d %b %Y}<br>%{y} " + unit + " %{customdata[1]}<br>%{customdata[0]}"
                                  "<extra></extra>")
crit = sel.criterion_value.dropna()
if len(crit):
    fig.add_hline(y=crit.iloc[0], line_dash="dash", line_color=ui.STATUS["critical"],
                  annotation_text=f"{sel.criterion_set.iloc[0]} criterion {crit.iloc[0]:g} {unit} (illustrative)",
                  annotation_position="top left")
fig.update_layout(height=430, yaxis_title=f"{analyte} ({unit})", yaxis_type="log" if log_y else "linear",
                  margin=dict(t=30, b=10), legend=dict(orientation="h", y=1.12), hovermode="closest",
                  xaxis=dict(tickformat="%d %b %Y", tickvals=sorted(sel.sample_datetime.dt.normalize().unique())))
st.plotly_chart(fig)
st.caption("Hollow markers are non-detects drawn at the reporting limit. Diamonds carry a validator qualifier "
           "(shown on hover).")

with st.expander("Data table"):
    st.dataframe(sel[["sample_datetime", "sys_sample_code", "sample_type", "result_value", "detect_flag", "rl",
                      "unit", "validator_qualifier", "criterion_value"]], hide_index=True)
