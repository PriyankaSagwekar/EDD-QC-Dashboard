import numpy as np
import plotly.graph_objects as go
import streamlit as st

from lib import data, maps, ui

ui.page("Screening",
        "Validated, usable results for primary field samples compared with illustrative UK criteria. "
        "A non-detect whose reporting limit is above the criterion cannot show compliance (inconclusive).")

st.subheader("Worst exceedance by location")
st.caption("Against the primary set for each matrix: drinking water standard (groundwater) and "
           "residential GAC (soil).")
loc = data.table("screening_location")
if not maps.embed("screening"):
    loc["ratio_txt"] = loc.max_ratio.map(lambda v: "" if np.isnan(v) else f"{v:.2g}x")
    st.plotly_chart(ui.site_map(
        loc, "ratio_band", ui.BAND, {}, ui.BAND_ORDER,
        {"worst_analyte": "Worst analyte", "ratio_txt": "Result / criterion",
         "n_analytes_exceeding": "Analytes exceeding", "n_analytes_inconclusive": "Inconclusive analytes"}))

summary = data.table("screening_summary")
sets = data.query("SELECT criterion_set, ANY_VALUE(matrix) AS matrix, MAX(is_primary) AS is_primary "
                  "FROM screening_summary GROUP BY 1 ORDER BY 1")
label = {r.criterion_set: f"{r.criterion_set} ({'soil' if r.matrix == 'SO' else 'groundwater'})"
         for r in sets.itertuples()}
crit_set = st.radio("Criteria set", sets.criterion_set, format_func=label.get, horizontal=True)
s = summary[summary.criterion_set == crit_set]

st.subheader("Location × analyte: highest result as a multiple of the criterion")
grid = s.pivot_table(index="location_code", columns="chemical_name", values="max_ratio", aggfunc="max")
grid = grid.loc[:, grid.notna().any()]
if grid.empty:
    st.info("No detected results for this criteria set.")
else:
    # log10(ratio), fixed at 0.01x-100x so the scale means the same thing for every set
    z = np.clip(np.log10(grid.values.astype(float)), -2, 2)
    text = np.where(np.isnan(grid.values), "", np.vectorize(lambda v: f"{v:.2g}")(np.nan_to_num(grid.values)))
    fig = go.Figure(go.Heatmap(
        z=z, x=grid.columns, y=grid.index, zmin=-2, zmax=2, xgap=2, ygap=2,
        colorscale=[[0, "#9ec5f4"], [0.5, "#f0efec"], [0.75, "#ec835a"], [1, "#d03b3b"]],
        text=text, texttemplate="%{text}", customdata=grid.values,
        colorbar=dict(title="result ÷ criterion", tickvals=[-2, -1, 0, 1, 2],
                      ticktext=["0.01", "0.1", "1", "10", "100"]),
        hovertemplate="%{y} · %{x}<br>%{customdata:.3g} × criterion<extra></extra>"))
    fig.update_layout(height=120 + 32 * len(grid), margin=dict(t=10, b=10), xaxis_tickangle=-40)
    st.plotly_chart(fig)
    st.caption("Red cells exceed the criterion (above 1), blue are below. Blank cells: analyte not detected.")

st.subheader("Exceedances")
exc = data.query("SELECT location_code, sys_sample_code, sample_datetime, chemical_name, result_value, unit, "
                 "criterion_value, exceedance_ratio, validator_qualifier FROM screening_exceedance "
                 "WHERE criterion_set = ? AND screening_class = 'Exceeds' "
                 "ORDER BY exceedance_ratio DESC", (crit_set,))
st.dataframe(exc, hide_index=True,
             column_config={"exceedance_ratio": st.column_config.NumberColumn("× criterion", format="%.2f")})
inc = s[s.n_inconclusive > 0][["location_code", "chemical_name", "n_inconclusive", "criterion_value", "unit"]]
if len(inc):
    st.subheader("Inconclusive non-detects")
    st.dataframe(inc, hide_index=True)
