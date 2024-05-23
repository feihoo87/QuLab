from datetime import date, datetime, timezone
from typing import Sequence, Type, Union

from sqlalchemy.orm import Query, Session, aliased
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.session import Session
from waveforms.dicttree import foldDict

from .models import Comment, Record, Report, Sample, Tag


def tag(session: Session, tag_text: str) -> Tag:
    """Get a tag from the database or create a new if not exists."""
    try:
        return session.query(Tag).filter(Tag.text == tag_text).one()
    except NoResultFound:
        tag = Tag(text=tag_text)
        return tag


def tag_it(session: Session, tag_text: str, obj: Union[Sample, Record,
                                                       Report]) -> Tag:
    """Tag an object."""
    if obj.id is None:
        session.add(obj)
        obj.tags.append(tag(session, tag_text))
    else:
        session.query(type(obj)).filter(
            type(obj).id == obj.id).one().tags.append(tag(session, tag_text))
    session.commit()


def get_object_with_tags(session: Session,
                         cls: Union[Type[Comment], Type[Sample], Type[Record],
                                    Type[Report]], *tags: str) -> Query:
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


def query_record(session: Session,
                 offset: int = 0,
                 limit: int = 10,
                 app: str | None = None,
                 tags: Sequence[str] = (),
                 before: datetime | date | None = None,
                 after: datetime | date | None = None):
    tz_offset = datetime.now(timezone.utc).astimezone().utcoffset()
    table = {'header': ['ID', 'App', 'tags', 'created time'], 'body': []}
    apps = sorted(
        set([
            n for n, *_ in get_object_with_tags(session.query(Record.app),
                                                Record, *tags).all()
        ]))
    apps = foldDict(dict([(app, None) for app in apps]))

    query = get_object_with_tags(session, Record, *tags)

    if app is not None:
        if app.endswith('*'):
            query = query.filter(Record.app.like(app[:-1] + '%'))
        else:
            query = query.filter(Record.app == app)
    if before is not None:
        if isinstance(before, date):
            before = datetime(before.year, before.month, before.day)
        query = query.filter(Record.ctime <= before - tz_offset)
    if after is not None:
        if isinstance(after, date):
            after = datetime(after.year, after.month, after.day)
        query = query.filter(Record.ctime >= after - tz_offset)
    total = query.count()
    for r in query.order_by(Record.ctime.desc()).limit(limit).offset(offset):
        tags = sorted([t.text for t in r.tags])
        ctime = r.ctime + tz_offset
        row = [r.id, r.app, tags, ctime]
        table['body'].append(row)

    return total, apps, table


def update_tags(session: Session,
                record_id: int,
                tags: Sequence[str],
                append: bool = False):
    record = session.get(Record, record_id)
    if record is None:
        return False
    if append:
        old = [t.text for t in record.tags]
        for t in old:
            if t not in tags:
                tags.append(t)
    record.tags = [tag(session, t) for t in tags]
    try:
        session.commit()
    except Exception:
        session.rollback()
        return False
    return True


def remove_tags(session: Session, record_id: int, tags: Sequence[str]):
    record = session.get(Record, record_id)
    if record is None:
        return False
    old = [t.text for t in record.tags]
    record.tags = [tag(session, t) for t in old if t not in tags]
    try:
        session.commit()
    except Exception:
        session.rollback()
        return False
    return True
