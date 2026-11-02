"""AGS viewer: the example renders, broken and older files are handled, and lib/ags is an unedited copy."""
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from lib import agsview as V

ROOT = Path(__file__).resolve().parents[1]
PAGE = str(ROOT / "pages" / "ags_viewer.py")


@pytest.fixture(scope="module")
def example():
    if not V.EXAMPLE.exists():
        pytest.skip("No example AGS file; run scripts/refresh_data.py")
    return V.decode(V.EXAMPLE.read_bytes())


def run(text=None) -> AppTest:
    at = AppTest.from_file(PAGE, default_timeout=60)
    if text is not None:
        at.session_state["ags_text"] = text
    at.run()
    return at


def test_example_file_renders_every_tab(example):
    at = run()
    assert not at.exception, at.exception
    assert not at.error
    assert [t.label for t in at.tabs] == ["File check", "Groups", "Borehole log", "Groundwater"]
    assert any("Passes the AGS 4.2 checks" in s.value for s in at.success)
    log = next(s for s in at.selectbox if s.label == "Location")
    for loc in log.options:
        log.set_value(loc).run()
        assert not at.exception, loc


def test_strip_log_has_one_block_per_geology_row(example):
    c = V.check(example)
    for loc in V.log_locations(c):
        fig = V.strip_log(c, loc)
        blocks = [t for t in fig.data if t.type == "bar" and list(t.x) == ["Geology"]]
        assert len(blocks) == len(V.layers(c, loc)), loc


def test_other_versions_are_rejected_and_nothing_else_shown(example):
    at = run(example.replace('"4.2","Portfolio', '"4.1","Portfolio'))
    assert not at.exception
    assert any("Only AGS 4.2 files are accepted" in e.value for e in at.error)
    assert len(at.tabs) == 0


def test_broken_file_shows_errors(example):
    broken = example.replace("\r\n", "\n").replace('"GROUP","LOCA"', '"GROUP","LOCX"')
    at = run(broken)
    assert not at.exception
    assert any("Fails the AGS 4.2 checks" in e.value for e in at.error)
    rules = set(V.issues_table(V.check(broken).issues).rule)
    assert {"Rule 2a", "Rule 10c"} <= rules


def drop_group(text, *names):
    keep, skip = [], False
    for ln in text.split("\r\n"):
        if ln.startswith('"GROUP"'):
            skip = ln in {f'"GROUP","{n}"' for n in names}
        keep.append("" if skip else ln)
    return "\r\n".join(keep)


def test_charts_survive_any_missing_group(example):
    """A partial or third-party file must never break a chart, only leave it emptier."""
    names = list(V.check(example).groups)
    for name in names:
        c = V.check(drop_group(example, name))
        for loc in V.log_locations(c)[:3]:
            V.strip_log(c, loc)
        V.water_levels(c)
        V.location_points(c)
        V.summary(c)


def test_file_without_geology_or_water_levels_shows_notices(example):
    lines, keep, skip = example.split("\r\n"), [], False
    for ln in lines:
        if ln.startswith('"GROUP"'):
            skip = ln in ('"GROUP","GEOL"', '"GROUP","MOND"', '"GROUP","WSTG"', '"GROUP","WSTD"')
        keep.append("" if skip else ln)
    at = run("\r\n".join(keep))
    assert not at.exception
    notices = " ".join(i.value for i in at.info)
    assert "no GEOL group" in notices and "no MOND" in notices


def test_copied_ags_modules_are_unchanged():
    sync = json.loads((ROOT / "lib" / "ags" / "SYNC.json").read_text())
    from sync_ags import FILES, PIPELINE_REPO, sha256
    assert set(sync["files"]) == set(FILES.values())
    for dst, rec in sync["files"].items():
        assert sha256(ROOT / "lib" / "ags" / dst) == rec["sha256"], f"lib/ags/{dst} was edited; sync again"
    if PIPELINE_REPO.exists():                       # on the laptop: also current with the pipeline
        stale = [d for s, d in FILES.items() if sha256(PIPELINE_REPO / s) != sync["files"][d]["sha256"]]
        assert not stale, f"Run scripts/sync_ags.py; changed in the pipeline: {stale}"
