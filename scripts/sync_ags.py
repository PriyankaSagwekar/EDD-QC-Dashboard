"""Copy the AGS reader/checker and the AGS code lists from the pipeline repo into lib/ags/.

Runs on the laptop only. The hosted app then needs no part of the pipeline package (and none of
its SQL Server dependencies). lib/ags/SYNC.json records the pipeline commit and a SHA-256 hash
of every copied file, and tests/test_ags_viewer.py checks the copies have not been edited.

    python scripts/sync_ags.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from refresh_data import PIPELINE_REPO  # noqa: E402

TARGET = ROOT / "lib" / "ags"
SYNC = TARGET / "SYNC.json"
# pipeline path -> path under lib/ags
FILES = {
    **{f"src/eddqc/ags/{n}": n for n in ("model.py", "dictionary.py", "checker.py", "reference.py")},
    **{f"docs/reference/ags/{n}": f"reference/{n}"
       for n in ("ABBR.csv", "UNITS.csv", "DATATYPES.csv", "ELRG.csv", "SOURCE.md")},
}


def sha256(path: Path) -> str:
    """Hash with LF line ends, so a git checkout with CRLF conversion still matches."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def sync(pipeline: Path = PIPELINE_REPO) -> dict:
    missing = [src for src in FILES if not (pipeline / src).exists()]
    if missing:
        raise FileNotFoundError(f"Not found in {pipeline}: {', '.join(missing)}")
    (TARGET / "reference").mkdir(parents=True, exist_ok=True)
    for src, dst in FILES.items():
        shutil.copyfile(pipeline / src, TARGET / dst)
    commit = subprocess.run(["git", "-C", str(pipeline), "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True).stdout.strip()
    record = {"pipeline_commit": commit, "files": {dst: {"source": src, "sha256": sha256(TARGET / dst)}
                                                   for src, dst in FILES.items()}}
    SYNC.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


if __name__ == "__main__":
    rec = sync()
    print(f"Copied {len(rec['files'])} files from pipeline commit {rec['pipeline_commit']} into {TARGET}")
