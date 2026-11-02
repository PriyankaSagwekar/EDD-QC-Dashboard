"""The refresh copies every view in full. Skipped when SQL Server is not reachable."""
import json

import duckdb
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

import refresh_data


@pytest.fixture(scope="module")
def engine():
    eng, _, _ = refresh_data.sql_engine()
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1 FROM dbo.vw_Batch_Summary WHERE 1 = 0"))
    except DBAPIError:
        pytest.skip("SQL Server or the EnvDataQC views are not reachable")
    return eng


def test_refresh_copies_every_view(engine, tmp_path):
    manifest = refresh_data.refresh(tmp_path)
    assert json.loads((tmp_path / "manifest.json").read_text())["tables"] == manifest["tables"]
    with duckdb.connect(str(tmp_path / "envdataqc.duckdb"), read_only=True) as con, engine.connect() as conn:
        for name, sql in refresh_data.TABLES.items():
            expected = conn.execute(text(f"SELECT COUNT(*) FROM ({sql}) t")).scalar()
            assert con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] == expected, name
        for name in refresh_data.POINT_TABLES:
            lat, lon = con.execute(f"SELECT AVG(lat), AVG(lon) FROM {name}").fetchone()
            assert 53.7 < lat < 53.9 and -1.6 < lon < -1.5   # fictional site plots in Leeds
