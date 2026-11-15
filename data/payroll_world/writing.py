"""Writes the generator's files the same, byte for byte, on every run and on every
machine: UTF-8, with \\n line endings, in the order the generator gives."""

import json
import textwrap
from pathlib import Path
from typing import Any

import yaml

GENERATED = "Written by data/generate.py (npm run generate). Don't edit it by hand."


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_json(path: Path, data: Any) -> None:
    write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def write_yaml(path: Path, about: str, data: dict[str, Any]) -> None:
    """A YAML file, headed by what it holds and how it's made."""
    lines = textwrap.wrap(about, 86) + [GENERATED]
    header = "".join(f"# {line}\n" for line in lines)
    body = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)
    write_text(path, f"{header}\n{body}")
