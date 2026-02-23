from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, declarative_base, sessionmaker

Base = declarative_base()


def utcnow() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class SessionManager:
    """Manages SQLAlchemy sessions for storage operations."""

    def __init__(self, engine: Engine):
        self.engine = engine
        self.Session = sessionmaker(bind=engine)

    @classmethod
    def from_url(cls, url: str) -> "SessionManager":
        """Create a SessionManager from a database URL."""
        engine = create_engine(url)
        return cls(engine)

    def get_session(self) -> Session:
        """Get a new session."""
        return self.Session()

    def create_tables(self):
        """Create all tables."""
        Base.metadata.create_all(self.engine)


# Update timestamps on modification
@event.listens_for(Base, "before_update", propagate=True)
def update_mtime(mapper, connection, target):
    """Automatically update mtime before any update."""
    if hasattr(target, "mtime"):
        target.mtime = utcnow()
