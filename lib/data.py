"""Read-only access to the DuckDB snapshot written by scripts/refresh_data.py."""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DB_FILE = ROOT / "data" / "envdataqc.duckdb"
MANIFEST = ROOT / "data" / "manifest.json"
SCHEMA_VERSION = 1
TABLES = ("batch_summary", "exception_summary", "exception_detail", "qualifier_summary", "held_rows",
          "location_qc_status", "result_timeseries", "screening_exceedance", "screening_summary",
          "screening_location", "rules")


@st.cache_data(ttl=600, show_spinner=False)
def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    with duckdb.connect(str(DB_FILE), read_only=True) as con:
        return con.execute(sql, list(params)).df()


def table(name: str) -> pd.DataFrame:
    if name not in TABLES:
        raise ValueError(f"Unknown table {name}")
    return query(f"SELECT * FROM {name}")


@st.cache_data(ttl=600, show_spinner=False)
def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}


def problems() -> list[str]:
    """Reasons the snapshot cannot be shown. Empty when it is fine."""
    if not DB_FILE.exists():
        return [f"No data file at {DB_FILE.relative_to(ROOT)}. Run scripts/refresh_data.py."]
    found = set(query("SELECT table_name FROM information_schema.tables").table_name)
    missing = [t for t in TABLES if t not in found]
    return [f"Data file is missing tables: {', '.join(missing)}. Re-run scripts/refresh_data.py."] if missing else []


def schema_warning() -> str | None:
    version = manifest().get("schema_version")
    if version != SCHEMA_VERSION:
        return f"Data schema version {version} does not match the app ({SCHEMA_VERSION}). Refresh the data."
    return None


def max_held_fraction() -> float:
    return float(manifest().get("max_held_fraction", 0.10))


def decision(rows: int, held: int, qualified: int, max_held: float) -> tuple[str, str]:
    """Same import decision as report.decision() in the pipeline repo."""
    rows = max(rows, 1)
    if held / rows > max_held:
        return ("NO-GO", f"{held / rows:.0%} of rows are held, above the {max_held:.0%} limit. "
                         "Return the EDD to the laboratory for correction.")
    if held:
        return ("PARTIAL", "Promote passed and qualified rows. Held rows stay in staging for review.")
    if qualified:
        return ("GO WITH QUALIFIERS", "All rows can be promoted. Qualified results carry validator flags.")
    return ("GO", "All rows passed every check.")
