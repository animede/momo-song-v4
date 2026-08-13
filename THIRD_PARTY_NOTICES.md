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

The Linux CUDA acestep.cpp archive is packaged from a tested local build with
`scripts/package_local_acestep_cuda.sh`. Its `SOURCE.txt` records the exact upstream revision.
This avoids requiring an always-online self-hosted GitHub Actions runner.
