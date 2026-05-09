"""spider2_lite_snow_tools_v8 — re-export of SF executor for Lite/SF lane.

The SF lane in Spider2-Lite is the same path Spider2-Snow uses; this
shim exists so the Lite runner can import lane-specific tools by name.
"""
from __future__ import annotations

from spider2_sf_executor_v8 import build_sf_executor  # noqa: F401
