"""Droid Debug Bridge — CLI toolkit for AI-assisted Android development."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("ddb-tool")
except PackageNotFoundError:
    __version__ = "0.0.0"
