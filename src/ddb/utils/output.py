"""Structured JSON output helpers."""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, Optional


def ok(data: Any = None, message: Optional[str] = None) -> Dict:
    """Build a success response dict and print it as JSON."""
    resp: Dict[str, Any] = {"success": True}
    if message:
        resp["message"] = message
    if data is not None:
        resp["data"] = data
    _emit(resp)
    return resp


def err(message: str, hint: Optional[str] = None) -> Dict:
    """Build an error response dict and print it as JSON."""
    resp: Dict[str, Any] = {"success": False, "error": message}
    if hint:
        resp["hint"] = hint
    _emit(resp)
    return resp


def _emit(data: Dict) -> None:
    """Print compact JSON to stdout."""
    print(json.dumps(data, indent=2, ensure_ascii=False))
