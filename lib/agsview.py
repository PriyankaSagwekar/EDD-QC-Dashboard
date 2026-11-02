"""AGS viewer: check an AGS 4.2 file and turn its groups into tables, borehole logs and water level charts."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from .ags import VERSION_ERROR, Group, Issue, check_text, errors, file_version, load_reference

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "data" / "example_RIE01.ags"
MAX_UPLOAD_MB = 20
SEVERITY_ORDER = {"ERROR": 0, "WARNING": 1, "INFO": 2}

# Soil and rock classes by the first digit of the AGS legend code (GEOL_LEG): conventional log colours,
# each with its own hatch so colour is never the only cue.
GEOLOGY_CLASS = {
    "1": ("Made ground / topsoil", "#8c7b6b", "x"),
    "2": ("Clay", "#8f9a55", "-"),
    "3": ("Silt", "#b8a77a", "/"),
    "4": ("Sand", "#e8cf6a", "."),
    "5": ("Gravel", "#e39a4c", "+"),
    "6": ("Peat / organic", "#5b4636", "\\"),
    "7": ("Cobbles / boulders", "#b0855a", "+"),
    "8": ("Rock", "#7d8a99", "|"),
    "9": ("Rock", "#7d8a99", "|"),
}
OTHER_CLASS = ("Other / unknown", "#c3c2b7", "")
WATER = "#2a78d6"
INK = "#52514e"


@dataclass
class Checked:
    groups: dict[str, Group]
    issues: list[Issue]
    version: str
    lists: str

    @property
    def rejected_version(self) -> bool:
        return any(i.rule == "Version" and i.severity == "ERROR" for i in self.issues)

    @property
    def n_errors(self) -> int:
        return len(errors(self.issues))

    def frame(self, name: str, needs: tuple[str, ...] = ()) -> pd.DataFrame:
        """A group as a table of strings, without the file line column. Empty if the group, or any
        heading in needs, is missing, so a partial or third-party file never breaks a chart."""
        g = self.groups.get(name)
        df = g.frame().drop(columns="_line") if g else pd.DataFrame()
        return df if set(needs) <= set(df.columns) else pd.DataFrame(columns=list(needs))

    def has(self, *names: str) -> bool:
        return all(n in self.groups and self.groups[n].rows for n in names)


def check(text: str) -> Checked:
    """AGS 4.2 only: any other version is rejected (the pipeline itself also reads 4.0 and 4.1)."""
    groups, issues = check_text(text, strict_version=True)
    return Checked(groups, issues, file_version(groups), load_reference().summary())


def decode(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace")


def issues_table(issues: list[Issue]) -> pd.DataFrame:
    df = pd.DataFrame([vars(i) for i in issues], columns=["severity", "rule", "group", "line", "message"])
    df["_order"] = df.severity.map(SEVERITY_ORDER)
    return df.sort_values(["_order", "line"], kind="stable").drop(columns="_order").reset_index(drop=True)


def summary(c: Checked) -> pd.DataFrame:
    rows = [(g.name, len(g.rows), len(g.headings), g.line) for g in c.groups.values()]
    return pd.DataFrame(rows, columns=["group", "data_rows", "headings", "line"])


def tran_value(c: Checked, heading: str) -> str:
    t = c.frame("TRAN", (heading,))
    return t[heading].iloc[0] if len(t) else ""


def num(s) -> pd.Series:
    return pd.to_numeric(pd.Series(s), errors="coerce")


def geology_class(legend: str) -> tuple[str, str, str]:
    return GEOLOGY_CLASS.get(str(legend)[:1], OTHER_CLASS)


def location_info(c: Checked, loc: str) -> dict:
    loca = c.frame("LOCA", ("LOCA_ID",))
    row = loca[loca.LOCA_ID == loc]
    get = lambda h: row[h].iloc[0] if h in row and len(row) else ""
    return {"type": get("LOCA_TYPE"), "easting": get("LOCA_NATE"), "northing": get("LOCA_NATN"),
            "ground_level": num([get("LOCA_GL")]).iloc[0], "final_depth": get("LOCA_FDEP"),
            "remark": get("LOCA_REM")}


def log_locations(c: Checked) -> list[str]:
    """Locations that have something to draw on a log, in LOCA order."""
    found = []
    for name in ("GEOL", "WSTG", "MONG", "SAMP"):
        found += list(c.frame(name, ("LOCA_ID",)).LOCA_ID)
    loca = list(c.frame("LOCA", ("LOCA_ID",)).LOCA_ID)
    return [l for l in dict.fromkeys(loca + found) if l in set(found)]


def layers(c: Checked, loc: str) -> pd.DataFrame:
    g = c.frame("GEOL", ("LOCA_ID", "GEOL_TOP", "GEOL_BASE"))
    g = g[g.LOCA_ID == loc].copy()
    g["top"], g["base"] = num(g.GEOL_TOP).values, num(g.GEOL_BASE).values
    for h in ("GEOL_LEG", "GEOL_GEOL", "GEOL_DESC", "GEOL_FORM"):
        if h not in g:
            g[h] = ""
    return g.dropna(subset=["top", "base"]).sort_values("top")


def strip_log(c: Checked, loc: str) -> go.Figure:
    """Depth-down log: geology column, well installation, water strikes and sample depths."""
    gl = location_info(c, loc)["ground_level"]
    mod = lambda d: f"{gl - d:.2f} mOD" if pd.notna(gl) and pd.notna(d) else "mOD not given"
    fig, depth_max = go.Figure(), 0.0

    shown = set()
    for r in layers(c, loc).itertuples():
        name, colour, hatch = geology_class(r.GEOL_LEG)
        fig.add_bar(x=["Geology"], y=[r.base - r.top], base=[r.top], name=name, legendgroup=name,
                    showlegend=name not in shown, width=0.9,
                    marker=dict(color=colour, line=dict(color="white", width=2),
                                pattern=dict(shape=hatch, fgcolor="rgba(0,0,0,0.35)", size=8, fillmode="overlay")),
                    text=[r.GEOL_GEOL or r.GEOL_LEG], textposition="inside", insidetextanchor="middle",
                    hovertemplate=f"<b>{r.top:.2f}-{r.base:.2f} m</b> ({mod(r.top)} to {mod(r.base)})<br>"
                                  f"{r.GEOL_DESC}<br>{r.GEOL_FORM}<extra></extra>")
        shown.add(name)
        depth_max = max(depth_max, r.base)

    mong = c.frame("MONG", ("LOCA_ID", "MONG_TRZ", "MONG_BRZ"))
    for r in mong[mong.LOCA_ID == loc].itertuples():
        top, base = num([r.MONG_TRZ, r.MONG_BRZ])
        if pd.isna(top) or pd.isna(base):
            continue
        fig.add_bar(x=["Well"], y=[top], base=[0], name="Plain casing", width=0.35,
                    marker=dict(color="#d9d8d0", line=dict(color=INK, width=1)),
                    hovertemplate=f"Plain casing 0.00-{top:.2f} m<extra></extra>")
        fig.add_bar(x=["Well"], y=[base - top], base=[top], name="Slotted screen", width=0.35,
                    marker=dict(color="white", line=dict(color=WATER, width=2),
                                pattern=dict(shape="-", fgcolor=WATER, size=5, fillmode="overlay")),
                    hovertemplate=f"Screen {top:.2f}-{base:.2f} m ({mod(top)} to {mod(base)})<extra></extra>")
        depth_max = max(depth_max, base)

    wstg = c.frame("WSTG", ("LOCA_ID", "WSTG_DPTH"))
    wstd = c.frame("WSTD", ("LOCA_ID", "WSTG_DPTH", "WSTD_NMIN", "WSTD_POST"))
    for r in wstg[wstg.LOCA_ID == loc].itertuples():
        strike = num([r.WSTG_DPTH]).iloc[0]
        if pd.isna(strike):
            continue
        fig.add_scatter(x=["Water"], y=[strike], mode="markers", name="Water strike",
                        marker=dict(symbol="triangle-down-open", size=16, color=WATER, line=dict(width=2)),
                        hovertemplate=f"Water struck at {strike:.2f} m ({mod(strike)})<extra></extra>")
        posts = wstd[(wstd.LOCA_ID == loc) & (wstd.WSTG_DPTH == r.WSTG_DPTH)]
        posts = posts.assign(n=num(posts.WSTD_NMIN).values, d=num(posts.WSTD_POST).values).dropna(subset=["d"])
        if len(posts):
            last = posts.sort_values("n").iloc[-1]
            fig.add_scatter(x=["Water"], y=[last.d], mode="markers", name="Level after rise",
                            marker=dict(symbol="triangle-down", size=16, color=WATER),
                            hovertemplate=f"Rose to {last.d:.2f} m after {last.n:.0f} min "
                                          f"({mod(last.d)})<extra></extra>")
            fig.add_annotation(x="Water", y=last.d, ax="Water", ay=strike, xref="x", yref="y", axref="x",
                               ayref="y", showarrow=True, arrowhead=2, arrowcolor=WATER, text="")
        depth_max = max(depth_max, strike)

    mond = c.frame("MOND", ("LOCA_ID", "MOND_TYPE", "MOND_RDNG"))
    dips = num(mond[(mond.LOCA_ID == loc) & (mond.MOND_TYPE == "WDEP")].MOND_RDNG.values).dropna()
    if len(dips):
        fig.add_bar(x=["Water"], y=[max(dips.max() - dips.min(), 0.02)], base=[dips.min()], width=0.25,
                    name="Range of dipped levels", marker=dict(color="rgba(42,120,214,0.25)"),
                    hovertemplate=f"{len(dips)} dips: {dips.min():.2f}-{dips.max():.2f} m<extra></extra>")

    samp = c.frame("SAMP", ("LOCA_ID", "SAMP_TOP", "SAMP_ID", "SAMP_TYPE"))
    elrg = c.frame("ELRG", ("SAMP_ID",))
    s = samp[samp.LOCA_ID == loc].copy()
    s["depth"] = num(s.SAMP_TOP).values
    s = s.dropna(subset=["depth"])
    if len(s):
        s["n"] = s.SAMP_ID.map(elrg.groupby("SAMP_ID").size()).fillna(0).astype(int)
        s["kind"] = s.SAMP_TYPC if "SAMP_TYPC" in s else s.SAMP_TYPE
        fig.add_scatter(x=["Samples"] * len(s), y=s.depth, mode="markers", name="Sample",
                        marker=dict(symbol="line-ew-open", size=26, color=INK, line=dict(width=2)),
                        customdata=s[["SAMP_ID", "kind", "n"]].values,
                        hovertemplate="%{customdata[0]}<br>%{customdata[1]}, top %{y:.2f} m<br>"
                                      "%{customdata[2]} lab results<extra></extra>")
        depth_max = max(depth_max, s.depth.max())

    final = num([location_info(c, loc)["final_depth"]]).iloc[0]
    bottom = max(depth_max, final if pd.notna(final) else 0) or 1
    fig.update_layout(barmode="overlay", height=620, margin=dict(t=10, b=10, l=10, r=10),
                      legend=dict(orientation="h", y=-0.08), bargap=0.1, hovermode="closest",
                      yaxis=dict(title="Depth (m below ground level)", range=[bottom * 1.03, -0.05],
                                 zeroline=True, zerolinecolor=INK, gridcolor="#ecebe6"),
                      xaxis=dict(categoryorder="array", categoryarray=["Geology", "Well", "Water", "Samples"],
                                 side="top"),
                      plot_bgcolor="white")
    return fig


def water_levels(c: Checked) -> pd.DataFrame:
    mond = c.frame("MOND", ("LOCA_ID", "MOND_TYPE", "MOND_DTIM", "MOND_RDNG"))
    w = mond[mond.MOND_TYPE == "WDEP"].copy()
    w["when"] = pd.to_datetime(w.MOND_DTIM, errors="coerce")
    w["depth"] = num(w.MOND_RDNG.values).values
    loca = c.frame("LOCA", ("LOCA_ID", "LOCA_GL")).drop_duplicates("LOCA_ID")
    w["elevation"] = num(w.LOCA_ID.map(loca.set_index("LOCA_ID").LOCA_GL).values).values - w.depth
    return w.dropna(subset=["when", "depth"]).sort_values(["LOCA_ID", "when"])


def level_chart(w: pd.DataFrame, value: str, title: str, colours: list[str], reverse: bool) -> go.Figure:
    unit = title.split("(")[-1].rstrip(")")
    fig = go.Figure()
    for loc, colour in zip(w.LOCA_ID.unique(), colours):
        sub = w[w.LOCA_ID == loc]
        fig.add_scatter(x=sub.when, y=sub[value], mode="lines+markers", name=loc,
                        line=dict(color=colour, width=2), marker=dict(size=9, color=colour),
                        hovertemplate=f"<b>{loc}</b><br>%{{x|%d %b %Y}}<br>%{{y:.2f}} {unit}<extra></extra>")
    fig.update_layout(height=340, margin=dict(t=10, b=10), yaxis_title=title, hovermode="closest",
                      legend=dict(orientation="h", y=1.12), xaxis=dict(tickformat="%b %Y"))
    if reverse:
        fig.update_yaxes(autorange="reversed")
    return fig


def location_points(c: Checked) -> pd.DataFrame:
    """LOCA rows with WGS84 lat/lon, for files in British National Grid (OSGB / EPSG:27700)."""
    loca = c.frame("LOCA", ("LOCA_ID", "LOCA_NATE", "LOCA_NATN"))
    pts = loca.assign(e=num(loca.LOCA_NATE.values).values, n=num(loca.LOCA_NATN.values).values)
    pts = pts.dropna(subset=["e", "n"])
    gref = pts.LOCA_GREF if "LOCA_GREF" in pts else pd.Series("", index=pts.index)
    nsri = pts.LOCA_NSRI if "LOCA_NSRI" in pts else pd.Series("", index=pts.index)
    pts = pts[(gref == "OSGB") | (nsri == "27700")]
    if pts.empty:
        return pts
    from pyproj import Transformer
    lon, lat = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True).transform(pts.e.values, pts.n.values)
    return pts.assign(lat=lat, lon=lon)
