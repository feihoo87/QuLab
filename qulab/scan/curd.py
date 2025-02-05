import lzma
import pickle
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Sequence, Type, Union

from sqlalchemy.orm import Query, Session, aliased
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.session import Session
from ..dicttree import foldDict

from .models import (Cell, Comment, Config, InputText, Notebook, Record,
                     Report, Sample, Tag, utcnow)


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


def create_notebook(session: Session, notebook_name: str) -> Notebook:
    """Create a notebook in the database."""
    notebook = Notebook(name=notebook_name)
    session.add(notebook)
    return notebook


def create_input_text(session: Session, input_text: str) -> InputText:
    """Create an input text in the database."""
    input = InputText()
    input.text = input_text
    try:
        input = session.query(InputText).filter(
            InputText.hash == input.hash,
            InputText.text_field == input_text).one()
    except NoResultFound:
        session.add(input)
    return input


def create_cell(session: Session, notebook: Notebook, input_text: str) -> Cell:
    """Create a cell in the database."""
    cell = Cell()
    cell.notebook = notebook
    cell.input = create_input_text(session, input_text)
    cell.index = len(notebook.cells) - 1
    session.add(cell)
    notebook.atime = cell.ctime
    return cell


def create_config(session: Session, config: dict | bytes, base: Path,
                  filename: str) -> Config:
    """Create a config in the database."""

    if not isinstance(config, bytes):
        buf = pickle.dumps(config)
        buf = lzma.compress(buf)
        content_type = 'application/pickle+lzma'
    else:
        buf = config
        content_type = 'application/octet-stream'
    config = Config(buf)
    config.content_type = content_type
    for cfg in session.query(Config).filter(Config.hash == config.hash).all():
        with open(base / cfg.file, 'rb') as f:
            if f.read() == buf:
                cfg.atime = utcnow()
                return cfg
    else:
        path = base / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'wb') as f:
            f.write(buf)
        config.file = filename
        session.add(config)
    return config


def get_config(session: Session, config_id: int, base: Path):
    config = session.get(Config, config_id)
    if config is None:
        return None
    config.atime = utcnow()
    path = base / config.file
    with open(path, 'rb') as f:
        buf = f.read()
    if config.content_type == 'application/pickle+lzma':
        buf = lzma.decompress(buf)
        buf = pickle.loads(buf)
    return buf
