"""Attachment class - file attachment with content-addressed storage."""

import hashlib
import mimetypes
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

if TYPE_CHECKING:
    from .local import LocalStorage


@dataclass
class Attachment:
    """Attachment - file attachment with content-addressed storage."""

    id: Optional[int] = None
    name: str = ""  # Original filename
    mime_type: str = "application/octet-stream"
    size: int = 0
    meta: dict = field(default_factory=dict)
    ctime: datetime = field(default_factory=datetime.now)
    atime: datetime = field(default_factory=datetime.now)

    _chunk_hash: Optional[str] = field(default=None, repr=False)
    _storage: Optional["LocalStorage"] = field(default=None, repr=False)

    def __repr__(self) -> str:
        return f"Attachment(id={self.id}, name={self.name!r}, mime_type={self.mime_type}, size={self.size})"

    @classmethod
    def create(
        cls,
        storage: "LocalStorage",
        file_path: Union[str, Path],
        name: Optional[str] = None,
        mime_type: Optional[str] = None,
        meta: Optional[dict] = None,
    ) -> "AttachmentRef":
        """Create attachment from file.

        Args:
            storage: LocalStorage instance
            file_path: Path to the file to attach
            name: Original filename (defaults to file_path name)
            mime_type: MIME type (auto-detected if not provided)
            meta: Optional metadata dictionary

        Returns:
            AttachmentRef for the created attachment
        """
        from .chunk import save_chunk
        from .local import AttachmentRef
        from .models import Attachment as AttachmentModel

        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Read file bytes
        data = file_path.read_bytes()

        # Save to chunk storage (content-addressed)
        chunk_path, size = save_chunk(data, base_path=storage.base_path)
        chunk_hash = chunk_path.name

        # Determine name and mime type
        actual_name = name or file_path.name
        actual_mime = mime_type or mimetypes.guess_type(actual_name)[0] or "application/octet-stream"

        with storage._get_session() as session:
            # Check if attachment with same hash already exists
            from .models import get_attachment_by_hash

            existing = get_attachment_by_hash(session, chunk_hash)
            if existing:
                # Return existing attachment
                return AttachmentRef(existing.id, storage, name=existing.name)

            # Create new attachment model
            att_model = AttachmentModel(
                name=actual_name,
                mime_type=actual_mime,
                chunk_hash=chunk_hash,
                size=size,
                meta=meta or {},
            )
            session.add(att_model)
            session.commit()

            return AttachmentRef(att_model.id, storage, name=actual_name)

    @classmethod
    def create_from_bytes(
        cls,
        storage: "LocalStorage",
        data: bytes,
        name: str,
        mime_type: str,
        meta: Optional[dict] = None,
    ) -> "AttachmentRef":
        """Create attachment from bytes.

        Args:
            storage: LocalStorage instance
            data: File content as bytes
            name: Original filename
            mime_type: MIME type
            meta: Optional metadata dictionary

        Returns:
            AttachmentRef for the created attachment
        """
        from .chunk import save_chunk
        from .local import AttachmentRef
        from .models import Attachment as AttachmentModel, get_attachment_by_hash

        # Save to chunk storage (content-addressed)
        chunk_path, size = save_chunk(data, base_path=storage.base_path)
        chunk_hash = chunk_path.name

        with storage._get_session() as session:
            # Check if attachment with same hash already exists
            existing = get_attachment_by_hash(session, chunk_hash)
            if existing:
                # Return existing attachment
                return AttachmentRef(existing.id, storage, name=existing.name)

            # Create new attachment model
            att_model = AttachmentModel(
                name=name,
                mime_type=mime_type,
                chunk_hash=chunk_hash,
                size=size,
                meta=meta or {},
            )
            session.add(att_model)
            session.commit()

            return AttachmentRef(att_model.id, storage, name=name)

    @classmethod
    def load(cls, storage: "LocalStorage", id: int) -> "Attachment":
        """Load attachment from storage.

        Args:
            storage: LocalStorage instance
            id: Attachment ID

        Returns:
            Attachment instance

        Raises:
            KeyError: If attachment not found
        """
        from .models import Attachment as AttachmentModel

        with storage._get_session() as session:
            att_model = session.get(AttachmentModel, id)
            if att_model is None:
                raise KeyError(f"Attachment {id} not found")

            # Update access time
            att_model.atime = datetime.now()
            session.commit()

            return cls(
                id=att_model.id,
                name=att_model.name,
                mime_type=att_model.mime_type,
                size=att_model.size,
                meta=att_model.meta,
                ctime=att_model.ctime,
                atime=att_model.atime,
                _chunk_hash=att_model.chunk_hash,
                _storage=storage,
            )

    def read(self) -> bytes:
        """Read attachment data.

        Returns:
            File content as bytes

        Raises:
            RuntimeError: If attachment is not associated with storage
        """
        if self._storage is None:
            raise RuntimeError("Attachment is not associated with a storage")

        if self._chunk_hash is None:
            raise RuntimeError("Attachment has no chunk hash")

        from .chunk import load_chunk

        return load_chunk(self._chunk_hash, base_path=self._storage.base_path)

    def save_to_file(self, path: Union[str, Path]) -> None:
        """Save attachment to filesystem.

        Args:
            path: Destination path
        """
        path = Path(path)
        path.write_bytes(self.read())

    def delete(self) -> bool:
        """Delete this attachment (only if no references exist).

        Returns:
            True if deleted, False if still referenced
        """
        if self._storage is None:
            raise RuntimeError("Attachment is not associated with a storage")

        from .models import Attachment as AttachmentModel

        with self._storage._get_session() as session:
            att_model = session.get(AttachmentModel, self.id)
            if att_model is None:
                return False

            # Check if still referenced
            if att_model.datasets or att_model.documents:
                return False

            session.delete(att_model)
            session.commit()
            return True


class AttachmentRef:
    """Lightweight reference to an attachment in local storage."""

    def __init__(self, id: int, storage: "LocalStorage", name: str = ""):
        self.id = id
        self.storage = storage
        self.name = name

    def get(self) -> Attachment:
        """Load the full attachment."""
        return Attachment.load(self.storage, self.id)

    def delete(self) -> bool:
        """Delete the attachment."""
        from .models import Attachment as AttachmentModel

        with self.storage._get_session() as session:
            att = session.get(AttachmentModel, self.id)
            if att is None:
                return False

            # Check if still referenced
            if att.datasets or att.documents:
                return False

            session.delete(att)
            session.commit()
            return True

    def __repr__(self) -> str:
        return f"AttachmentRef(id={self.id}, name={self.name!r})"
