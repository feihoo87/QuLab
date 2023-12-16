from datetime import date, datetime
from typing import Sequence

import dill
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Session, relationship

from .base import Base
from .config import Config
from .tag import get_object_with_tags, has_tags, tag


@has_tags
class Record(Base):
    __tablename__ = 'records'

    id = Column(Integer, primary_key=True)
    ctime = Column(DateTime, default=datetime.utcnow)
    mtime = Column(DateTime, default=datetime.utcnow)
    atime = Column(DateTime, default=datetime.utcnow)
    name = Column(String)
    datafile_id = Column(Integer, ForeignKey('files.id'))
    configfile_id = Column(Integer, ForeignKey('files.id'))
    meta_id = Column(Integer, ForeignKey('files.id'))

    datafile = relationship("File", foreign_keys=[datafile_id])
    configfile = relationship("File", foreign_keys=[configfile_id])
    metafile = relationship("File", foreign_keys=[meta_id])

    @property
    def data(self) -> dict:
        result = dill.loads(self.datafile.read())
        result['meta'] = self.meta
        result['meta']['config'] = self.config
        return result

    @data.setter
    def data(self, data: dict):
        meta = data.pop('meta', {})
        self.meta = meta
        self.datafile.write(dill.dumps(data))

    @property
    def config(self) -> dict:
        return dill.loads(self.configfile.read())

    @config.setter
    def config(self, data: dict):
        self.configfile.write(dill.dumps(data))

    @property
    def meta(self) -> dict:
        meta = dill.loads(self.metafile.read())
        meta['id'] = self.id
        meta['name'] = self.name
        meta['ctime'] = self.ctime
        meta['mtime'] = self.mtime
        meta['atime'] = self.atime
        return meta

    @meta.setter
    def meta(self, data: dict):
        if 'config' in data:
            config = data.pop('config', {})
            self.config = config
        self.metafile.write(dill.dumps(data))

    def export(self, path):
        with open(path, 'wb') as f:
            f.write(self.data)

    def __init__(self, name: str, data: bytes) -> None:
        self.name = name
        self.data = data

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f'Record({self.name!r})'


def query_record(
        session: Session,
        offset: int = 0,
        limit: int = 10,
        name: str | None = None,
        tags: Sequence[str] = (),
        before: datetime | date | None = None,
        after: datetime | date | None = None) -> tuple[int, dict, dict]:
    from waveforms.dicttree import foldDict

    local_tm = datetime.fromtimestamp(0)
    utc_tm = datetime.utcfromtimestamp(0)
    tz_offset = local_tm - utc_tm
    table = {'header': ['ID', 'Name', 'tags', 'created time'], 'body': []}
    name_lst = sorted(
        set([
            n for n, *_ in get_object_with_tags(session.query(Record.name),
                                                Record, *tags).all()
        ]))
    name_tr = foldDict(dict([(name, None) for name in name_lst]))

    query = get_object_with_tags(session, Record, *tags)

    if name is not None:
        if name.endswith('*'):
            query = query.filter(Record.name.like(name[:-1] + '%'))
        else:
            query = query.filter(Record.name == name)
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
        row = [r.id, r.name, tags, ctime]
        table['body'].append(row)

    return total, name_tr, table


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
