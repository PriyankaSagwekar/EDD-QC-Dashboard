import plotly.graph_objects as go
import streamlit as st

from lib import data, ui

ui.page("EDD QA/QC overview",
        "Each laboratory EDD is loaded to staging, checked against 36 QA/QC rules, and only passed or "
        "qualified rows are promoted to the master database.")

b = data.table("batch_summary").sort_values("batch_id")
limit = data.max_held_fraction()
b["decision"] = [data.decision(r.row_count, r.rows_held, r.rows_qualified, limit)[0] for r in b.itertuples()]

held_pct = b.rows_held.sum() / max(b.row_count.sum(), 1)
c1, c2, c3, c4 = st.columns(4)
c1.metric("EDD batches loaded", len(b))
c2.metric("Results promoted", f"{int(b.rows_promoted.sum()):,}")
c3.metric("Rows held in staging", f"{held_pct:.1%}", help="Share of all EDD rows that failed a critical check")
c4.metric("NO-GO batches", int((b.decision == "NO-GO").sum()), help=f"More than {limit:.0%} of rows held")

st.subheader("Rows held per batch")
st.caption(f"Batches above the {limit:.0%} line are returned to the laboratory (NO-GO).")
over = b.held_fraction > limit
fig = go.Figure()
for flag, name, colour in [(False, "Within limit", ui.SERIES[0]), (True, "NO-GO", ui.STATUS["critical"])]:
    sub = b[over == flag]
    fig.add_bar(x=sub.file_name, y=sub.held_fraction, name=name, marker_color=colour,
                customdata=sub[["rows_held", "row_count"]].values,
                hovertemplate="%{x}<br>%{y:.1%} held (%{customdata[0]} of %{customdata[1]} rows)<extra></extra>")
fig.add_hline(y=limit, line_dash="dash", line_color=ui.MUTED_INK,
              annotation_text=f"{limit:.0%} NO-GO limit", annotation_position="top left")
fig.update_layout(yaxis_tickformat=".0%", yaxis_title="Rows held", xaxis_title=None, height=360,
                  xaxis=dict(categoryorder="array", categoryarray=list(b.file_name)),
                  margin=dict(t=30, b=10), legend=dict(orientation="h", y=1.12), bargap=0.4)
st.plotly_chart(fig)

st.subheader("Batch status")
st.dataframe(
    b[["batch_id", "file_name", "first_sample_date", "status", "decision", "row_count", "rows_passed",
       "rows_qualified", "rows_held", "held_fraction", "n_critical", "n_warning", "rows_promoted"]],
    hide_index=True,
    column_config={"held_fraction": st.column_config.NumberColumn("held", format="percent"),
                   "first_sample_date": st.column_config.DateColumn("sampled"),
                   "file_name": "EDD file", "batch_id": "batch"})
