from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock
from uuid import uuid4

from app.services.file_reader import UploadedFile


@dataclass(slots=True)
class StoredUpload:
    """Small immutable snapshot of an upload kept only for resampling."""

    filename: str
    content: bytes
    file_type: str


class InMemoryUploadStore:
    """Bounded in-process upload cache used by the resample flow.

    DatasetPeek intentionally avoids persistence. This store exists only so a user
    can request a new random sample after profiling the same uploaded file.
    """

    def __init__(self, max_entries: int = 2) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")

        self._max_entries = max_entries
        self._uploads: OrderedDict[str, StoredUpload] = OrderedDict()
        self._lock = RLock()

    def save(self, uploaded_file: UploadedFile) -> str:
        """Store one upload and return an opaque token for later lookup."""

        token = uuid4().hex
        with self._lock:
            self._uploads[token] = StoredUpload(
                filename=uploaded_file.filename,
                content=uploaded_file.content,
                file_type=uploaded_file.file_type,
            )
            self._uploads.move_to_end(token)
            self._evict_oldest_uploads()
        return token

    def get(self, token: str) -> StoredUpload | None:
        """Return the upload for a token and mark it as recently used."""

        with self._lock:
            upload = self._uploads.get(token)
            if upload is None:
                return None

            self._uploads.move_to_end(token)
            return upload

    def _evict_oldest_uploads(self) -> None:
        while len(self._uploads) > self._max_entries:
            self._uploads.popitem(last=False)
