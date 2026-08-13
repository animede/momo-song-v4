#!/usr/bin/env python3
"""Package the Windows binaries published by the acestep.cpp project."""

from __future__ import annotations

import urllib.request
import zipfile
from pathlib import Path


BASE = "https://www.serveurperso.com/temp/acestep.cpp-win64"
FILES = (
    "ace-lm.exe", "ace-server.exe", "ace-synth.exe", "ace-understand.exe",
    "ggml-base.dll", "ggml-cpu-alderlake.dll", "ggml-cpu-cannonlake.dll",
    "ggml-cpu-cascadelake.dll", "ggml-cpu-haswell.dll", "ggml-cpu-icelake.dll",
    "ggml-cpu-sandybridge.dll", "ggml-cpu-skylakex.dll", "ggml-cpu-sse42.dll",
    "ggml-cpu-x64.dll", "ggml-cuda.dll", "ggml-vulkan.dll", "ggml.dll",
    "mp3-codec.exe", "neural-codec.exe",
)


def main() -> None:
    output = Path("acestep.cpp-windows-x86_64-cuda.zip")
    staging = Path("acestep-windows")
    release = staging / "build" / "Release"
    release.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        urllib.request.urlretrieve(f"{BASE}/build/Release/{name}", release / name)
    urllib.request.urlretrieve(f"{BASE}/server.cmd", staging / "server.cmd")
    urllib.request.urlretrieve(
        "https://raw.githubusercontent.com/ServeurpersoCom/acestep.cpp/master/LICENSE",
        staging / "LICENSE.acestep.cpp",
    )
    (staging / "SOURCE.txt").write_text(f"Binary source: {BASE}\n", encoding="utf-8")
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in staging.rglob("*"):
            if path.is_file():
                bundle.write(path, path.relative_to(staging))


if __name__ == "__main__":
    main()
