import plotly.graph_objects as go
import streamlit as st

from lib import agsview as V
from lib import ui

st.title("AGS viewer")
st.caption("Check an AGS 4.2 file, browse its groups, and draw borehole logs and groundwater levels. "
           "Uploaded files are read in memory and never stored. The example file is the pipeline's export "
           "for a fictional site.")


@st.cache_data(show_spinner="Checking the file...", max_entries=8)
def checked(text: str) -> V.Checked:
    return V.check(text)


source = st.segmented_control("File", ["Example file", "Upload a file"], default="Example file")
text = st.session_state.get("ags_text")          # set directly by the tests
if text is None and source == "Upload a file":
    up = st.file_uploader(f"AGS 4.2 file (.ags, up to {V.MAX_UPLOAD_MB} MB)", type=["ags"])
    if up is None:
        st.info("Choose an .ags file to check. Only AGS 4.2 files are accepted.")
        st.stop()
    if up.size > V.MAX_UPLOAD_MB * 1024 * 1024:
        st.error(f"The file is larger than {V.MAX_UPLOAD_MB} MB.")
        st.stop()
    text = V.decode(up.getvalue())
elif text is None:
    if not V.EXAMPLE.exists():
        st.error("The example file is missing; run scripts/refresh_data.py.")
        st.stop()
    text = V.decode(V.EXAMPLE.read_bytes())

c = checked(text)
if c.rejected_version:
    st.error(next(i.message for i in c.issues if i.rule == "Version") + ". Convert the file to AGS 4.2 and try again.")
    st.stop()

check_tab, groups_tab, log_tab, gw_tab = st.tabs(["File check", "Groups", "Borehole log", "Groundwater"])

with check_tab:
    k = st.columns(4)
    k[0].metric("AGS version", c.version or "not given")
    k[1].metric("Groups", len(c.groups))
    k[2].metric("Data rows", f"{sum(len(g.rows) for g in c.groups.values()):,}")
    k[3].metric("Errors", c.n_errors)
    n_warn = sum(i.severity == "WARNING" for i in c.issues)
    n_info = sum(i.severity == "INFO" for i in c.issues)
    if c.n_errors:
        st.error(f"Fails the AGS 4.2 checks: {c.n_errors} error(s), {n_warn} warning(s), {n_info} note(s).",
                 icon=":material/cancel:")
    elif n_warn:
        st.warning(f"Passes with {n_warn} warning(s) and {n_info} note(s).", icon=":material/warning:")
    else:
        st.success(f"Passes the AGS 4.2 checks with no errors or warnings"
                   + (f" ({n_info} note(s))." if n_info else "."), icon=":material/check_circle:")
    produced = V.tran_value(c, "TRAN_PROD")
    st.caption((f"Produced by {produced}. " if produced else "") + c.lists)
    if c.issues:
        table = V.issues_table(c.issues)
        show = st.pills("Show", ["ERROR", "WARNING", "INFO"], default=["ERROR", "WARNING", "INFO"],
                        selection_mode="multi")
        st.dataframe(table[table.severity.isin(show or [])], hide_index=True, width="stretch",
                     column_config={"line": st.column_config.NumberColumn("line", format="%d")})
    with st.expander("Groups in the file"):
        st.dataframe(V.summary(c), hide_index=True)

with groups_tab:
    names = list(c.groups)
    default = names.index("ELRG") if "ELRG" in names else 0
    name = st.selectbox("Group", names, index=default)
    g = c.groups[name]
    df = c.frame(name)
    st.caption(f"{len(df):,} data rows, {len(g.headings)} headings, starting at line {g.line}. "
               "Hover a column heading for its unit and type.")
    config = {h: st.column_config.TextColumn(f"{h} ({u})" if u else h, help=f"Unit: {u or 'none'}. Type: {t}.")
              for h, u, t in zip(g.headings, g.units, g.types)}
    st.dataframe(df, hide_index=True, column_config=config, height=460)
    st.download_button(f"Download {name} as CSV", df.to_csv(index=False).encode("utf-8"), f"{name}.csv",
                       "text/csv", icon=":material/download:")

with log_tab:
    locs = V.log_locations(c)
    if not locs:
        st.info("This file has no GEOL, WSTG, MONG or SAMP data, so there is no borehole log to draw.")
    else:
        default = locs.index("MW03") if "MW03" in locs else 0
        loc = st.selectbox("Location", locs, index=default)
        info = V.location_info(c, loc)
        gl = f"{info['ground_level']:.2f} mOD" if info["ground_level"] == info["ground_level"] else "not given"
        st.caption(f"{loc}: {info['remark'] or info['type']}. Ground level {gl}; final depth "
                   f"{info['final_depth'] or 'not given'} m; easting {info['easting']}, northing {info['northing']}.")
        if not c.has("GEOL"):
            st.info("This file has no GEOL group, so the log shows no geology.")
        left, right = st.columns([3, 2])
        left.plotly_chart(V.strip_log(c, loc))
        lay = V.layers(c, loc)
        if len(lay):
            right.markdown("**Strata**")
            right.dataframe(lay.assign(stratum=lay.GEOL_LEG.map(lambda l: V.geology_class(l)[0]))
                            [["GEOL_TOP", "GEOL_BASE", "stratum", "GEOL_DESC"]]
                            .rename(columns={"GEOL_TOP": "top (m)", "GEOL_BASE": "base (m)",
                                             "GEOL_DESC": "description"}),
                            hide_index=True, width="stretch")
        right.caption("Hollow triangle: water strike. Solid triangle: level after the rise. Shaded bar: range "
                      "of later dipped levels. Ticks: sample depths. Elevations (mOD) are in the hover text.")

with gw_tab:
    w = V.water_levels(c)
    if w.empty:
        st.info("This file has no MOND depth-to-water (WDEP) readings, so there is nothing to plot.")
    else:
        wells = list(w.LOCA_ID.unique())
        picked = st.multiselect("Wells (up to 3)", wells, default=wells[:3], max_selections=3)
        sel = w[w.LOCA_ID.isin(picked)]
        if sel.empty:
            st.info("Pick at least one well.")
        else:
            st.markdown("**Depth to water** (m below ground level)")
            st.plotly_chart(V.level_chart(sel, "depth", "Depth to water (m)", ui.SERIES, reverse=True))
            if sel.elevation.notna().any():
                st.markdown("**Groundwater elevation** (ground level minus depth to water)")
                st.plotly_chart(V.level_chart(sel, "elevation", "Elevation (mOD)", ui.SERIES, reverse=False))
            with st.expander("Data table"):
                st.dataframe(sel[["LOCA_ID", "MOND_DTIM", "MOND_REF", "depth", "elevation", "MOND_REM"]]
                             if "MOND_REM" in sel else sel[["LOCA_ID", "MOND_DTIM", "depth", "elevation"]],
                             hide_index=True)
    pts = V.location_points(c)
    if len(pts):
        st.markdown("**Locations in the file**")
        has_mond = pts.LOCA_ID.isin(set(w.LOCA_ID)) if len(w) else pts.LOCA_ID.isin([])
        fig = go.Figure()
        for flag, name, colour in ((True, "Has water level readings", ui.SERIES[0]),
                                   (False, "No water level readings", ui.STATUS["none"])):
            sub = pts[has_mond == flag]
            if len(sub):
                fig.add_trace(go.Scattermap(lat=sub.lat, lon=sub.lon, mode="markers+text", name=name,
                                            marker=dict(size=13, color=colour), text=sub.LOCA_ID,
                                            textposition="top right",
                                            hovertemplate="<b>%{text}</b><extra></extra>"))
        fig.update_layout(map=dict(style="carto-positron", center=dict(lat=pts.lat.mean(), lon=pts.lon.mean()),
                                   zoom=15.3), height=420, margin=dict(l=0, r=0, t=0, b=0),
                          legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0))
        st.plotly_chart(fig)
