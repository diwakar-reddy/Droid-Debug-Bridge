"""Tests for the JSON output helpers."""

import json

from ddb.utils.output import emit, err, ok


def test_ok_basic():
    result = ok({"key": "value"}, message="it worked")
    assert result["success"] is True
    assert result["message"] == "it worked"
    assert result["data"]["key"] == "value"


def test_ok_no_data():
    result = ok(message="done")
    assert result["success"] is True
    assert "data" not in result


def test_err_basic():
    result = err("something broke", hint="try again")
    assert result["success"] is False
    assert result["error"] == "something broke"
    assert result["hint"] == "try again"


def test_err_no_hint():
    result = err("oops")
    assert "hint" not in result


def test_emit(capsys):
    data = {"success": True, "message": "hello"}
    emit(data)
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["success"] is True
    assert parsed["message"] == "hello"
