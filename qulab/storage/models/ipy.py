import hashlib
from datetime import datetime

from sqlalchemy import (Column, DateTime, ForeignKey, Integer, LargeBinary,
                        String, Text)
from sqlalchemy.orm import relationship

from .base import Base


class InputText(Base):
    __tablename__ = 'inputs'

    id = Column(Integer, primary_key=True)
    hash = Column(LargeBinary(20))
    text_field = Column(Text, unique=True)

    @property
    def text(self):
        return self.text_field

    @text.setter
    def text(self, text):
        self.hash = hashlib.sha1(text.encode('utf-8')).digest()
        self.text_field = text

    def __repr__(self) -> str:
        return self.text


class Cell(Base):
    __tablename__ = 'cells'

    id = Column(Integer, primary_key=True)
    notebook_id = Column(Integer, ForeignKey("notebooks.id"))
    index = Column(Integer)
    ctime = Column(DateTime, default=datetime.utcnow)
    ftime = Column(DateTime, default=datetime.utcnow)
    input_id = Column(Integer, ForeignKey("inputs.id"))

    notebook = relationship("Notebook", back_populates="cells")
    input = relationship("InputText")

    def __repr__(self) -> str:
        return f"Cell(index={self.index}, input='{self.input}')"


class Notebook(Base):
    __tablename__ = 'notebooks'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    ctime = Column(DateTime, default=datetime.utcnow)
    atime = Column(DateTime, default=datetime.utcnow)

    cells = relationship("Cell",
                         order_by=Cell.index,
                         back_populates="notebook")
