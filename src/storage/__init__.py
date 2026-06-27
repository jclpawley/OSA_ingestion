"""Storage backend factory."""

from __future__ import annotations

from src.config_loader import StorageSettings
from src.storage.base import StorageBackend
from src.storage.local import LocalStorageBackend


def create_storage(settings: StorageSettings) -> StorageBackend:
    if settings.mode == "local":
        return LocalStorageBackend(settings.local_s3_path, settings.local_rds_path)
    raise NotImplementedError(
        f"Storage mode '{settings.mode}' is not implemented yet. Use 'local' for testing."
    )
