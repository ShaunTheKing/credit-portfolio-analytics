#!/usr/bin/env python3
"""
requirements.py — shared dependency check with actionable guidance.

Importing this module gives one place that explains how to install what the
scripts need, tailored to the interpreter that is actually running.

The common trap this exists to prevent:

    pip install duckdb        -> installs the Python MODULE the scripts import
    brew install duckdb       -> installs only the CLI, which the scripts do NOT use

On Homebrew and Debian/Ubuntu Python, `pip install` into the system interpreter
is blocked (PEP 668, "externally-managed-environment"). A virtual environment is
the reliable fix and works on every platform.
"""

from __future__ import annotations

import os
import shutil
import sys
import sysconfig
import venv


def in_virtualenv() -> bool:
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def pip_install_hint() -> str:
    """Return an install instruction appropriate to the current interpreter."""
    py = "python3" if shutil.which("python3") else sys.executable

    if in_virtualenv():
        return f"  {py} -m pip install duckdb xlrd"

    lines = [
        "This interpreter is not a virtual environment, so a plain `pip install`",
        "may be refused by your OS (PEP 668: 'externally-managed-environment').",
        "",
        "Recommended — create a virtual environment (works on macOS and Linux):",
        f"  {py} -m venv .venv",
        "  source .venv/bin/activate          # Windows: .venv\\Scripts\\activate",
        "  pip install duckdb xlrd",
        "  # then re-run this script with the venv active",
        "",
        "Alternative — install for this user only, no venv:",
        f"  {py} -m pip install --user duckdb xlrd",
        "",
        "Already using conda? With the environment active:",
        "  python -m pip install duckdb xlrd",
        "",
        "Note: `brew install duckdb` installs only the DuckDB *command-line tool*.",
        "These scripts import the DuckDB *Python module*, which is a separate install.",
    ]
    return "\n".join(lines)


def require(module: str, pip_name: str | None = None):
    """Import `module` or exit with tailored install guidance."""
    try:
        return __import__(module)
    except ImportError:
        pip_name = pip_name or module
        sys.stderr.write(
            f"\nERROR: the Python module '{module}' is not available to this interpreter.\n"
            f"       ({sys.executable})\n\n{pip_install_hint()}\n\n"
        )
        sys.exit(1)


if __name__ == "__main__":
    print(f"interpreter : {sys.executable}")
    print(f"version     : {sys.version.split()[0]}")
    print(f"virtualenv  : {in_virtualenv()}")
    print(f"platform    : {sysconfig.get_platform()}")
    print()
    for mod in ("duckdb", "xlrd"):
        try:
            m = __import__(mod)
            print(f"  {mod:8s} OK  {getattr(m, '__version__', '')}")
        except ImportError:
            print(f"  {mod:8s} MISSING")
    print()
    if not in_virtualenv():
        print("Install guidance for this interpreter:")
        print(pip_install_hint())
