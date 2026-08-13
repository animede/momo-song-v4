#!/usr/bin/env python3
"""Install Momo Song dependencies from their original upstream distributors."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import urllib.request
import venv
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = ROOT / ".venv"
ACESTEP_DIR = ROOT / "vendor" / "acestep.cpp"
LLAMA_VERSION = "0.3.34"
LLAMA_INDEX_BASE = "https://abetlen.github.io/llama-cpp-python/whl"
ACESTEP_REPOSITORY = "https://github.com/ServeurpersoCom/acestep.cpp.git"
ACESTEP_WINDOWS_BASE = "https://www.serveurperso.com/temp/acestep.cpp-win64"
ACESTEP_WINDOWS_FILES = (
    "ace-lm.exe",
    "ace-server.exe",
    "ace-synth.exe",
    "ace-understand.exe",
    "ggml-base.dll",
    "ggml-cpu-alderlake.dll",
    "ggml-cpu-cannonlake.dll",
    "ggml-cpu-cascadelake.dll",
    "ggml-cpu-haswell.dll",
    "ggml-cpu-icelake.dll",
    "ggml-cpu-sandybridge.dll",
    "ggml-cpu-skylakex.dll",
    "ggml-cpu-sse42.dll",
    "ggml-cpu-x64.dll",
    "ggml-cuda.dll",
    "ggml-vulkan.dll",
    "ggml.dll",
    "mp3-codec.exe",
    "neural-codec.exe",
)


def run(command: list[str], *, cwd: Path | None = None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def venv_python() -> Path:
    return VENV_DIR / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def install_python(backend: str, cuda: str) -> None:
    if not VENV_DIR.exists():
        print(f"Creating virtual environment: {VENV_DIR}")
        venv.EnvBuilder(with_pip=True).create(VENV_DIR)
    python = str(venv_python())
    run([python, "-m", "pip", "install", "--upgrade", "pip"])
    run([python, "-m", "pip", "install", "--only-binary=:all:", "-r", str(ROOT / "requirements.txt")])
    wheel_index = f"{LLAMA_INDEX_BASE}/{'cpu' if backend == 'cpu' else cuda}"
    run([
        python, "-m", "pip", "install", "--only-binary=:all:",
        f"llama-cpp-python=={LLAMA_VERSION}", "--extra-index-url", wheel_index,
    ])
    record_source("llama-cpp-python", {"version": LLAMA_VERSION, "index": wheel_index})


def download(url: str, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    temporary = destination.with_suffix(destination.suffix + ".part")
    print(f"Downloading {url}")
    with urllib.request.urlopen(url) as response, temporary.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
            digest.update(chunk)
    temporary.replace(destination)
    return digest.hexdigest()


def record_source(name: str, details: dict[str, object]) -> None:
    record_dir = ROOT / "vendor" / ".sources"
    record_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "component": name,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        **details,
    }
    (record_dir / f"{name}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def install_acestep_windows() -> None:
    release_dir = ACESTEP_DIR / "build" / "Release"
    hashes: dict[str, str] = {}
    for filename in ACESTEP_WINDOWS_FILES:
        url = f"{ACESTEP_WINDOWS_BASE}/build/Release/{filename}"
        hashes[filename] = download(url, release_dir / filename)
    server_url = f"{ACESTEP_WINDOWS_BASE}/server.cmd"
    hashes["server.cmd"] = download(server_url, ACESTEP_DIR / "server.cmd")
    record_source("acestep.cpp", {
        "distribution": "upstream Windows prebuilt directory",
        "base_url": ACESTEP_WINDOWS_BASE,
        "sha256": hashes,
    })


def install_acestep_source(backend: str) -> None:
    if platform.system() == "Windows":
        raise SystemExit("Windowsでは --acestep prebuilt を使用してください。")
    if not ACESTEP_DIR.exists():
        ACESTEP_DIR.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--depth", "1", "--recurse-submodules", ACESTEP_REPOSITORY, str(ACESTEP_DIR)])
    elif not (ACESTEP_DIR / ".git").exists():
        raise SystemExit(f"既存の {ACESTEP_DIR} はGit作業ツリーではありません。")
    run(["git", "submodule", "update", "--init", "--recursive"], cwd=ACESTEP_DIR)
    build_dir = ACESTEP_DIR / ("build-cpu" if backend == "cpu" else "build")
    options = ["-DGGML_CUDA=OFF", "-DGGML_NATIVE=ON"] if backend == "cpu" else ["-DGGML_CUDA=ON"]
    run(["cmake", "-S", str(ACESTEP_DIR), "-B", str(build_dir), "-DCMAKE_BUILD_TYPE=Release", *options])
    jobs = str(os.cpu_count() or 1)
    run(["cmake", "--build", str(build_dir), "--config", "Release", "-j", jobs])
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ACESTEP_DIR, text=True).strip()
    record_source("acestep.cpp", {"distribution": "upstream source build", "repository": ACESTEP_REPOSITORY, "revision": revision})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--cuda", choices=("cu121", "cu122", "cu123", "cu124", "cu125"), default="cu125")
    parser.add_argument("--acestep", choices=("auto", "prebuilt", "source", "skip"), default="auto")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if sys.version_info < (3, 10) or sys.version_info >= (3, 13):
        raise SystemExit("Python 3.10〜3.12を使用してください。")
    install_python(args.backend, args.cuda)
    mode = args.acestep
    if mode == "auto":
        mode = "prebuilt" if platform.system() == "Windows" else "source"
    if mode == "prebuilt":
        if platform.system() != "Windows":
            raise SystemExit("上流のビルド済みacestep.cppは現在Windows版のみです。Linuxでは --acestep source を指定してください。")
        install_acestep_windows()
    elif mode == "source":
        install_acestep_source(args.backend)
    print("\nInstallation complete. Model weights are not bundled; see README.md for model paths.")


if __name__ == "__main__":
    main()
