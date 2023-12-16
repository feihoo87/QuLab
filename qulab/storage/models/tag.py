from typing import Type

from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import Query, Session, aliased, relationship
from sqlalchemy.orm.exc import NoResultFound

from . import Base


class Tag(Base):
    __tablename__ = 'tags'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)

    def __init__(self, name: str) -> None:
        self.name = name

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f'Tag({self.name!r})'


def has_tags(cls: Type[Base]) -> Type[Base]:
    table = Table(
        f'{cls.__tablename__}_tags', Base.metadata,
        Column('item_id',
               ForeignKey(f'{cls.__tablename__}.id'),
               primary_key=True),
        Column('tag_id', ForeignKey('tags.id'), primary_key=True))

    cls.tags = relationship("Tag", secondary=table, backref=cls.__tablename__)

    def add_tag(self, tag: Tag):
        if tag not in self.tags:
            self.tags.append(tag)

    def remove_tag(self, tag: Tag):
        if tag in self.tags:
            self.tags.remove(tag)

    cls.add_tag = add_tag
    cls.remove_tag = remove_tag

    return cls


def tag(session: Session, tag_text: str) -> Tag:
    """Get a tag from the database or create a new if not exists."""
    try:
        return session.query(Tag).filter(Tag.text == tag_text).one()
    except NoResultFound:
        tag = Tag(text=tag_text)
        return tag


def get_object_with_tags(session: Session, cls: Type[Base],
                         *tags: str) -> Query:
    """
    Query objects with the given tags.

    Parameters
    ----------
    session : :class:`sqlalchemy.orm.Session`
        The database session.
    cls : :class:`sqlalchemy.orm.Mapper`
        The object class.
    tags : str
        The tags.

    Returns
    -------
    :class:`sqlalchemy.orm.Query`
        The query.
    """
    if isinstance(session, Query):
        q = session
    else:
        q = session.query(cls)
    if not hasattr(cls, 'tags'):
        return []

    aliase = {tag: aliased(Tag) for tag in tags}

    for tag, a in aliase.items():
        q = q.join(a, cls.tags)
        if '*' in tag:
            q = q.filter(a.text.like(tag.replace('*', '%')))
        else:
            q = q.filter(a.text == tag)
    return q
