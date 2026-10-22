"""Vision-language model provider abstraction.

Two providers are implemented (per the chosen design: Claude Opus 4.8 as primary,
OpenAI GPT vision as the second model for inter-model agreement). Both expose the
same ``complete_json`` interface: given a system prompt, an ordered list of images
(file paths and/or URLs), and a text block, return a parsed-and-validated JSON
object conforming to ``codebook/schema.json``.

SDKs are imported lazily so the module can be inspected without the providers
installed. Each call uses temperature 0 and validates output against the schema,
retrying once with an explicit "fix your JSON" nudge on failure.
"""

from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import Any

try:
    import jsonschema
except Exception:  # pragma: no cover - optional at inspection time
    jsonschema = None


def _b64_image(path: str | Path) -> tuple[str, str]:
    """Return (media_type, base64_data) for a local image file."""
    p = Path(path)
    media_type = mimetypes.guess_type(p.name)[0] or "image/jpeg"
    data = base64.b64encode(p.read_bytes()).decode("ascii")
    return media_type, data


def _image_bytes(img: str | Path) -> tuple[str, bytes]:
    """Return (media_type, raw_bytes) for a local path or an http(s) URL."""
    s = str(img)
    if s.startswith("http"):
        import urllib.request
        with urllib.request.urlopen(s, timeout=30) as r:  # noqa: S310 - trusted YouTube CDN
            data = r.read()
        media_type = "image/jpeg"
        if s.lower().endswith(".png"):
            media_type = "image/png"
        return media_type, data
    p = Path(img)
    media_type = mimetypes.guess_type(p.name)[0] or "image/jpeg"
    return media_type, p.read_bytes()


def is_session_provider(provider: str) -> bool:
    """Providers ending in '_session' are coded in-session by Claude Code
    (using the user's subscription) rather than via a billed API."""
    return provider.lower().endswith("_session")


def validate(obj: dict, schema: dict) -> list[str]:
    """Return a list of validation error messages ([] if valid)."""
    if jsonschema is None:
        # Minimal fallback: check required keys only.
        missing = [k for k in schema.get("required", []) if k not in obj]
        return [f"missing required field: {k}" for k in missing]
    validator = jsonschema.Draft7Validator(schema)
    return [e.message for e in validator.iter_errors(obj)]


def _extract_json(text: str) -> dict:
    """Parse the first JSON object found in a text blob."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object in model output: {text[:200]}")
    return json.loads(text[start:end + 1])


class VLMClient:
    provider = "base"

    def __init__(self, model: str, temperature: float, api_key: str):
        self.model = model
        self.temperature = temperature
        self.api_key = api_key

    @property
    def name(self) -> str:
        return f"{self.provider}:{self.model}"

    def _raw_complete(self, system: str, images: list[str], text: str) -> str:
        raise NotImplementedError

    def complete_json(self, system: str, images: list[str], text: str,
                      schema: dict, max_retries: int = 1) -> dict:
        prompt_text = text
        last_err = None
        for attempt in range(max_retries + 1):
            raw = self._raw_complete(system, images, prompt_text)
            try:
                obj = _extract_json(raw)
            except ValueError as e:
                last_err = str(e)
                prompt_text = text + f"\n\nYour previous reply was not valid JSON ({e}). Return ONLY the JSON object."
                continue
            errs = validate(obj, schema)
            if not errs:
                return obj
            last_err = "; ".join(errs[:5])
            prompt_text = text + f"\n\nYour previous JSON failed schema validation: {last_err}. Fix and return ONLY the JSON object."
        raise RuntimeError(f"{self.name} failed schema validation: {last_err}")


class AnthropicVLM(VLMClient):
    provider = "anthropic"

    def _client(self):
        import anthropic
        return anthropic.Anthropic(api_key=self.api_key)

    def _raw_complete(self, system: str, images: list[str], text: str) -> str:
        content: list[dict[str, Any]] = []
        for img in images:
            if str(img).startswith("http"):
                content.append({"type": "image",
                                "source": {"type": "url", "url": img}})
            else:
                media_type, data = _b64_image(img)
                content.append({"type": "image", "source": {
                    "type": "base64", "media_type": media_type, "data": data}})
        content.append({"type": "text", "text": text})
        resp = self._client().messages.create(
            model=self.model,
            max_tokens=3000,
            temperature=self.temperature,
            system=system,
            messages=[{"role": "user", "content": content}],
        )
        return "".join(block.text for block in resp.content
                       if getattr(block, "type", None) == "text")


class OpenAIVLM(VLMClient):
    provider = "openai"

    def _client(self):
        import openai
        return openai.OpenAI(api_key=self.api_key)

    def _raw_complete(self, system: str, images: list[str], text: str) -> str:
        parts: list[dict[str, Any]] = [{"type": "text", "text": text}]
        for img in images:
            if str(img).startswith("http"):
                url = img
            else:
                media_type, data = _b64_image(img)
                url = f"data:{media_type};base64,{data}"
            parts.append({"type": "image_url", "image_url": {"url": url}})
        resp = self._client().chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=3000,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": parts},
            ],
        )
        return resp.choices[0].message.content or ""


class GeminiVLM(VLMClient):
    provider = "google"

    def _model(self, system: str):
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        return genai.GenerativeModel(self.model, system_instruction=system)

    def _raw_complete(self, system: str, images: list[str], text: str) -> str:
        import time

        parts: list = [text]
        for img in images:
            mime, data = _image_bytes(img)
            parts.append({"mime_type": mime, "data": data})
        model = self._model(system)
        # Free-tier rate limits (429/ResourceExhausted) are expected; back off and
        # retry rather than losing the coding row.
        last = None
        for attempt in range(6):
            try:
                resp = model.generate_content(
                    parts,
                    generation_config={"temperature": self.temperature,
                                       "response_mime_type": "application/json",
                                       "max_output_tokens": 3000},
                )
                return resp.text or ""
            except Exception as e:  # noqa: BLE001 - includes ResourceExhausted
                last = e
                msg = str(e).lower()
                if any(s in msg for s in ("429", "resourceexhausted", "rate", "quota", "exhausted")):
                    time.sleep(min(60, 5 * (attempt + 1)))
                    continue
                raise
        raise RuntimeError(f"Gemini ret/rate-limit exhausted: {last}")


class CodexCLIVLM(VLMClient):
    """GPT via the Codex CLI in headless mode (``codex exec``), authenticated by
    the user's ChatGPT OAuth login (Plus subscription — $0 marginal cost).

    Notes for provenance: temperature is NOT configurable through the Codex CLI;
    the model is pinned via ``-m`` and reasoning effort forced to "medium" so
    coding calls don't burn the Plus quota at the config default ("ultra").
    Quota-window exhaustion surfaces as a raised error whose message mentions
    the limit — the resumable coding/screening loops fast-fail on a streak of
    these and pick up after the window renews."""

    provider = "codex_cli"

    QUOTA_MARKERS = ("rate limit", "usage limit", "quota", "too many requests",
                     "429", "plan limit")

    def _raw_complete(self, system: str, images: list[str], text: str) -> str:
        import os
        import subprocess
        import tempfile
        import urllib.request

        with tempfile.TemporaryDirectory() as td:
            out_file = os.path.join(td, "last_message.txt")
            cmd = ["codex", "exec", "--skip-git-repo-check",
                   "-s", "read-only", "-o", out_file,
                   "-c", 'model_reasoning_effort="medium"']
            if self.model and self.model not in ("default", ""):
                cmd += ["-m", self.model]
            for idx, img in enumerate(images):
                s = str(img)
                if s.startswith("http"):  # e.g. thumbnails — fetch locally first
                    local = os.path.join(td, f"img_{idx}.jpg")
                    urllib.request.urlretrieve(s, local)  # noqa: S310 - YouTube CDN
                    s = local
                cmd += ["-i", s]
            # The variadic -i flag swallows a trailing positional prompt, so the
            # prompt goes in via stdin ("-" mode) instead.
            cmd.append("-")
            res = subprocess.run(cmd, input=system + "\n\n" + text,
                                 capture_output=True, text=True, timeout=900)
            if os.path.exists(out_file):
                msg = open(out_file, encoding="utf-8").read().strip()
                if msg:
                    return msg
            err = (res.stderr or res.stdout or "").strip()
            raise RuntimeError(f"codex exec failed (rc={res.returncode}): {err[-400:]}")


def is_quota_error(err: str) -> bool:
    """Heuristic: does an error message indicate a rate/usage-window limit?"""
    low = str(err).lower()
    return any(m in low for m in CodexCLIVLM.QUOTA_MARKERS)


def make_client(provider: str, model: str, temperature: float, secrets: dict) -> VLMClient:
    provider = provider.lower()
    if is_session_provider(provider):
        raise NotImplementedError(
            f"Provider '{provider}' is coded in-session by Claude Code, not via API. "
            f"The automated pipeline skips it; see session_coding.py.")
    if provider == "anthropic":
        return AnthropicVLM(model, temperature, secrets.get("anthropic_api_key", ""))
    if provider == "openai":
        return OpenAIVLM(model, temperature, secrets.get("openai_api_key", ""))
    if provider in ("google", "gemini"):
        return GeminiVLM(model, temperature, secrets.get("google_api_key", ""))
    if provider in ("codex", "codex_cli"):
        return CodexCLIVLM(model, temperature, "")  # auth = ChatGPT OAuth login
    raise ValueError(f"Unsupported provider: {provider}")
