"""Dataset and Array models - unified storage for scan data."""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Session, relationship

from .base import Base
from .tag import has_tags

if TYPE_CHECKING:
    from .document import Document
    from .tag import Tag


@has_tags
class Dataset(Base):
    """Dataset model - stores scan/experiment data.

    This unifies the previous Record concept from scan.record with a more
    general dataset storage concept.
    """

    __tablename__ = "datasets"

    # Composite index for efficient "find latest by name" queries
    __table_args__ = (
        Index('ix_datasets_name_ctime', 'name', 'ctime'),
    )

    id = Column(Integer, primary_key=True)
    name = Column(String, index=True)
    description = Column(JSON, default=dict)

    # Config and Script references (content-addressed)
    config_id = Column(Integer, ForeignKey("configs.id"), nullable=True)
    script_id = Column(Integer, ForeignKey("scripts.id"), nullable=True)

    # Timestamps
    ctime = Column(DateTime, default=datetime.utcnow)
    mtime = Column(DateTime, default=datetime.utcnow)
    atime = Column(DateTime, default=datetime.utcnow)

    # Relationships
    config = relationship("Config", foreign_keys=[config_id])
    script = relationship("Script", foreign_keys=[script_id])

    # Associated arrays
    arrays = relationship(
        "Array", back_populates="dataset", cascade="all, delete-orphan"
    )

    # Many-to-many relationship with Document
    # A Dataset can be analyzed to produce multiple Documents
    # A Document can be derived from multiple Datasets
    documents = relationship(
        "Document",
        secondary="document_datasets",
        back_populates="datasets",
        doc="Documents derived from this dataset",
    )

    def __repr__(self) -> str:
        return f"Dataset(id={self.id}, name={self.name!r}, arrays={len(self.arrays)})"

    def touch(self):
        """Update access time."""
        self.atime = datetime.utcnow()


class Array(Base):
    """Array model - stores multidimensional array data.

    Represents a single array within a dataset, corresponding to
    the previous BufferList concept from scan.record.
    """

    __tablename__ = "arrays"

    id = Column(Integer, primary_key=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=False)
    name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)  # Relative path within storage
    inner_shape = Column(JSON, default=list)  # Inner shape as list
    lu = Column(JSON, default=list)  # Lower bounds (left-bottom)
    rd = Column(JSON, default=list)  # Upper bounds (right-top)

    # Relationship
    dataset = relationship("Dataset", back_populates="arrays")

    def __repr__(self) -> str:
        return f"Array(name={self.name!r}, dataset_id={self.dataset_id})"

    @property
    def shape(self) -> tuple:
        """Compute logical shape from bounds."""
        if not self.lu or not self.rd:
            return ()
        outer = tuple(r - l for l, r in zip(self.lu, self.rd))
        inner = tuple(self.inner_shape) if self.inner_shape else ()
        return outer + inner


def query_datasets(
    session: Session,
    name: Optional[str] = None,
    tags: Optional[List[str]] = None,
    before: datetime | None = None,
    after: datetime | None = None,
    offset: int = 0,
    limit: int = 100,
) -> list[Dataset]:
    """Query datasets with filters.

    Args:
        session: Database session
        name: Name pattern (supports * wildcard)
        tags: List of required tags
        before: Created before this time
        after: Created after this time
        offset: Query offset
        limit: Maximum results

    Returns:
        List of Dataset instances matching the filters
    """
    query = session.query(Dataset)

    if name is not None:
        if name.endswith("*"):
            query = query.filter(Dataset.name.like(name[:-1] + "%"))
        else:
            query = query.filter(Dataset.name == name)

    if before is not None:
        query = query.filter(Dataset.ctime <= before)

    if after is not None:
        query = query.filter(Dataset.ctime >= after)

    if tags:
        from .tag import Tag

        for tag_name in tags:
            query = query.filter(Dataset.tags.any(Tag.name == tag_name))

    query = query.order_by(Dataset.ctime.desc())
    query = query.offset(offset).limit(limit)

    return query.all()


def count_datasets(
    session: Session,
    name: Optional[str] = None,
    tags: Optional[List[str]] = None,
    before: datetime | None = None,
    after: datetime | None = None,
) -> int:
    """Count datasets matching filters.

    Args:
        session: Database session
        name: Name pattern
        tags: List of required tags
        before: Created before this time
        after: Created after this time

    Returns:
        Number of matching datasets
    """
    query = session.query(Dataset)

    if name is not None:
        if name.endswith("*"):
            query = query.filter(Dataset.name.like(name[:-1] + "%"))
        else:
            query = query.filter(Dataset.name == name)

    if before is not None:
        query = query.filter(Dataset.ctime <= before)

    if after is not None:
        query = query.filter(Dataset.ctime >= after)

    if tags:
        from .tag import Tag

        for tag_name in tags:
            query = query.filter(Dataset.tags.any(Tag.name == tag_name))

    return query.count()


def get_array(session: Session, dataset_id: int, name: str) -> Array | None:
    """Get an array by dataset_id and name.

    Args:
        session: Database session
        dataset_id: Dataset ID
        name: Array name

    Returns:
        Array instance or None
    """
    return (
        session.query(Array)
        .filter_by(dataset_id=dataset_id, name=name)
        .first()
    )


def get_or_create_array(
    session: Session, dataset_id: int, name: str, file_path: str
) -> Array:
    """Get existing array or create new one.

    Args:
        session: Database session
        dataset_id: Dataset ID
        name: Array name
        file_path: Storage file path

    Returns:
        Array instance
    """
    arr = get_array(session, dataset_id, name)
    if arr is None:
        arr = Array(dataset_id=dataset_id, name=name, file_path=file_path)
        session.add(arr)
    return arr
