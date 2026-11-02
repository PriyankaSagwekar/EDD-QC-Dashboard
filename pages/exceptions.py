import plotly.express as px
import streamlit as st

from lib import data, ui

ui.page("Exceptions", "Every QA/QC finding from the latest validation run of each batch.")

exc = data.table("exception_detail")
exc = exc.assign(_sev=exc.severity.map({"CRITICAL": 0, "WARNING": 1, "INFO": 2})) \
    .sort_values(["file_name", "_sev", "rule_id", "source_row_no"]).drop(columns="_sev")
f1, f2, f3 = st.columns(3)
batches = f1.multiselect("EDD file", sorted(exc.file_name.unique()))
families = f2.multiselect("Rule family", sorted(exc.family.unique()))
severities = f3.multiselect("Severity", ["CRITICAL", "WARNING", "INFO"])
sel = exc
if batches:
    sel = sel[sel.file_name.isin(batches)]
if families:
    sel = sel[sel.family.isin(families)]
if severities:
    sel = sel[sel.severity.isin(severities)]
rules = st.multiselect("Rule", sorted(sel.rule_id.unique()))
if rules:
    sel = sel[sel.rule_id.isin(rules)]

st.metric("Exceptions shown", f"{len(sel):,}")
if sel.empty:
    st.info("No exceptions match these filters.")
    st.stop()

counts = sel.groupby(["family", "severity"], as_index=False).size()
order = counts.groupby("family")["size"].sum().sort_values().index.tolist()
fig = px.bar(counts, x="size", y="family", color="severity", orientation="h",
             color_discrete_map=ui.SEVERITY, category_orders={"family": order,
                                                             "severity": ["CRITICAL", "WARNING", "INFO"]},
             labels={"size": "Exceptions", "family": ""})
fig.update_layout(height=60 + 34 * len(order), margin=dict(t=30, b=10), legend_title_text="",
                  legend=dict(orientation="h", y=1.08), bargap=0.35)
fig.update_traces(hovertemplate="%{y}<br>%{x} exceptions<extra></extra>")
st.plotly_chart(fig)

st.subheader("Exception detail")
cols = ["file_name", "severity", "rule_id", "rule_name", "source_row_no", "sys_sample_code", "location_code",
        "chemical_name", "observed_value", "limit_value", "message"]
st.dataframe(sel[cols], hide_index=True, column_config={"source_row_no": "EDD row", "file_name": "EDD file"})
st.download_button("Download as CSV", sel[cols].to_csv(index=False), "exceptions.csv", "text/csv")
