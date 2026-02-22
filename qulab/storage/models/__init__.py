"""Storage models - SQLAlchemy ORM models for unified storage."""

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from .base import Base, SessionManager
from .config import Config, get_or_create_config, load_config, save_config
from .dataset import Array, Dataset, count_datasets, get_array, query_datasets
from .document import Document, count_documents, query_documents
from .script import Script, get_or_create_script, load_script, save_script
from .tag import Tag, get_or_create_tag, has_tags


def create_tables(url: str):
    """Create all tables in the database."""
    from sqlalchemy import create_engine

    engine = create_engine(url)
    Base.metadata.create_all(engine)


def create_session(url: str) -> Session:
    """Create a new database session."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(url)
    session = sessionmaker(bind=engine)
    return session()


__all__ = [
    # Base
    "Base",
    "SessionManager",
    # Core models
    "Document",
    "Dataset",
    "Array",
    # Config models
    "Config",
    "get_or_create_config",
    "load_config",
    "save_config",
    # Script models
    "Script",
    "get_or_create_script",
    "load_script",
    "save_script",
    # Tag models
    "Tag",
    "get_or_create_tag",
    "has_tags",
    # Query functions
    "query_documents",
    "count_documents",
    "query_datasets",
    "count_datasets",
    "get_array",
    # Utilities
    "create_tables",
    "create_session",
]
