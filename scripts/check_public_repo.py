#!/usr/bin/env python3
"""Fail when common secrets, personal paths, or release artifacts are tracked."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    "", ".css", ".html", ".ini", ".js", ".json", ".md", ".py", ".sh",
    ".toml", ".txt", ".yaml", ".yml",
}
FORBIDDEN_TRACKED_PARTS = {"venv", ".venv", "__pycache__", "runtime", "logs", "vendor"}
PATTERNS = {
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "likely API token": re.compile(r"\b(?:sk|ghp|github_pat)_[A-Za-z0-9_-]{16,}\b"),
    "personal Unix home": re.compile(r"/home/(?!user(?:/|\b))[^/\s]+/"),
    "personal Windows home": re.compile(r"[A-Za-z]:\\Users\\(?!Public\\)[^\\\s]+\\", re.I),
    "public IPv4 literal": re.compile(
        r"\b(?!(?:0|10|127)\.)(?!192\.168\.)(?!172\.(?:1[6-9]|2\d|3[01])\.)"
        r"(?:\d{1,3}\.){3}\d{1,3}\b"
    ),
}


def repository_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [ROOT / value.decode() for value in result.stdout.split(b"\0") if value]


def main() -> int:
    failures: list[str] = []
    for path in repository_files():
        relative = path.relative_to(ROOT)
        if FORBIDDEN_TRACKED_PARTS.intersection(relative.parts):
            failures.append(f"tracked local artifact: {relative}")
        if path.suffix.lower() in {".gguf", ".safetensors", ".pfx", ".p12", ".key"}:
            failures.append(f"tracked model or credential file: {relative}")
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if relative == Path("scripts/check_public_repo.py"):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in PATTERNS.items():
            for match in pattern.finditer(content):
                line = content.count("\n", 0, match.start()) + 1
                failures.append(f"{label}: {relative}:{line}")

    if failures:
        print("Public repository check failed:", file=sys.stderr)
        print("\n".join(f"- {failure}" for failure in failures), file=sys.stderr)
        return 1
    print("Public repository check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
