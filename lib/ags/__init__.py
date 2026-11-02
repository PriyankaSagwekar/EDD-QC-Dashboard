"""AGS 4.2 parser and checker, copied from the pipeline repo by scripts/sync_ags.py (see SYNC.json).

Do not edit the copied modules here; change them in the pipeline repo and sync again.
"""
from .checker import VERSION_ERROR, Issue, check_text, errors, file_version
from .model import Group
from .reference import Reference, load_reference
