
"""GridFS implementation for durable uploaded-file storage."""
from __future__ import annotations

from io import BytesIO

from gridfs import GridFSBucket
from gridfs.errors import NoFile

from backend.app.database.mongodb import get_mongodb_database

BUCKET_NAME = "classroom_files"


def _bucket():
    """Get the GridFS bucket from the configured MongoDB database."""
    return GridFSBucket(
        get_mongodb_database(),
        bucket_name=BUCKET_NAME,
    )


def save_file(
    file_id: str,
    filename: str,
    data: bytes,
    metadata: dict | None = None,
) -> None:
    """Save file bytes using the application's stable file ID."""
    bucket = _bucket()

    try:
        bucket.delete(file_id)
    except NoFile:
        pass

    bucket.upload_from_stream_with_id(
        file_id,
        filename,
        BytesIO(data),
        metadata=metadata or {},
    )


def get_file(file_id: str) -> bytes:
    """Retrieve the complete file."""
    try:
        stream = _bucket().open_download_stream(file_id)
    except NoFile as exc:
        raise FileNotFoundError(
            f"Stored file '{file_id}' was not found."
        ) from exc

    try:
        return stream.read()
    finally:
        stream.close()


def delete_file(file_id: str) -> bool:
    """Delete a stored file."""
    try:
        _bucket().delete(file_id)
        return True
    except NoFile:
        return False
