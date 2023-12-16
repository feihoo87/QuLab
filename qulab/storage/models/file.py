import zlib
from datetime import datetime

from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Integer, String,
                        event)
from sqlalchemy.orm import relationship
from sqlalchemy.orm.session import Session

from ..chunk import CHUNKSIZE, delete_chunk, load_chunk, save_chunk
from . import Base


class FileChunk(Base):
    __tablename__ = 'file_chunks'

    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey('files.id'))
    index = Column(Integer)
    size = Column(Integer)
    chunk_hash = Column(String)
    compressed = Column(Boolean, default=False)

    file = relationship("File", back_populates="chunks")

    @property
    def chunk(self):
        if hasattr(self, '_chunk'):
            return self._chunk
        return load_chunk(self.chunk_hash, self.compressed)

    @chunk.setter
    def chunk(self, data):
        self._chunk = data


@event.listens_for(FileChunk, 'before_insert')
def before_insert_file_chunk(mapper, connection, target: FileChunk):
    target.chunk_hash, target.size = save_chunk(target._chunk)


class File(Base):
    __tablename__ = 'files'

    id = Column(Integer, primary_key=True)
    ctime = Column(DateTime, default=datetime.utcnow)
    mtime = Column(DateTime, default=datetime.utcnow)
    atime = Column(DateTime, default=datetime.utcnow)
    name = Column(String)
    size = Column(Integer)
    chunks = relationship("FileChunk", order_by=FileChunk.index)

    def write(self, data):
        self.mtime = datetime.utcnow()
        self.size = len(data)
        self.chunks = []
        for i in range(0, len(data), CHUNKSIZE):
            chunk = FileChunk()
            chunk.index = i // CHUNKSIZE
            chunk._chunk = data[i:i + CHUNKSIZE]
            chunk.size = len(chunk._chunk)
            self.chunks.append(chunk)

    def read(self):
        self.atime = datetime.utcnow()
        return b''.join([c.chunk for c in self.chunks])


@event.listens_for(File, 'before_delete')
def before_delete_file(mapper, connection, target):
    for chunk in target.chunks:
        connection.execute(
            FileChunk.__table__.delete().where(FileChunk.id == chunk.id))


def compress_chunks(db: Session):
    for chunk in db.query(FileChunk).filter(
            FileChunk.compressed == False).limit(100):
        old_chunk_hash = chunk.chunk_hash
        buf = zlib.compress(chunk.chunk)
        chunk_hash, size = save_chunk(buf, compressed=True)
        chunk.chunk_hash = chunk_hash
        chunk.size = size
        chunk.compressed = True
        try:
            db.commit()
            delete_chunk(old_chunk_hash)
        except:
            db.rollback()
            delete_chunk(chunk_hash)
