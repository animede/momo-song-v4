# Third-party binary notices

Momo Song release assets may redistribute the following unmodified or compiled components:

- **llama-cpp-python**, copyright Andrei Betlen and contributors, MIT License.
  Source: <https://github.com/abetlen/llama-cpp-python>
- **llama.cpp / ggml**, copyright Georgi Gerganov and contributors, MIT License.
  Source: <https://github.com/ggml-org/llama.cpp>
- **acestep.cpp**, copyright its contributors, MIT License.
  Source: <https://github.com/ServeurpersoCom/acestep.cpp>

Each binary archive produced by the release workflow must contain its applicable upstream license,
source URL, and exact source revision or upstream wheel URL. Model weights are not redistributed.

The Linux CUDA acestep.cpp archive is built on a repository-owned GitHub Actions runner labeled
`self-hosted`, `Linux`, `X64`, and `cuda`. This runner is not required by end users.
