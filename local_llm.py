"""Lazy local Gemma 4 text-completion backend using llama-cpp-python."""

import asyncio
import gc
import os
import threading
from pathlib import Path


MODEL_PATH = Path(os.getenv(
    "LOCAL_LLM_MODEL",
    str(Path(__file__).resolve().parent / "models" / "gemma-4-E4B-it-Q4_K_M.gguf"),
))
_model = None
_model_lock = threading.Lock()
_completion_lock = threading.Lock()


def _get_model():
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is None:
            if not MODEL_PATH.is_file():
                raise FileNotFoundError(f"ローカルLLMモデルがありません: {MODEL_PATH}")
            try:
                from llama_cpp import Llama, LLAMA_SPLIT_MODE_NONE
            except ImportError as error:
                raise RuntimeError(
                    "llama-cpp-pythonが未導入です。requirements.txtを再インストールしてください"
                ) from error
            _model = Llama(
                model_path=str(MODEL_PATH),
                n_ctx=int(os.getenv("LOCAL_LLM_N_CTX", "8192")),
                n_threads=int(os.getenv("LOCAL_LLM_THREADS", str(max(1, (os.cpu_count() or 4) // 2)))),
                n_gpu_layers=int(os.getenv("LOCAL_LLM_GPU_LAYERS", "-1")),
                main_gpu=int(os.getenv("LOCAL_LLM_MAIN_GPU", "0")),
                split_mode=LLAMA_SPLIT_MODE_NONE,
                flash_attn=os.getenv("LOCAL_LLM_FLASH_ATTN", "1") == "1",
                verbose=os.getenv("LOCAL_LLM_VERBOSE", "0") == "1",
            )
    return _model


def _complete(prompt: str) -> str:
    # High-level text completion API. Gemmaのturn tokenはプロンプト側で与える。
    formatted = (
        "<start_of_turn>user\n"
        "あなたは賢いAIです。要求に正確に従ってください。\n"
        f"{prompt}<end_of_turn>\n<start_of_turn>model\n"
    )
    with _completion_lock:
        output = _get_model().create_completion(
            prompt=formatted,
            max_tokens=int(os.getenv("LOCAL_LLM_MAX_TOKENS", "2048")),
            temperature=float(os.getenv("LOCAL_LLM_TEMPERATURE", "0.7")),
            top_p=0.9,
            repeat_penalty=1.05,
            stop=["<end_of_turn>", "<eos>"],
            echo=False,
        )
    choices = output.get("choices", [])
    if not choices or not choices[0].get("text", "").strip():
        raise RuntimeError("ローカルGemmaが空の応答を返しました")
    return choices[0]["text"].strip()


async def local_completion(prompt: str) -> str:
    return await asyncio.to_thread(_complete, prompt)


def release_local_model() -> None:
    """Release Gemma and its CUDA buffers before ACE-Step starts."""
    global _model
    with _completion_lock:
        with _model_lock:
            model, _model = _model, None
            if model is not None:
                model.close()
                del model
    gc.collect()


async def release_local_model_async() -> None:
    await asyncio.to_thread(release_local_model)
