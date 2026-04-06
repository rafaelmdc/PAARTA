from __future__ import annotations

import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CLI_ENV = {**os.environ}


def cli_command(name: str) -> list[str]:
    return [sys.executable, "-m", f"homorepeat.cli.{name}"]
