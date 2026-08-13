# Momo Song v4

English | [日本語](README.md)

Momo Song v4 is a web application that combines lyric generation, ACE-Step 1.5 music generation,
selectable backgrounds, and audio-reactive visuals.

![Momo Song GUI example](docs/images/gui-example.png)

## Features

- Lyrics and song descriptions using local Gemma 4 or an OpenAI-compatible API
- Music generation using local acestep.cpp or a remote ACE-Step 1.5 API
- Automatic, random, and manual background selection
- Visual effects driven by volume, waveform, and frequency data
- Continuous loop generation and click-to-stop playback
- Session-scoped 20-row song history with playback, deletion, and ZIP download
- Japanese and English GUI, saved in the browser

Local mode does not generate images and keeps the selected background. Remote mode can use a
configured image-generation API.

## Install

Python 3.10–3.12 is required. The installer downloads verified prebuilt packages from Momo Song v4
GitHub Releases.

```bash
# Linux, CUDA 12.5
./install.sh --backend cuda --cuda cu125
```

```powershell
# Windows PowerShell, CUDA 12.5
.\install.ps1 -Backend cuda -Cuda cu125
```

Use `--backend cpu` (`-Backend cpu` in PowerShell) for CPU installation. The installer creates
`.venv`. Model weights are not bundled or downloaded automatically.

- Official `llama-cpp-python` 0.3.34 wheels are wrapped in release ZIP archives.
- Source-build fallback is disabled when a compatible wheel is unavailable.
- Linux acestep.cpp archives are built from a pinned upstream source revision during release creation.
- The Linux CUDA archive is packaged from a tested build and uploaded to the release separately.
- Windows binaries are repackaged from the prebuilt distribution listed by upstream.
- Use `--acestep skip` or `-AceStep skip` if acestep.cpp is managed separately.
- Downloads are checked against SHA-256 files attached to the same release.
- Official wheel coverage is CPU/CUDA 12.1–12.5 on Linux and CPU/CUDA 12.4–12.5 on Windows.

> Dependency download works on Windows, but automatic local ACE server lifecycle management still
> relies on Linux tools (`ss`, `/proc`, and shell scripts). Fully automatic Local mode on Windows is
> not complete yet.

## Models

Place the local LLM at:

```text
models/gemma-4-E4B-it-Q4_K_M.gguf
```

Place ACE-Step models in `vendor/acestep.cpp/models/`. The GUI supports TURBO-Q4, TURBO-Q8, and
XL TURBO. TURBO-Q4 is the default. STRICT mode lowers VRAM use; actual requirements depend on the
GPU, driver, model, and song duration.

## Run

```bash
./start.sh
# or
.venv/bin/python music_server.py
```

Open <http://localhost:64653>. Choose **English** from the language selector in the header if it is
not selected automatically. The selection is stored in the browser.

Remote services are configured with `LLM_API_URL`, `ACE_STEP_API_URL`, and `IMAGE_API_URL`. See
[`.env.example`](.env.example) for defaults and [DEPLOYMENT.md](DEPLOYMENT.md) for deployment notes.

## License

Momo Song v4 is licensed under the [Apache License 2.0](LICENSE). Third-party libraries, binaries,
and model weights remain under their respective upstream licenses. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for redistributed components.
