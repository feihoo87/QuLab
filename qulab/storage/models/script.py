"""Script model - content-addressed storage for code scripts."""

import lzma
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import Session

from .base import Base, utcnow


class Script(Base):
    """Script model - stores code scripts with content-addressed deduplication.

    Scripts are stored as compressed text and referenced by SHA1 hash.
    Same script content is only stored once, with reference counting for cleanup.
    """

    __tablename__ = "scripts"

    id = Column(Integer, primary_key=True)
    script_hash = Column(String(40), unique=True, index=True, nullable=False)  # SHA1 hash
    size = Column(Integer, nullable=False)
    language = Column(String, default="python")  # python, javascript, etc.
    ref_count = Column(Integer, default=0)  # Reference count for cleanup
    ctime = Column(DateTime, default=utcnow)
    atime = Column(DateTime, default=utcnow)

    def __repr__(self) -> str:
        return f"Script(id={self.id}, hash={self.script_hash[:8]}..., lang={self.language}, refs={self.ref_count})"

    def touch(self):
        """Update access time."""
        self.atime = utcnow()


def compute_script_hash(code: str) -> str:
    """Compute SHA1 hash for script code.

    The hash is computed from the compressed representation (same as save_script).

    Args:
        code: Script code string

    Returns:
        SHA1 hash string (40 characters)
    """
    import hashlib

    # Compress first (must match what save_script does)
    script_bytes = lzma.compress(code.encode('utf-8'))
    return hashlib.sha1(script_bytes).hexdigest()


def save_script(code: str, base_path, language: str = "python") -> tuple[str, int]:
    """Save script to content-addressed storage.

    Args:
        code: Script code string
        base_path: Base storage path
        language: Programming language identifier

    Returns:
        Tuple of (script_hash, size_in_bytes)
    """
    from ..chunk import save_chunk

    # Compress the code
    script_bytes = lzma.compress(code.encode('utf-8'))
    chunk_path, size = save_chunk(script_bytes, base_path=base_path)
    # chunk_path.name is the hash
    return chunk_path.name, size


def load_script(script_hash: str, base_path) -> str:
    """Load script from content-addressed storage.

    Args:
        script_hash: SHA1 hash of the script
        base_path: Base storage path

    Returns:
        Script code string
    """
    from ..chunk import load_chunk

    script_bytes = load_chunk(script_hash, base_path=base_path)
    return lzma.decompress(script_bytes).decode('utf-8')


def get_or_create_script(
    session: Session, code: str, base_path, language: str = "python"
) -> Script:
    """Get existing script or create new one with content-addressed storage.

    Args:
        session: Database session
        code: Script code string
        base_path: Base storage path
        language: Programming language identifier

    Returns:
        Script instance
    """
    script_hash = compute_script_hash(code)

    # Try to find existing script
    script = session.query(Script).filter_by(script_hash=script_hash).first()

    if script is None:
        # Save script to storage
        _, size = save_script(code, base_path, language)

        # Create new script record
        script = Script(script_hash=script_hash, size=size, language=language, ref_count=0)
        session.add(script)

    script.touch()
    return script


def increment_script_ref(session: Session, script_id: int) -> None:
    """Increment reference count for a script.

    Args:
        session: Database session
        script_id: Script ID
    """
    script = session.get(Script, script_id)
    if script:
        script.ref_count += 1


def decrement_script_ref(session: Session, script_id: int) -> None:
    """Decrement reference count for a script, optionally cleaning up.

    Args:
        session: Database session
        script_id: Script ID
    """
    script = session.get(Script, script_id)
    if script:
        script.ref_count = max(0, script.ref_count - 1)
        # Optionally delete if ref_count reaches 0
        # if script.ref_count == 0:
        #     # Cleanup logic here if needed
        #     pass
