"""Provider-independent interface for original uploaded files.

Application modules should import from this module, never from a provider-specific
implementation. FILE_STORAGE_PROVIDER selects the implementation at runtime.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any



def _provider():
    provider = os.getenv("FILE_STORAGE_PROVIDER", "gridfs").strip().lower()
    if provider == "gridfs":
        from backend.app.storage import gridfs_storage
        return gridfs_storage
    raise RuntimeError(
        f"Unsupported FILE_STORAGE_PROVIDER '{provider}'. "
        "Supported provider: gridfs."
    )


def save_file(file_id: str, filename: str, data: bytes, metadata: dict | None = None) -> None:
    _provider().save_file(file_id, filename, data, metadata)


def get_file(file_id: str) -> bytes:
    return _provider().get_file(file_id)


def delete_file(file_id: str) -> bool:
    return _provider().delete_file(file_id)


def read_file_record(record: dict[str, Any], *, allow_external_legacy: bool = False) -> bytes:
    """Read a new GridFS record or a legacy local-file record."""
    if record.get("storage_provider") == "gridfs":
        file_id = record.get("storage_file_id") or record.get("file_id") or record.get("document_id")
        if not file_id:
            raise FileNotFoundError("The stored file reference is missing.")
        return get_file(str(file_id))

    # Backward compatibility for records created before the GridFS migration.
    legacy_path = record.get("file_path")
    if legacy_path:
        backend_root = Path(__file__).resolve().parents[2]
        path = Path(legacy_path)
        if not path.is_absolute():
            path = backend_root / path
        path = path.resolve()
        allowed_roots = [
            (backend_root / "data" / "uploads").resolve(),
            (backend_root / "data" / "project_uploads").resolve(),
        ]
        is_allowed = any(path == allowed or allowed in path.parents for allowed in allowed_roots)
        if path.is_file() and (is_allowed or allow_external_legacy):
            return path.read_bytes()
    raise FileNotFoundError("The uploaded file is no longer available in storage.")


def delete_file_record(record: dict[str, Any]) -> None:
    if record.get("storage_provider") == "gridfs":
        file_id = record.get("storage_file_id") or record.get("file_id") or record.get("document_id")
        if file_id:
            delete_file(str(file_id))
        return
    legacy_path = record.get("file_path")
    if legacy_path:
        backend_root = Path(__file__).resolve().parents[2]
        path = Path(legacy_path)
        if not path.is_absolute():
            path = backend_root / path
        path = path.resolve()
        allowed_roots = [
            (backend_root / "data" / "uploads").resolve(),
            (backend_root / "data" / "project_uploads").resolve(),
        ]
        if any(path == allowed or allowed in path.parents for allowed in allowed_roots) and path.is_file():
            path.unlink()
