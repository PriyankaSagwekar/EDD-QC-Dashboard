"""Smoke tests: every page renders against the committed snapshot without errors."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
PAGES = sorted(p.name for p in (ROOT / "pages").glob("*.py"))


@pytest.fixture(autouse=True)
def snapshot_present():
    if not (ROOT / "data" / "envdataqc.duckdb").exists():
        pytest.skip("No data snapshot; run scripts/refresh_data.py")


def run(path: Path) -> AppTest:
    at = AppTest.from_file(str(path), default_timeout=60)
    at.run()
    return at


def test_entry_point_renders_overview():
    at = run(ROOT / "app.py")
    assert not at.exception
    assert at.title[0].value == "EDD QA/QC overview"


@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page):
    at = run(ROOT / "pages" / page)
    assert not at.exception, at.exception
    assert not at.error


def test_every_batch_and_location_renders():
    at = run(ROOT / "pages" / "batch_detail.py")
    for name in at.selectbox[0].options:
        at.selectbox[0].set_value(name).run()
        assert not at.exception
    at = run(ROOT / "pages" / "results_explorer.py")
    for loc in at.selectbox[0].options:
        at.selectbox[0].set_value(loc).run()
        assert not at.exception, loc


def test_decision_matches_pipeline_rule():
    from lib.data import decision
    assert decision(100, 11, 0, 0.10)[0] == "NO-GO"
    assert decision(100, 10, 0, 0.10)[0] == "PARTIAL"
    assert decision(100, 0, 5, 0.10)[0] == "GO WITH QUALIFIERS"
    assert decision(100, 0, 0, 0.10)[0] == "GO"
