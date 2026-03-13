from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class EndBrainConfig:
    storage_dir: str
    memory_limit_mb: int = 512
    sync_interval_seconds: int = 5
    auto_load: bool = True

    def __post_init__(self) -> None:
        if not self.storage_dir:
            raise ValueError("storage_dir is required")
        if self.memory_limit_mb <= 0:
            raise ValueError("memory_limit_mb must be > 0")
        if self.sync_interval_seconds < 0:
            raise ValueError("sync_interval_seconds must be >= 0")

    @property
    def storage_path(self) -> Path:
        return Path(self.storage_dir)

    @property
    def memory_limit_bytes(self) -> int:
        return int(self.memory_limit_mb * 1024 * 1024)
