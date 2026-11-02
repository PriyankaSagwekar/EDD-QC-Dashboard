"""EDD QA/QC dashboard. Run with: streamlit run app.py"""
import streamlit as st

st.set_page_config(page_title="EDD QA/QC Dashboard", page_icon=":material/science:", layout="wide")

pages = [
    st.Page("pages/overview.py", title="Overview", icon=":material/dashboard:", default=True),
    st.Page("pages/exceptions.py", title="Exceptions", icon=":material/rule:"),
    st.Page("pages/batch_detail.py", title="Batch detail", icon=":material/fact_check:"),
    st.Page("pages/site_map.py", title="Site map", icon=":material/map:"),
    st.Page("pages/results_explorer.py", title="Results explorer", icon=":material/show_chart:"),
    st.Page("pages/screening.py", title="Screening", icon=":material/warning:"),
    st.Page("pages/ags_viewer.py", title="AGS viewer", icon=":material/layers:"),
]
st.navigation(pages).run()
