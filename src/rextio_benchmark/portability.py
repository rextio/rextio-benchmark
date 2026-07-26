from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def portable_string(value: str, repository_root: Path, home: Path | None = None) -> str:
    root = repository_root.resolve()
    user_home = (home or Path.home()).resolve()
    candidate = Path(value)
    if candidate.is_absolute():
        try:
            relative = candidate.resolve().relative_to(root)
            return relative.as_posix() or "."
        except ValueError:
            pass
        try:
            relative = candidate.resolve().relative_to(user_home)
            return f"<home>/{relative.as_posix()}" if relative.parts else "<home>"
        except ValueError:
            pass
    result = value.replace(str(root), "<repository>")
    return result.replace(str(user_home), "<home>")


def portable_value(value: Any, repository_root: Path, home: Path | None = None) -> Any:
    if isinstance(value, str):
        return portable_string(value, repository_root, home)
    if isinstance(value, list):
        return [portable_value(item, repository_root, home) for item in value]
    if isinstance(value, tuple):
        return [portable_value(item, repository_root, home) for item in value]
    if isinstance(value, dict):
        return {
            str(key): portable_value(item, repository_root, home)
            for key, item in value.items()
        }
    return value


def require_portable(value: Any, repository_root: Path, home: Path | None = None) -> None:
    serialized = json.dumps(value, sort_keys=True)
    for forbidden in (str(repository_root.resolve()), str((home or Path.home()).resolve())):
        if forbidden and forbidden in serialized:
            raise ValueError(f"payload contains a private absolute path: {forbidden}")


def write_portable_snapshot(
    destination: Path,
    value: Any,
    repository_root: Path,
    home: Path | None = None,
) -> Any:
    portable = portable_value(value, repository_root, home)
    require_portable(portable, repository_root, home)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(portable, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return portable
