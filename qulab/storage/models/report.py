from .base import Base
from .tag import Tag, has_tags
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from datetime import datetime

@has_tags
class Report(Base):
    __tablename__ = 'reports'

    id = Column(Integer, primary_key=True)
    ctime = Column(DateTime, default=datetime.utcnow)
    mtime = Column(DateTime, default=datetime.utcnow)

    name = Column(String)
    datafile_id = Column(Integer, ForeignKey('files.id'))
    configfile_id = Column(Integer, ForeignKey('files.id'))
    meta_id = Column(Integer, ForeignKey('files.id'))

    datafile = relationship("File", foreign_keys=[datafile_id])
    configfile = relationship("File", foreign_keys=[configfile_id])
    metafile = relationship("File", foreign_keys=[meta_id])
