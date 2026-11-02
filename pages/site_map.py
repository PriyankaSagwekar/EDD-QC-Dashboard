import streamlit as st

from lib import data, maps, ui

ui.page("Site map", "QC status of every borehole, monitoring well and trial pit.")

loc = data.table("location_qc_status")
if not maps.embed("site_qc"):
    st.plotly_chart(ui.site_map(
        loc, "qc_rag", ui.RAG, ui.RAG_LABEL, ["RED", "AMBER", "GREEN", "GREY"],
        {"location_type": "Type", "n_samples": "Samples", "n_held": "Results held",
         "n_qualified": "Results qualified", "n_critical_exceptions": "Critical exceptions"}))
    st.caption("Locations are placed for illustration only; the site is fictional. "
               "Coordinates are stored in British National Grid (EPSG:27700) and converted to WGS84 for the web map.")

st.subheader("Locations")
st.dataframe(loc[["location_code", "location_type", "qc_rag", "n_samples", "n_results", "n_held", "n_qualified",
                  "n_critical_exceptions", "n_warning_exceptions", "last_sample_date", "easting", "northing"]],
             hide_index=True, column_config={"qc_rag": "QC status", "last_sample_date":
                                             st.column_config.DatetimeColumn("last sampled", format="YYYY-MM-DD")})
