"""Document model - unified storage for workflow reports and similar documents."""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, Table
from sqlalchemy.orm import Session, relationship

from .base import Base, utcnow
from .tag import has_tags

if TYPE_CHECKING:
    from .dataset import Dataset
    from .tag import Tag


# Document-Dataset association table
# A Document can be derived from multiple Datasets
# A Dataset can be analyzed to produce multiple Documents
document_datasets = Table(
    "document_datasets",
    Base.metadata,
    Column("document_id", ForeignKey("documents.id"), primary_key=True),
    Column("dataset_id", ForeignKey("datasets.id"), primary_key=True),
)


@has_tags
class Document(Base):
    """Document model - stores workflow reports and general documents.

    This unifies the previous Report model from executor.storage with a more
    general document storage concept.
    """

    __tablename__ = "documents"

    # Composite index for efficient "find latest by name" queries
    __table_args__ = (
        Index('ix_documents_name_ctime', 'name', 'ctime'),
    )

    id = Column(Integer, primary_key=True)
    name = Column(String, index=True)
    state = Column(String, default="unknown")  # 'ok', 'error', 'warning', 'unknown'
    version = Column(Integer, default=1)
    parent_id = Column(Integer, ForeignKey("documents.id"), nullable=True)

    # Content-addressed storage reference
    chunk_hash = Column(String(40), index=True)  # SHA1 hash
    chunk_size = Column(Integer)

    # Script reference (content-addressed)
    script_id = Column(Integer, ForeignKey("scripts.id"), nullable=True)

    # Metadata
    meta = Column(JSON, default=dict)

    # Timestamps
    ctime = Column(DateTime, default=utcnow)
    mtime = Column(DateTime, default=utcnow)
    atime = Column(DateTime, default=utcnow)

    # Self-referential relationship for version chain
    parent = relationship("Document", remote_side=[id], backref="children")

    # Script relationship
    script = relationship("Script", foreign_keys=[script_id])

    # Many-to-many relationship with Dataset
    # A Document can be derived from multiple Datasets
    # A Dataset can be analyzed to produce multiple Documents
    datasets = relationship(
        "Dataset",
        secondary=document_datasets,
        back_populates="documents",
        doc="Datasets used to derive this document",
    )

    def __repr__(self) -> str:
        return f"Document(id={self.id}, name={self.name!r}, state={self.state})"

    def touch(self):
        """Update access time."""
        self.atime = utcnow()


def get_or_create_tag(session: Session, tag_name: str) -> "Tag":
    """Get existing tag or create new one."""
    from .tag import Tag

    tag = session.query(Tag).filter(Tag.name == tag_name).first()
    if tag is None:
        tag = Tag(name=tag_name)
        session.add(tag)
    return tag


def query_documents(
    session: Session,
    name: Optional[str] = None,
    tags: Optional[List[str]] = None,
    state: Optional[str] = None,
    before: datetime | None = None,
    after: datetime | None = None,
    offset: int = 0,
    limit: int = 100,
) -> list[Document]:
    """Query documents with filters.

    Args:
        session: Database session
        name: Name pattern (supports * wildcard)
        tags: List of required tags
        state: Filter by state
        before: Created before this time
        after: Created after this time
        offset: Query offset
        limit: Maximum results

    Returns:
        List of Document instances matching the filters
    """
    query = session.query(Document)

    if name is not None:
        if name.endswith("*"):
            query = query.filter(Document.name.like(name[:-1] + "%"))
        else:
            query = query.filter(Document.name == name)

    if state is not None:
        query = query.filter(Document.state == state)

    if before is not None:
        query = query.filter(Document.ctime <= before)

    if after is not None:
        query = query.filter(Document.ctime >= after)

    if tags:
        from .tag import Tag

        for tag_name in tags:
            query = query.filter(Document.tags.any(Tag.name == tag_name))

    query = query.order_by(Document.ctime.desc())
    query = query.offset(offset).limit(limit)

    return query.all()


def count_documents(
    session: Session,
    name: Optional[str] = None,
    tags: Optional[List[str]] = None,
    state: Optional[str] = None,
    before: datetime | None = None,
    after: datetime | None = None,
) -> int:
    """Count documents matching filters.

    Args:
        session: Database session
        name: Name pattern
        tags: List of required tags
        state: Filter by state
        before: Created before this time
        after: Created after this time

    Returns:
        Number of matching documents
    """
    query = session.query(Document)

    if name is not None:
        if name.endswith("*"):
            query = query.filter(Document.name.like(name[:-1] + "%"))
        else:
            query = query.filter(Document.name == name)

    if state is not None:
        query = query.filter(Document.state == state)

    if before is not None:
        query = query.filter(Document.ctime <= before)

    if after is not None:
        query = query.filter(Document.ctime >= after)

    if tags:
        from .tag import Tag

        for tag_name in tags:
            query = query.filter(Document.tags.any(Tag.name == tag_name))

    return query.count()


def get_latest_document(
    session: Session,
    name: str,
    state: Optional[str] = None,
) -> Optional[Document]:
    """Get the latest document by name.

    This is the most common query pattern for documents - finding
    the most recent document with a given name.

    Args:
        session: Database session
        name: Document name (exact match)
        state: Optional state filter

    Returns:
        The most recent Document or None if not found
    """
    query = session.query(Document).filter(Document.name == name)

    if state is not None:
        query = query.filter(Document.state == state)

    return query.order_by(Document.ctime.desc()).first()
