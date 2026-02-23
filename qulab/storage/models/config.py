"""Config model - content-addressed storage for dataset configuration."""

import json
import lzma
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import Session

from .base import Base, utcnow


class Config(Base):
    """Config model - stores dataset configuration with content-addressed deduplication.

    Configurations are stored as compressed JSON and referenced by SHA1 hash.
    Same config content is only stored once, with reference counting for cleanup.
    """

    __tablename__ = "configs"

    id = Column(Integer, primary_key=True)
    config_hash = Column(String(40), unique=True, index=True, nullable=False)  # SHA1 hash
    size = Column(Integer, nullable=False)
    ref_count = Column(Integer, default=0)  # Reference count for cleanup
    ctime = Column(DateTime, default=utcnow)
    atime = Column(DateTime, default=utcnow)

    def __repr__(self) -> str:
        return f"Config(id={self.id}, hash={self.config_hash[:8]}..., refs={self.ref_count})"

    def touch(self):
        """Update access time."""
        self.atime = utcnow()


def compute_config_hash(config_dict: dict) -> str:
    """Compute SHA1 hash for a config dictionary.

    The hash is computed from the compressed representation (same as save_config).

    Args:
        config_dict: Configuration dictionary

    Returns:
        SHA1 hash string (40 characters)
    """
    import hashlib

    # Normalize by sorting keys and using separators without whitespace, then compress
    # This must match what save_config does
    config_bytes = lzma.compress(
        json.dumps(config_dict, sort_keys=True, separators=(',', ':')).encode('utf-8')
    )
    return hashlib.sha1(config_bytes).hexdigest()


def save_config(config_dict: dict, base_path) -> tuple[str, int]:
    """Save config to content-addressed storage.

    Args:
        config_dict: Configuration dictionary
        base_path: Base storage path

    Returns:
        Tuple of (config_hash, size_in_bytes)
    """
    from ..chunk import save_chunk

    # Serialize to JSON and compress
    config_bytes = lzma.compress(
        json.dumps(config_dict, sort_keys=True, separators=(',', ':')).encode('utf-8')
    )
    chunk_path, size = save_chunk(config_bytes, base_path=base_path)
    # chunk_path.name is the hash
    return chunk_path.name, size


def load_config(config_hash: str, base_path) -> dict:
    """Load config from content-addressed storage.

    Args:
        config_hash: SHA1 hash of the config
        base_path: Base storage path

    Returns:
        Configuration dictionary
    """
    from ..chunk import load_chunk

    config_bytes = load_chunk(config_hash, base_path=base_path)
    return json.loads(lzma.decompress(config_bytes).decode('utf-8'))


def get_or_create_config(session: Session, config_dict: dict, base_path) -> Config:
    """Get existing config or create new one with content-addressed storage.

    Args:
        session: Database session
        config_dict: Configuration dictionary
        base_path: Base storage path

    Returns:
        Config instance
    """
    config_hash = compute_config_hash(config_dict)

    # Try to find existing config
    config = session.query(Config).filter_by(config_hash=config_hash).first()

    if config is None:
        # Save config to storage
        _, size = save_config(config_dict, base_path)

        # Create new config record
        config = Config(config_hash=config_hash, size=size, ref_count=0)
        session.add(config)

    config.touch()
    return config


def increment_config_ref(session: Session, config_id: int) -> None:
    """Increment reference count for a config.

    Args:
        session: Database session
        config_id: Config ID
    """
    config = session.get(Config, config_id)
    if config:
        config.ref_count += 1


def decrement_config_ref(session: Session, config_id: int) -> None:
    """Decrement reference count for a config, optionally cleaning up.

    Args:
        session: Database session
        config_id: Config ID
    """
    config = session.get(Config, config_id)
    if config:
        config.ref_count = max(0, config.ref_count - 1)
        # Optionally delete if ref_count reaches 0
        # if config.ref_count == 0:
        #     # Cleanup logic here if needed
        #     pass
