# Adapted from ningzimu/codex-ppt-skill scripts/image_providers (MIT License).
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional


class ImageProvider(ABC):
    """Common API shape used by image_gen.py command handlers."""

    @abstractmethod
    def generate(self, payload: Dict[str, Any]) -> List[str]:
        """Generate images and return base64-encoded image payloads."""

    @abstractmethod
    def edit(
        self,
        payload: Dict[str, Any],
        image_paths: List[Path],
        mask_path: Optional[Path],
    ) -> List[str]:
        """Edit input images and return base64-encoded image payloads."""

    @abstractmethod
    async def generate_batch(
        self,
        payload: Dict[str, Any],
        *,
        attempts: int,
        job_label: str,
    ) -> List[str]:
        """Generate one batch job with provider-specific retry behavior."""
