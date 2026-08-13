"""Synchronous client for the acestep.cpp queued HTTP API."""

import json
import os
import re
import time
from typing import Any

import requests


class AceStepCppClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or os.getenv("ACESTEP_CPP_URL", "http://127.0.0.1:8085")).rstrip("/")
        self.timeout = int(os.getenv("ACESTEP_CPP_TIMEOUT", "1800"))
        self.poll_interval = float(os.getenv("ACESTEP_CPP_POLL_INTERVAL", "2"))
        self.lm_model = os.getenv("ACESTEP_CPP_LM_MODEL", "acestep-5Hz-lm-1.7B-Q8_0.gguf")
        self.synth_model = os.getenv("ACESTEP_CPP_SYNTH_MODEL", "acestep-v15-turbo-Q8_0.gguf")

    def health(self) -> dict[str, Any]:
        response = requests.get(f"{self.base_url}/health", timeout=5)
        response.raise_for_status()
        return response.json()

    def _submit(self, endpoint: str, payload: dict[str, Any]) -> str:
        response = requests.post(f"{self.base_url}{endpoint}", json=payload, timeout=30)
        response.raise_for_status()
        job_id = response.json().get("id")
        if not job_id:
            raise RuntimeError(f"acestep.cpp {endpoint} did not return a job id")
        return str(job_id)

    def _wait(self, job_id: str) -> None:
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            response = requests.get(f"{self.base_url}/job", params={"id": job_id}, timeout=15)
            response.raise_for_status()
            status = response.json().get("status")
            if status == "done":
                return
            if status in {"failed", "cancelled"}:
                raise RuntimeError(f"acestep.cpp job {job_id} {status}")
            time.sleep(self.poll_interval)
        requests.post(f"{self.base_url}/job", params={"id": job_id, "cancel": 1}, timeout=10)
        raise TimeoutError(f"acestep.cpp job {job_id} timed out")

    def _result(self, job_id: str) -> requests.Response:
        response = requests.get(
            f"{self.base_url}/job", params={"id": job_id, "result": 1}, timeout=120
        )
        response.raise_for_status()
        return response

    @staticmethod
    def _first_audio_part(response: requests.Response) -> bytes:
        content_type = response.headers.get("Content-Type", "")
        if "multipart/mixed" not in content_type:
            return response.content
        match = re.search(r"boundary=\"?([^\";]+)", content_type, re.IGNORECASE)
        if not match:
            raise RuntimeError("acestep.cpp multipart response has no boundary")
        delimiter = b"--" + match.group(1).encode()
        for chunk in response.content.split(delimiter):
            chunk = chunk.strip(b"\r\n")
            if not chunk or chunk == b"--":
                continue
            header_end = chunk.find(b"\r\n\r\n")
            if header_end < 0:
                continue
            headers = chunk[:header_end].decode("latin-1", errors="replace").lower()
            body = chunk[header_end + 4 :].rstrip(b"\r\n")
            if "content-type: audio/" in headers:
                return body
        raise RuntimeError("acestep.cpp response did not contain an audio part")

    def generate(
        self, *, caption: str, lyrics: str, duration: int, inference_steps: int,
        guidance_scale: float, vocal_language: str, bpm: int | None,
        keyscale: str | None, seed: int | None, instrumental: bool,
        synth_model: str | None = None,
    ) -> bytes:
        selected_synth_model = synth_model or self.synth_model
        allowed_synth_models = {
            "acestep-v15-turbo-Q4_K_M.gguf",
            "acestep-v15-turbo-Q8_0.gguf",
            "acestep-v15-xl-turbo-Q4_K_M.gguf",
        }
        if selected_synth_model not in allowed_synth_models:
            raise ValueError(f"Unsupported local ACE-Step model: {selected_synth_model}")
        payload: dict[str, Any] = {
            "caption": caption,
            "lyrics": "[Instrumental]" if instrumental else lyrics,
            "duration": 0 if duration == -1 else duration,
            "vocal_language": "unknown" if instrumental else vocal_language,
            "seed": -1 if seed is None else seed,
            "bpm": 0 if bpm is None else bpm,
            "keyscale": keyscale or "",
            "timesignature": "4",
            "lm_batch_size": 1,
            "synth_batch_size": 1,
            "lm_model": self.lm_model,
            "synth_model": selected_synth_model,
            "inference_steps": inference_steps,
            "guidance_scale": guidance_scale,
            "shift": 3.0,
            "output_format": "mp3",
        }
        lm_job = self._submit("/lm", payload)
        self._wait(lm_job)
        lm_response = self._result(lm_job)
        enriched = lm_response.json()
        if not isinstance(enriched, list) or not enriched:
            raise RuntimeError("acestep.cpp LM returned no enriched request")

        synth_job = self._submit("/synth", enriched[0])
        self._wait(synth_job)
        audio = self._first_audio_part(self._result(synth_job))
        if not audio:
            raise RuntimeError("acestep.cpp returned empty audio")
        return audio


acestep_cpp_client = AceStepCppClient()
