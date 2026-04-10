"""Tests for the JSON output helpers."""

import json

from ddb.utils.output import ok, err


def test_ok_basic(capsys):
    result = ok({"key": "value"}, message="it worked")
    assert result["success"] is True
    assert result["message"] == "it worked"
    assert result["data"]["key"] == "value"

    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["success"] is True


def test_ok_no_data(capsys):
    result = ok(message="done")
    assert result["success"] is True
    assert "data" not in result


def test_err_basic(capsys):
    result = err("something broke", hint="try again")
    assert result["success"] is False
    assert result["error"] == "something broke"
    assert result["hint"] == "try again"

    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["success"] is False


def test_err_no_hint(capsys):
    result = err("oops")
    assert "hint" not in result
