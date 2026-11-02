"""Copy the EDD QA/QC reporting views from the local SQL Server into data/envdataqc.duckdb.

Runs on the laptop only. The hosted dashboard reads the DuckDB file and never connects
to SQL Server. Usage:

    python scripts/refresh_data.py            # rebuild data/envdataqc.duckdb + data/manifest.json
    python scripts/refresh_data.py --push     # ...then git commit and push the data folder

Connection settings come from EDDQC_SERVER / EDDQC_DATABASE (Windows authentication).
"""
from __future__ import annotations

import argparse
import datetime as dt
import decimal
import json
import os
import shutil
import subprocess
import tomllib
import urllib.parse
from pathlib import Path

import duckdb
import pandas as pd
from pyproj import Transformer
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DB_FILE = DATA / "envdataqc.duckdb"
MANIFEST = DATA / "manifest.json"
EXAMPLE_AGS = DATA / "example_RIE01.ags"   # sample file for the AGS viewer page
PIPELINE_REPO = Path(os.environ.get("EDDQC_PIPELINE_REPO", ROOT.parent / "EDD-Validation-Engine-and-QA-QC"))
SCHEMA_VERSION = 1

# DuckDB table -> SQL Server query. Everything except the rule catalogue is a reporting view.
TABLES = {
    "batch_summary": "SELECT * FROM dbo.vw_Batch_Summary",
    "exception_summary": "SELECT * FROM dbo.vw_Exception_Summary",
    "exception_detail": "SELECT * FROM dbo.vw_Exception_Detail",
    "qualifier_summary": "SELECT * FROM dbo.vw_Qualifier_Summary",
    "held_rows": "SELECT * FROM dbo.vw_Held_Rows",
    "location_qc_status": "SELECT * FROM dbo.vw_Location_QC_Status",
    "result_timeseries": "SELECT * FROM dbo.vw_Result_Timeseries",
    "screening_exceedance": "SELECT * FROM dbo.vw_Screening_Exceedance",
    "screening_summary": "SELECT * FROM dbo.vw_Screening_Summary",
    "screening_location": "SELECT * FROM dbo.vw_Screening_Location",
    "rules": "SELECT rule_id, family, rule_name, severity, default_qualifier, description FROM dbo.qc_Rule",
}
# Tables that get WGS84 lat/lon added for web maps (source is British National Grid).
POINT_TABLES = ("location_qc_status", "screening_location")


def sql_engine():
    server = os.environ.get("EDDQC_SERVER", r".\SQLEXPRESS")
    database = os.environ.get("EDDQC_DATABASE", "EnvDataQC")
    odbc = (f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};"
            "Trusted_Connection=yes;")
    return create_engine(f"mssql+pyodbc:///?odbc_connect={urllib.parse.quote_plus(odbc)}"), server, database


def tidy(df: pd.DataFrame) -> pd.DataFrame:
    """Turn SQL Server decimals and dates into types DuckDB stores natively."""
    for col in df.columns:
        sample = df[col].dropna()
        if sample.empty:
            continue
        first = sample.iloc[0]
        if isinstance(first, decimal.Decimal):
            df[col] = df[col].astype(float)
        elif isinstance(first, dt.date) and not isinstance(first, dt.datetime):
            df[col] = pd.to_datetime(df[col])
    return df


def add_lat_lon(df: pd.DataFrame) -> pd.DataFrame:
    to_wgs84 = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
    lon, lat = to_wgs84.transform(df.easting.astype(float).values, df.northing.astype(float).values)
    return df.assign(lon=lon, lat=lat)


def pipeline_info() -> dict:
    info = {"pipeline_commit": None, "max_held_fraction": 0.10}
    try:
        out = subprocess.run(["git", "-C", str(PIPELINE_REPO), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, check=True)
        info["pipeline_commit"] = out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        pass
    settings = PIPELINE_REPO / "config" / "settings.toml"
    if settings.exists():
        cfg = tomllib.loads(settings.read_text(encoding="utf-8"))
        info["max_held_fraction"] = cfg.get("validation", {}).get("max_held_fraction", 0.10)
    return info


def copy_example_ags(data_dir: Path) -> str | None:
    """Copy the pipeline's latest full AGS export (not a single-batch one) as the viewer's example file."""
    exports = sorted(p for p in (PIPELINE_REPO / "data" / "ags").glob("RIE01_*.ags") if "_batch" not in p.name)
    if not exports:
        return None
    shutil.copyfile(exports[-1], data_dir / EXAMPLE_AGS.name)
    return exports[-1].name


def refresh(data_dir: Path = DATA) -> dict:
    engine, server, database = sql_engine()
    data_dir.mkdir(parents=True, exist_ok=True)
    db_file = data_dir / DB_FILE.name
    tmp = db_file.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    counts = {}
    with engine.connect() as conn, duckdb.connect(str(tmp)) as con:
        for name, sql in TABLES.items():
            df = tidy(pd.read_sql(text(sql), conn))
            if name in POINT_TABLES:
                df = add_lat_lon(df)
            con.register("frame", df)
            con.execute(f"CREATE TABLE {name} AS SELECT * FROM frame")
            con.unregister("frame")
            counts[name] = len(df)
    os.replace(tmp, db_file)
    example = copy_example_ags(data_dir)

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_utc": dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "source": f"{server} / {database}",
        **pipeline_info(),
        "tables": counts,
        "example_ags": example,
        "note": "Fictional site and simulated laboratory data. Screening criteria are illustrative.",
    }
    (data_dir / MANIFEST.name).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def push() -> None:
    subprocess.run(["git", "-C", str(ROOT), "add", "data/envdataqc.duckdb", "data/manifest.json",
                    "data/example_RIE01.ags"], check=True)
    staged = subprocess.run(["git", "-C", str(ROOT), "diff", "--cached", "--quiet"])
    if staged.returncode == 0:
        print("Data unchanged; nothing to push.")
        return
    subprocess.run(["git", "-C", str(ROOT), "commit", "-m", "Refresh dashboard data"], check=True)
    subprocess.run(["git", "-C", str(ROOT), "push"], check=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--push", action="store_true", help="commit and push the refreshed data")
    args = p.parse_args()
    m = refresh()
    print(f"Wrote {DB_FILE} ({sum(m['tables'].values())} rows in {len(m['tables'])} tables)")
    if args.push:
        push()


if __name__ == "__main__":
    main()
