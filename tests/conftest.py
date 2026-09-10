"""Isolate every test run from the user's real app-data directory."""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault(
    "YTPDL_DATA_DIR", tempfile.mkdtemp(prefix="ytpdl_test_data_")
)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
