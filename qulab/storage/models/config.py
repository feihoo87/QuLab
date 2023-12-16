import dill
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .base import Base
from .file import File
from .tag import Tag, has_tags


@has_tags
class Config(Base):
    __tablename__ = 'configs'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    file_id = Column(Integer, ForeignKey('files.id'))
    meta_id = Column(Integer, ForeignKey('files.id'))

    file = relationship("File", foreign_keys=[file_id])

    @property
    def data(self) -> dict:
        result = dill.loads(self.file.read())
        return result

    @data.setter
    def data(self, data: dict):
        self.file.write(dill.dumps(data))
