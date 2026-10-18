# Adapted from ningzimu/codex-ppt-skill scripts/image_providers (MIT License).
from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
from pathlib import Path
import sys
import time
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen as default_urlopen

from .base import ImageProvider


UrlOpen = Callable[..., Any]
USER_AGENT = "patent-disclosure-skill (+https://github.com/handsomestWei/patent-disclosure-skill)"


class AtlasCloudImageProvider(ImageProvider):
    _FINISHED_STATUSES = {"completed", "succeeded"}
    _FAILED_STATUSES = {"failed"}

    def __init__(
        self,
        *,
        api_key: Optional[str],
        base_url: Optional[str],
        urlopen: UrlOpen = default_urlopen,
        sleep: Callable[[float], None] = time.sleep,
        poll_interval: float = 2.0,
        max_polls: int = 120,
    ) -> None:
        self.api_key = api_key
        self.model_base_url = _model_base_url(base_url)
        self._urlopen = urlopen
        self._sleep = sleep
        self.poll_interval = poll_interval
        self.max_polls = max_polls

    def generate(self, payload: Dict[str, Any]) -> List[str]:
        count = int(payload.get("n", 1))
        outputs: List[str] = []
        for _ in range(count):
            outputs.extend(self._submit_and_collect(payload, operation="text-to-image"))
        return outputs

    def edit(
        self,
        payload: Dict[str, Any],
        image_paths: List[Path],
        mask_path: Optional[Path],
    ) -> List[str]:
        if mask_path is not None:
            raise ValueError("AtlasCloud image edit does not support --mask.")

        count = int(payload.get("n", 1))
        edit_payload = dict(payload)
        edit_payload["images"] = [_image_to_data_url(path) for path in image_paths]
        outputs: List[str] = []
        for _ in range(count):
            outputs.extend(self._submit_and_collect(edit_payload, operation="edit"))
        return outputs

    async def generate_batch(
        self,
        payload: Dict[str, Any],
        *,
        attempts: int,
        job_label: str,
    ) -> List[str]:
        last_exc: Optional[Exception] = None
        for attempt in range(1, attempts + 1):
            try:
                return await asyncio.to_thread(self.generate, payload)
            except Exception as exc:
                last_exc = exc
                if attempt == attempts:
                    raise
                sleep_s = min(60.0, 2.0**attempt)
                print(
                    f"{job_label} attempt {attempt}/{attempts} failed ({exc.__class__.__name__}); retrying in {sleep_s:.1f}s",
                    file=sys.stderr,
                )
                await asyncio.sleep(sleep_s)
        raise last_exc or RuntimeError("unknown error")

    def _submit_and_collect(self, payload: Dict[str, Any], *, operation: str) -> List[str]:
        request_payload = self._atlas_payload(payload, operation=operation)
        submitted = self._request_json(
            "POST",
            f"{self.model_base_url}/generateImage",
            request_payload,
        )
        prediction_id = _prediction_id(submitted)
        if not prediction_id:
            raise RuntimeError("AtlasCloud response did not include a prediction id.")

        result_url = _prediction_result_url(submitted) or f"{self.model_base_url}/result/{prediction_id}"
        result = self._poll_prediction(result_url)
        outputs = result.get("outputs")
        if not isinstance(outputs, list) or not outputs:
            raise RuntimeError("AtlasCloud prediction completed without outputs.")
        return [self._output_to_b64(str(output)) for output in outputs]

    def _poll_prediction(self, url: str) -> Dict[str, Any]:
        last: Dict[str, Any] = {}
        for _ in range(self.max_polls):
            last = self._request_json("GET", url)
            status = str(last.get("status", "")).lower()
            if status in self._FINISHED_STATUSES:
                return last
            if status in self._FAILED_STATUSES:
                raise RuntimeError(f"AtlasCloud prediction failed: {last}")
            self._sleep(self.poll_interval)
        raise TimeoutError(f"AtlasCloud prediction timed out: {last}")

    def _atlas_payload(self, payload: Dict[str, Any], *, operation: str) -> Dict[str, Any]:
        output_format = payload.get("output_format")
        if output_format not in (None, "png", "jpeg"):
            raise ValueError("AtlasCloud supports output_format png or jpeg.")

        body: Dict[str, Any] = {
            "model": atlascloud_model_for_operation(
                str(payload.get("model", "gpt-image-2")),
                operation,
            ),
            "prompt": payload["prompt"],
            "enable_sync_mode": False,
            "enable_base64_output": True,
        }
        for key in ("size", "quality", "output_format"):
            value = payload.get(key)
            if value is not None and value != "auto":
                body[key] = value
        if operation == "edit":
            body["images"] = payload["images"]
        return body

    def _request_json(
        self,
        method: str,
        url: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        if payload is not None:
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=headers, method=method)
        with self._urlopen(request, timeout=60) as response:
            parsed = json.loads(response.read().decode("utf-8"))
        if not isinstance(parsed, dict):
            raise RuntimeError(f"Unexpected AtlasCloud response: {parsed}")
        code = parsed.get("code")
        if code is not None and code not in (0, 200, "0", "200"):
            raise RuntimeError(f"AtlasCloud API error: {parsed}")
        data_obj = parsed.get("data", parsed)
        if not isinstance(data_obj, dict):
            raise RuntimeError(f"Unexpected AtlasCloud response data: {parsed}")
        return data_obj

    def _output_to_b64(self, value: str) -> str:
        if value.startswith("data:") and "," in value:
            return value.split(",", 1)[1]
        parsed = urlparse(value)
        if parsed.scheme in {"http", "https"}:
            request = Request(value, headers={"User-Agent": USER_AGENT}, method="GET")
            with self._urlopen(request, timeout=60) as response:
                return base64.b64encode(response.read()).decode("ascii")
        return value


def _model_base_url(base_url: Optional[str]) -> str:
    if not base_url:
        return "https://api.atlascloud.ai/api/v1/model"
    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
    path = parsed.path.rstrip("/")
    marker = "/api/v1/model"
    if marker in path:
        prefix = path[: path.index(marker) + len(marker)]
        return f"{origin}{prefix}"
    if origin:
        return f"{origin}{marker}"
    return base_url.rstrip("/")


def atlascloud_model_for_operation(model: str, operation: str) -> str:
    suffix = "edit" if operation == "edit" else "text-to-image"
    base = model.rstrip("/")
    for existing_suffix in ("/text-to-image", "/edit"):
        if base.endswith(existing_suffix):
            base = base[: -len(existing_suffix)]
            break
    if "/" not in base:
        base = f"openai/{base}"
    return f"{base}/{suffix}"


def _prediction_id(data: Dict[str, Any]) -> Optional[str]:
    value = data.get("id") or data.get("prediction_id")
    return str(value) if value else None


def _prediction_result_url(data: Dict[str, Any]) -> Optional[str]:
    urls = data.get("urls")
    if not isinstance(urls, dict):
        return None
    value = urls.get("get")
    return str(value) if value else None


def _image_to_data_url(path: Path) -> str:
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"
