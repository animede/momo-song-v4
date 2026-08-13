#!/usr/bin/env python3
"""Install Momo Song dependencies from Momo Song GitHub Releases."""

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
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = ROOT / ".venv"
ACESTEP_DIR = ROOT / "vendor" / "acestep.cpp"
LLAMA_VERSION = "0.3.34"
RELEASE_REPOSITORY = os.getenv("MOMO_RELEASE_REPOSITORY", "animede/momo-song-v4")
RELEASE_TAG = os.getenv("MOMO_RELEASE_TAG", "latest")
RELEASE_BASE = f"https://github.com/{RELEASE_REPOSITORY}/releases"
_resolved_release_tag: str | None = None
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
    accelerator = "cpu" if backend == "cpu" else cuda
    system = "windows" if os.name == "nt" else "linux"
    if system == "windows" and accelerator not in {"cpu", "cu124", "cu125"}:
        raise SystemExit("Windows用公式ホイールはCPU、CUDA 12.4、CUDA 12.5に対応しています。")
    asset = f"llama-cpp-python-{LLAMA_VERSION}-{accelerator}-{system}-x86_64.zip"
    archive = ROOT / "vendor" / ".downloads" / asset
    source_url, digest = download_release_asset(asset, archive)
    wheel_dir = archive.parent / asset.removesuffix(".zip")
    wheel_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        wheels = [name for name in bundle.namelist() if name.endswith(".whl")]
        if len(wheels) != 1:
            raise RuntimeError(f"Expected one wheel in {asset}, found {len(wheels)}")
        bundle.extract(wheels[0], wheel_dir)
    run([python, "-m", "pip", "install", "--only-binary=:all:", str(wheel_dir / wheels[0])])
    record_source("llama-cpp-python", {
        "version": LLAMA_VERSION, "release_asset": source_url, "sha256": digest,
    })


def release_asset_url(asset: str) -> str:
    global _resolved_release_tag
    if RELEASE_TAG != "latest":
        tag = RELEASE_TAG
    else:
        if _resolved_release_tag is None:
            request = urllib.request.Request(
                f"https://api.github.com/repos/{RELEASE_REPOSITORY}/releases?per_page=20",
                headers={"Accept": "application/vnd.github+json", "User-Agent": "momo-song-installer"},
            )
            with urllib.request.urlopen(request) as response:
                releases = json.load(response)
            published = [item for item in releases if not item.get("draft")]
            if not published:
                raise RuntimeError(f"No published release found for {RELEASE_REPOSITORY}")
            _resolved_release_tag = published[0]["tag_name"]
        tag = _resolved_release_tag
    return f"{RELEASE_BASE}/download/{tag}/{asset}"


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


def download_release_asset(asset: str, destination: Path) -> tuple[str, str]:
    url = release_asset_url(asset)
    digest = download(url, destination)
    with urllib.request.urlopen(release_asset_url(f"{asset}.sha256")) as response:
        expected = response.read().decode().split()[0].lower()
    if digest.lower() != expected:
        destination.unlink(missing_ok=True)
        raise RuntimeError(f"SHA-256 mismatch for {asset}")
    return url, digest


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
    asset = "acestep.cpp-windows-x86_64-cuda.zip"
    archive = ROOT / "vendor" / ".downloads" / asset
    source_url, digest = download_release_asset(asset, archive)
    ACESTEP_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(ACESTEP_DIR)
    record_source("acestep.cpp", {
        "distribution": "Momo Song GitHub Release",
        "release_asset": source_url, "sha256": digest,
    })


def install_acestep_linux(backend: str) -> None:
    asset = f"acestep.cpp-linux-x86_64-{backend}.tar.gz"
    archive = ROOT / "vendor" / ".downloads" / asset
    source_url, digest = download_release_asset(asset, archive)
    ACESTEP_DIR.mkdir(parents=True, exist_ok=True)
    run(["tar", "-xzf", str(archive), "-C", str(ACESTEP_DIR)])
    record_source("acestep.cpp", {
        "distribution": "Momo Song GitHub Release",
        "release_asset": source_url, "sha256": digest,
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
        mode = "prebuilt"
    if mode == "prebuilt":
        if platform.machine().lower() not in {"x86_64", "amd64"}:
            raise SystemExit("ビルド済み配布はx86-64専用です。--acestep sourceを指定してください。")
        if platform.system() == "Windows":
            install_acestep_windows()
        elif platform.system() == "Linux":
            install_acestep_linux(args.backend)
        else:
            raise SystemExit("ビルド済みacestep.cppはLinux/Windows x86-64用です。")
    elif mode == "source":
        install_acestep_source(args.backend)
    print("\nInstallation complete. Model weights are not bundled; see README.md for model paths.")


if __name__ == "__main__":
    main()
