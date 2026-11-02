"""Embedded ArcGIS Online maps, configured in config/maps.toml."""
from __future__ import annotations

import tomllib
from pathlib import Path

import streamlit as st

CONFIG = Path(__file__).resolve().parents[1] / "config" / "maps.toml"


def url(key: str) -> str:
    if not CONFIG.exists():
        return ""
    return tomllib.loads(CONFIG.read_text(encoding="utf-8")).get("maps", {}).get(key, "").strip()


def embed(key: str, height: int = 620) -> bool:
    """Show the ArcGIS map for key. Returns False when none is configured."""
    src = url(key)
    if not src:
        return False
    st.iframe(src, height=height)
    st.caption(f"Map made in ArcGIS Online. [Open full screen]({src})")
    return True
