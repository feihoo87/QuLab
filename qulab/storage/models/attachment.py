"""Attachment model - content-addressed file storage.

Attachments can be associated with multiple Datasets and Documents.
Supports images, PDFs, videos, and any other file types.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Table
from sqlalchemy.orm import Session, relationship

from .base import Base, utcnow

if TYPE_CHECKING:
    from .dataset import Dataset
    from .document import Document


# Dataset-Attachment association table
# An Attachment can be associated with multiple Datasets
# A Dataset can have multiple Attachments
dataset_attachments = Table(
    "dataset_attachments",
    Base.metadata,
    Column("dataset_id", ForeignKey("datasets.id"), primary_key=True),
    Column("attachment_id", ForeignKey("attachments.id"), primary_key=True),
)


# Document-Attachment association table
# An Attachment can be associated with multiple Documents
# A Document can have multiple Attachments
document_attachments = Table(
    "document_attachments",
    Base.metadata,
    Column("document_id", ForeignKey("documents.id"), primary_key=True),
    Column("attachment_id", ForeignKey("attachments.id"), primary_key=True),
)


class Attachment(Base):
    """Attachment model - content-addressed file storage.

    Attachments can be associated with multiple Datasets and Documents.
    Supports images, PDFs, videos, and any other file types.
    """

    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)  # Original filename
    mime_type = Column(String, nullable=False)  # MIME type
    chunk_hash = Column(String(40), nullable=False, index=True)  # SHA1 content hash
    size = Column(Integer, nullable=False)  # File size in bytes

    # Optional metadata
    meta = Column(JSON, default=dict)

    # Timestamps
    ctime = Column(DateTime, default=utcnow)
    atime = Column(DateTime, default=utcnow)

    # Relationships (back-populated by association tables)
    datasets = relationship(
        "Dataset",
        secondary=dataset_attachments,
        back_populates="attachments",
        doc="Datasets that reference this attachment",
    )
    documents = relationship(
        "Document",
        secondary=document_attachments,
        back_populates="attachments",
        doc="Documents that reference this attachment",
    )

    def __repr__(self) -> str:
        return f"Attachment(id={self.id}, name={self.name!r}, mime_type={self.mime_type})"

    def touch(self):
        """Update access time."""
        self.atime = utcnow()


def query_attachments(
    session: Session,
    name: Optional[str] = None,
    mime_type: Optional[str] = None,
    offset: int = 0,
    limit: int = 100,
) -> list[Attachment]:
    """Query attachments with filters.

    Args:
        session: Database session
        name: Name pattern (supports * wildcard)
        mime_type: MIME type filter (supports * wildcard)
        offset: Query offset
        limit: Maximum results

    Returns:
        List of Attachment instances matching the filters
    """
    query = session.query(Attachment)

    if name is not None:
        if name.endswith("*"):
            query = query.filter(Attachment.name.like(name[:-1] + "%"))
        else:
            query = query.filter(Attachment.name == name)

    if mime_type is not None:
        if mime_type.endswith("*"):
            query = query.filter(Attachment.mime_type.like(mime_type[:-1] + "%"))
        else:
            query = query.filter(Attachment.mime_type == mime_type)

    query = query.order_by(Attachment.ctime.desc())
    query = query.offset(offset).limit(limit)

    return query.all()


def count_attachments(
    session: Session,
    name: Optional[str] = None,
    mime_type: Optional[str] = None,
) -> int:
    """Count attachments matching filters.

    Args:
        session: Database session
        name: Name pattern
        mime_type: MIME type filter

    Returns:
        Number of matching attachments
    """
    query = session.query(Attachment)

    if name is not None:
        if name.endswith("*"):
            query = query.filter(Attachment.name.like(name[:-1] + "%"))
        else:
            query = query.filter(Attachment.name == name)

    if mime_type is not None:
        if mime_type.endswith("*"):
            query = query.filter(Attachment.mime_type.like(mime_type[:-1] + "%"))
        else:
            query = query.filter(Attachment.mime_type == mime_type)

    return query.count()


def get_attachment_by_hash(session: Session, chunk_hash: str) -> Optional[Attachment]:
    """Get attachment by content hash.

    Args:
        session: Database session
        chunk_hash: SHA1 content hash

    Returns:
        Attachment instance or None
    """
    return session.query(Attachment).filter_by(chunk_hash=chunk_hash).first()
