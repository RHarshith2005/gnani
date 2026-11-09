"""Vercel Python entrypoint.

Local runs still use ``uvicorn api.main:app``; Vercel detects this file's
top-level ``app`` and routes every request (including ``/ws/voice``) to it.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.main import app  # noqa: E402

__all__ = ["app"]
