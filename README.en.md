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

Python 3.10–3.12 is required. Dependencies are downloaded directly from their original upstream
distributors and are not re-hosted by this repository.

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

- `llama-cpp-python` 0.3.34 comes from abetlen's official wheel index.
- Source-build fallback is disabled when a compatible wheel is unavailable.
- Windows acestep.cpp binaries come directly from the prebuilt location listed upstream.
- Since upstream does not publish Linux binaries, Linux builds the official source locally.
- Use `--acestep skip` or `-AceStep skip` if acestep.cpp is managed separately.

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
and model weights remain under their respective upstream licenses.
