# Adapted from ningzimu/codex-ppt-skill scripts/image_providers (MIT License).
from __future__ import annotations

import asyncio
from pathlib import Path
import re
import sys
from typing import Any, Callable, Dict, List, Optional

from .base import ImageProvider


ClientFactory = Callable[[], Any]


def _dependency_hint(package: str, *, upgrade: bool = False) -> str:
    package_arg = f"-U {package}" if upgrade else package
    requirements = Path(__file__).resolve().parents[1] / "requirements-image.txt"
    return (
        "征得用户同意后安装出图依赖："
        f"`python -m pip install -r {requirements}`，或单装 `python -m pip install {package_arg}`。"
    )


def _extract_retry_after_seconds(exc: Exception) -> Optional[float]:
    for attr in ("retry_after", "retry_after_seconds"):
        val = getattr(exc, attr, None)
        if isinstance(val, (int, float)) and val >= 0:
            return float(val)
    msg = str(exc)
    m = re.search(r"retry[- ]after[:= ]+([0-9]+(?:\\.[0-9]+)?)", msg, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            return None
    return None


def _is_rate_limit_error(exc: Exception) -> bool:
    name = exc.__class__.__name__.lower()
    if "ratelimit" in name or "rate_limit" in name:
        return True
    msg = str(exc).lower()
    return "429" in msg or "rate limit" in msg or "too many requests" in msg


def _is_transient_error(exc: Exception) -> bool:
    if _is_rate_limit_error(exc):
        return True
    name = exc.__class__.__name__.lower()
    if "timeout" in name or "timedout" in name or "tempor" in name:
        return True
    msg = str(exc).lower()
    return "timeout" in msg or "timed out" in msg or "connection reset" in msg


async def _generate_one_with_retries(
    client: Any,
    payload: Dict[str, Any],
    *,
    attempts: int,
    job_label: str,
) -> Any:
    last_exc: Optional[Exception] = None
    for attempt in range(1, attempts + 1):
        try:
            return await client.images.generate(**payload)
        except Exception as exc:
            last_exc = exc
            if not _is_transient_error(exc):
                raise
            if attempt == attempts:
                raise
            sleep_s = _extract_retry_after_seconds(exc)
            if sleep_s is None:
                sleep_s = min(60.0, 2.0**attempt)
            print(
                f"{job_label} attempt {attempt}/{attempts} failed ({exc.__class__.__name__}); retrying in {sleep_s:.1f}s",
                file=sys.stderr,
            )
            await asyncio.sleep(sleep_s)
    raise last_exc or RuntimeError("unknown error")


class OpenAICompatibleImageProvider(ImageProvider):
    def __init__(
        self,
        *,
        api_key: Optional[str],
        base_url: Optional[str],
        client_factory: Optional[ClientFactory] = None,
        async_client_factory: Optional[ClientFactory] = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self._client_factory = client_factory
        self._async_client_factory = async_client_factory
        self._async_client: Optional[Any] = None

    def generate(self, payload: Dict[str, Any]) -> List[str]:
        result = self._create_client().images.generate(**payload)
        return [item.b64_json for item in result.data]

    def edit(
        self,
        payload: Dict[str, Any],
        image_paths: List[Path],
        mask_path: Optional[Path],
    ) -> List[str]:
        with _open_files(image_paths) as image_files, _open_mask(mask_path) as mask_file:
            request = dict(payload)
            request["image"] = image_files if len(image_files) > 1 else image_files[0]
            if mask_file is not None:
                request["mask"] = mask_file
            result = self._create_client().images.edit(**request)
        return [item.b64_json for item in result.data]

    async def generate_batch(
        self,
        payload: Dict[str, Any],
        *,
        attempts: int,
        job_label: str,
    ) -> List[str]:
        result = await _generate_one_with_retries(
            self._create_async_client(),
            payload,
            attempts=attempts,
            job_label=job_label,
        )
        return [item.b64_json for item in result.data]

    def _create_client(self) -> Any:
        if self._client_factory is not None:
            return self._client_factory()
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                f"openai SDK not installed in the active environment. {_dependency_hint('openai')}"
            ) from exc
        return OpenAI(api_key=self.api_key, base_url=self.base_url)

    def _create_async_client(self) -> Any:
        if self._async_client is not None:
            return self._async_client
        if self._async_client_factory is not None:
            self._async_client = self._async_client_factory()
            return self._async_client
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            try:
                import openai as _openai  # noqa: F401
            except ImportError:
                raise RuntimeError(
                    f"openai SDK not installed in the active environment. {_dependency_hint('openai')}"
                ) from exc
            raise RuntimeError(
                "AsyncOpenAI not available in this openai SDK version. "
                f"{_dependency_hint('openai', upgrade=True)}"
            ) from exc
        self._async_client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._async_client


def _open_files(paths: List[Path]):
    return _FileBundle(paths)


def _open_mask(mask_path: Optional[Path]):
    if mask_path is None:
        return _NullContext()
    return _SingleFile(mask_path)


class _NullContext:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


class _SingleFile:
    def __init__(self, path: Path):
        self._path = path
        self._handle = None

    def __enter__(self):
        self._handle = self._path.open("rb")
        return self._handle

    def __exit__(self, exc_type, exc, tb):
        if self._handle:
            try:
                self._handle.close()
            except Exception:
                pass
        return False


class _FileBundle:
    def __init__(self, paths: List[Path]):
        self._paths = paths
        self._handles: List[object] = []

    def __enter__(self):
        self._handles = [p.open("rb") for p in self._paths]
        return self._handles

    def __exit__(self, exc_type, exc, tb):
        for handle in self._handles:
            try:
                handle.close()
            except Exception:
                pass
        return False
