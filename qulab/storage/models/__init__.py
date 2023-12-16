from sqlalchemy import Engine
from sqlalchemy.orm import Session

from .base import Base
from .file import File, FileChunk
from .ipy import Cell, InputText, Notebook
from .record import Record
from .tag import Tag, has_tags


def create_tables(url: str):
    from sqlalchemy import create_engine
    engine = create_engine(url)
    Base.metadata.create_all(engine)


def create_session(url: str) -> Session:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(url)
    session = sessionmaker(bind=engine)
    return session()
