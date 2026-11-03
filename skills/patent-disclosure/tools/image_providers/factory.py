# Adapted from ningzimu/codex-ppt-skill scripts/image_providers (MIT License).
from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

from .atlascloud import AtlasCloudImageProvider
from .base import ImageProvider
from .openai_compatible import OpenAICompatibleImageProvider


def create_image_provider(*, api_key: Optional[str], base_url: Optional[str]) -> ImageProvider:
    if _is_atlascloud_base_url(base_url):
        return AtlasCloudImageProvider(api_key=api_key, base_url=base_url)
    return OpenAICompatibleImageProvider(api_key=api_key, base_url=base_url)


def _is_atlascloud_base_url(base_url: Optional[str]) -> bool:
    if not base_url:
        return False
    hostname = urlparse(base_url).hostname or ""
    return "atlascloud.ai" in hostname.lower()
