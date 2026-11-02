import plotly.express as px
import streamlit as st

from lib import data, ui

ui.page("Batch detail", "The import decision for one EDD, as written on its Excel exception report.")

b = data.table("batch_summary").sort_values("batch_id")
choice = st.selectbox("EDD file", b.file_name)
r = b[b.file_name == choice].iloc[0]
verdict, advice = data.decision(r.row_count, r.rows_held, r.rows_qualified, data.max_held_fraction())
show = {"NO-GO": st.error, "PARTIAL": st.warning}.get(verdict, st.success)
show(f"**{verdict}**: {advice}")

c = st.columns(5)
c[0].metric("Rows in EDD", int(r.row_count))
c[1].metric("Passed", int(r.rows_passed))
c[2].metric("Qualified", int(r.rows_qualified))
c[3].metric("Held", int(r.rows_held))
c[4].metric("Promoted", int(r.rows_promoted))
st.caption(f"Status {r.status}. Exceptions: {int(r.n_critical)} critical, {int(r.n_warning)} warning, "
           f"{int(r.n_info)} info.")

q = data.query("SELECT validator_qualifier, SUM(n_results) AS n FROM qualifier_summary "
               "WHERE batch_id = ? AND validator_qualifier <> 'None' GROUP BY 1 ORDER BY n DESC",
               (int(r.batch_id),))
left, right = st.columns([1, 2])
with left:
    st.subheader("Qualifiers applied")
    if q.empty:
        st.info("No promoted results were qualified." if r.rows_promoted else "Nothing was promoted.")
    else:
        fig = px.bar(q, x="n", y="validator_qualifier", orientation="h", text="n",
                     labels={"n": "Results", "validator_qualifier": "Qualifier"},
                     color_discrete_sequence=[ui.SERIES[0]])
        fig.update_layout(height=60 + 40 * len(q), margin=dict(t=10, b=10), yaxis_type="category")
        fig.update_traces(hovertemplate="%{y}: %{x} results<extra></extra>")
        st.plotly_chart(fig)
with right:
    st.subheader("Rows held in staging")
    held = data.query("SELECT source_row_no, sys_sample_code, location_code, sample_type, chemical_name, "
                      "result_value, unit, rules, messages FROM held_rows WHERE batch_id = ? "
                      "ORDER BY source_row_no", (int(r.batch_id),))
    if held.empty:
        st.info("No rows were held.")
    else:
        st.dataframe(held, hide_index=True, column_config={"source_row_no": "EDD row"})
