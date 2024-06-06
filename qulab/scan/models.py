import hashlib
import pickle
from datetime import datetime, timezone
from functools import singledispatchmethod

from sqlalchemy import (Column, DateTime, Float, ForeignKey, Integer,
                        LargeBinary, String, Table, Text, create_engine)
from sqlalchemy.orm import (backref, declarative_base, relationship,
                            sessionmaker)
from sqlalchemy.orm.session import Session
from waveforms.security import InvalidKey, encryptPassword, verifyPassword


def utcnow():
    return datetime.now(timezone.utc)


Base = declarative_base()

# association table
user_roles = Table('user_roles', Base.metadata,
                   Column('user_id', ForeignKey('users.id'), primary_key=True),
                   Column('role_id', ForeignKey('roles.id'), primary_key=True))

record_reports = Table(
    'record_reports', Base.metadata,
    Column('record_id', ForeignKey('records.id'), primary_key=True),
    Column('report_id', ForeignKey('reports.id'), primary_key=True))

comment_tags = Table(
    'comment_tags', Base.metadata,
    Column('comment_id', ForeignKey('comments.id'), primary_key=True),
    Column('tag_id', ForeignKey('tags.id'), primary_key=True))

snapshot_tags = Table(
    'snapshot_tags', Base.metadata,
    Column('snapshot_id', ForeignKey('snapshots.id'), primary_key=True),
    Column('tag_id', ForeignKey('tags.id'), primary_key=True))

record_tags = Table(
    'record_tags', Base.metadata,
    Column('record_id', ForeignKey('records.id'), primary_key=True),
    Column('tag_id', ForeignKey('tags.id'), primary_key=True))

report_tags = Table(
    'report_tags', Base.metadata,
    Column('report_id', ForeignKey('reports.id'), primary_key=True),
    Column('tag_id', ForeignKey('tags.id'), primary_key=True))

sample_tags = Table(
    'sample_tags', Base.metadata,
    Column('sample_id', ForeignKey('samples.id'), primary_key=True),
    Column('tag_id', ForeignKey('tags.id'), primary_key=True))

sample_reports = Table(
    'sample_reports', Base.metadata,
    Column('sample_id', ForeignKey('samples.id'), primary_key=True),
    Column('report_id', ForeignKey('reports.id'), primary_key=True))

sample_records = Table(
    'sample_records', Base.metadata,
    Column('sample_id', ForeignKey('samples.id'), primary_key=True),
    Column('record_id', ForeignKey('records.id'), primary_key=True))

sample_comments = Table(
    'sample_comments', Base.metadata,
    Column('sample_id', ForeignKey('samples.id'), primary_key=True),
    Column('comment_id', ForeignKey('comments.id'), primary_key=True))

sample_transfer_comments = Table(
    'sample_transfer_comments', Base.metadata,
    Column('transfer_id', ForeignKey('sample_transfer.id'), primary_key=True),
    Column('comment_id', ForeignKey('comments.id'), primary_key=True))

report_comments = Table(
    'report_comments', Base.metadata,
    Column('report_id', ForeignKey('reports.id'), primary_key=True),
    Column('comment_id', ForeignKey('comments.id'), primary_key=True))

record_comments = Table(
    'record_comments', Base.metadata,
    Column('record_id', ForeignKey('records.id'), primary_key=True),
    Column('comment_id', ForeignKey('comments.id'), primary_key=True))


class Role(Base):
    __tablename__ = 'roles'

    id = Column(Integer, primary_key=True)
    name = Column(String)

    users = relationship('User', secondary=user_roles, back_populates='roles')

    def __repr__(self):
        return f"Role(name='{self.name}')"


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    hashed_password = Column(LargeBinary(64))
    fullname = Column(String)

    roles = relationship('Role', secondary=user_roles, back_populates='users')
    attachments = relationship('Attachment', back_populates='user')
    comments = relationship('Comment', back_populates='user')

    def setPassword(self, password):
        self.hashed_password = encryptPassword(password)

    def verify(self, password):
        try:
            verifyPassword(password, self.hashed_password)
            return True
        except InvalidKey:
            return False

    def __repr__(self):
        return f"User(name='{self.name}')"


class ParameterEdge(Base):
    __tablename__ = 'parameter_edges'
    parent_id = Column(ForeignKey('parameters.id'), primary_key=True)
    child_id = Column(ForeignKey('parameters.id'), primary_key=True)
    key = Column(String(50), primary_key=True)


class Parameter(Base):
    __tablename__ = 'parameters'

    id = Column(Integer, primary_key=True)
    type = Column(String)
    unit = Column(String)
    integer = Column(Integer)
    real = Column(Float)
    imag = Column(Float)
    string = Column(String)
    buff = Column(LargeBinary)

    children = relationship("ParameterEdge",
                            foreign_keys=[ParameterEdge.parent_id],
                            backref="parent")
    parents = relationship("ParameterEdge",
                           foreign_keys=[ParameterEdge.child_id],
                           backref="child")

    @property
    def value(self):
        if self.type == 'integer':
            return self.integer
        elif self.type == 'real':
            return self.real
        elif self.type == 'complex':
            return self.real + 1j * self.imag
        elif self.type == 'string':
            return self.string
        elif self.type == 'buffer':
            return self.buff
        elif self.type == 'boolean':
            return self.integer == 1
        elif self.type is None or self.type == 'none':
            return None
        elif self.type == 'tree':
            return self.export()
        else:
            return pickle.loads(self.buff)

    @value.setter
    def value(self, value):
        self._set_value(value)

    @singledispatchmethod
    def _set_value(self, value):
        self.buff = pickle.dumps(value)
        self.type = 'pickle'

    @_set_value.register
    def _(self, value: int):
        self.integer = value
        self.type = 'integer'

    @_set_value.register
    def _(self, value: bool):
        self.integer = int(value)
        self.type = 'boolean'

    @_set_value.register
    def _(self, value: float):
        self.real = value
        self.type = 'real'

    @_set_value.register
    def _(self, value: complex):
        self.real = value.real
        self.imag = value.imag
        self.type = 'complex'

    @_set_value.register
    def _(self, value: str):
        self.string = value
        self.type = 'string'

    @_set_value.register
    def _(self, value: bytes):
        self.buff = value
        self.type = 'buffer'

    @_set_value.register
    def _(self, value: None):
        self.type = 'none'

    def export(self):
        if self.type == 'tree':
            return {a.key: a.child.export() for a in self.children}
        else:
            return self.value


class Snapshot(Base):
    __tablename__ = 'snapshots'

    id = Column(Integer, primary_key=True)
    root_id = Column(ForeignKey('parameters.id'))
    previous_id = Column(Integer, ForeignKey('snapshots.id'))

    followers = relationship("Snapshot",
                             backref=backref('previous', remote_side=[id]))

    root = relationship('Parameter')
    tags = relationship('Tag',
                        secondary=snapshot_tags,
                        back_populates='snapshots')

    def export(self):
        return self.root.export()


class ReportParameters(Base):
    __tablename__ = 'report_parameters'
    parent_id = Column(ForeignKey('reports.id'), primary_key=True)
    child_id = Column(ForeignKey('parameters.id'), primary_key=True)
    key = Column(String(50), primary_key=True)

    parameter = relationship('Parameter')

    @property
    def value(self):
        return self.parameter.value


class Tag(Base):
    __tablename__ = 'tags'

    id = Column(Integer, primary_key=True)
    text = Column(String, unique=True)

    comments = relationship('Comment',
                            secondary=comment_tags,
                            back_populates='tags')
    records = relationship('Record',
                           secondary=record_tags,
                           back_populates='tags')
    reports = relationship('Report',
                           secondary=report_tags,
                           back_populates='tags')
    samples = relationship('Sample',
                           secondary=sample_tags,
                           back_populates='tags')
    snapshots = relationship('Snapshot',
                             secondary=snapshot_tags,
                             back_populates='tags')

    def __init__(self, text) -> None:
        super().__init__()
        self.text = text

    def __repr__(self):
        return f"Tag('{self.text}')"


class Comment(Base):
    __tablename__ = 'comments'

    id = Column(Integer, primary_key=True)
    text = Column(String)
    user_id = Column(Integer, ForeignKey('users.id'))
    ctime = Column(DateTime, default=utcnow)
    mtime = Column(DateTime, default=utcnow)
    atime = Column(DateTime, default=utcnow)
    parent_id = Column(Integer, ForeignKey('comments.id'))

    replies = relationship("Comment", lazy="joined", join_depth=2)
    user = relationship('User', back_populates='comments')
    tags = relationship('Tag',
                        secondary=comment_tags,
                        back_populates='comments')
    attachments = relationship('Attachment', back_populates='comment')


class Attachment(Base):
    __tablename__ = 'attachments'

    id = Column(Integer, primary_key=True)
    filename = Column(String)
    mime_type = Column(String, default='application/octet-stream')
    user_id = Column(Integer, ForeignKey('users.id'))
    comment_id = Column(Integer, ForeignKey('comments.id'))
    ctime = Column(DateTime, default=utcnow)
    mtime = Column(DateTime, default=utcnow)
    atime = Column(DateTime, default=utcnow)
    size = Column(Integer)
    sha1 = Column(String)
    description = Column(Text)

    user = relationship('User', back_populates='attachments')
    comment = relationship('Comment', back_populates='attachments')


class InputText(Base):
    __tablename__ = 'inputs'

    id = Column(Integer, primary_key=True)
    hash = Column(LargeBinary(20), index=True)
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
    ctime = Column(DateTime, default=utcnow)
    ftime = Column(DateTime, default=utcnow)
    input_id = Column(Integer, ForeignKey("inputs.id"))

    notebook = relationship("Notebook", back_populates="cells")
    input = relationship("InputText")

    def __repr__(self) -> str:
        return str(f"Cell(index={self.index}, input='{self.input}')")


class Notebook(Base):
    __tablename__ = 'notebooks'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    ctime = Column(DateTime, default=utcnow)
    atime = Column(DateTime, default=utcnow)

    cells = relationship("Cell",
                         order_by=Cell.index,
                         back_populates="notebook")


class Sample(Base):
    __tablename__ = 'samples'

    id = Column(Integer, primary_key=True)
    name = Column(String)

    account_id = Column(Integer, ForeignKey("sample_accounts.id"))

    tags = relationship("Tag", secondary=sample_tags, back_populates="samples")
    records = relationship("Record",
                           secondary=sample_records,
                           back_populates="samples")
    reports = relationship("Report",
                           secondary=sample_reports,
                           back_populates="samples")
    transfers = relationship("SampleTransfer",
                             order_by="SampleTransfer.ctime",
                             back_populates="sample")
    account = relationship("SampleAccount", back_populates="samples")
    comments = relationship("Comment", secondary=sample_comments)


class SampleAccountType(Base):
    __tablename__ = 'sample_account_types'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(String)

    accounts = relationship("SampleAccount", back_populates="type")


class SampleAccount(Base):
    __tablename__ = 'sample_accounts'

    id = Column(Integer, primary_key=True)
    name = Column(String)
    type_id = Column(Integer, ForeignKey("sample_account_types.id"))
    description = Column(String)

    type = relationship("SampleAccountType", back_populates="accounts")

    samples = relationship("Sample", back_populates="account")


class SampleTransfer(Base):
    __tablename__ = 'sample_transfer'

    id = Column(Integer, primary_key=True)
    sample_id = Column(Integer, ForeignKey("samples.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    ctime = Column(DateTime, default=utcnow)
    debtor_id = Column(Integer, ForeignKey("sample_accounts.id"))
    creditor_id = Column(Integer, ForeignKey("sample_accounts.id"))

    user = relationship("User")
    sample = relationship("Sample", back_populates="transfers")
    debtor = relationship("SampleAccount", foreign_keys=[debtor_id])
    creditor = relationship("SampleAccount", foreign_keys=[creditor_id])
    comments = relationship("Comment", secondary=sample_transfer_comments)


class Config(Base):
    __tablename__ = 'configs'

    id = Column(Integer, primary_key=True)
    hash = Column(LargeBinary(20), index=True)
    file = Column(String)
    content_type = Column(String, default='application/pickle')
    ctime = Column(DateTime, default=utcnow)
    atime = Column(DateTime, default=utcnow)

    records = relationship("Record", back_populates="config")

    def __init__(self, data: bytes) -> None:
        self.hash = hashlib.sha1(data).digest()


class Record(Base):
    __tablename__ = 'records'

    id = Column(Integer, primary_key=True)
    ctime = Column(DateTime, default=utcnow)
    mtime = Column(DateTime, default=utcnow)
    atime = Column(DateTime, default=utcnow)
    user_id = Column(Integer, ForeignKey('users.id'))
    config_id = Column(Integer, ForeignKey('configs.id'))
    parent_id = Column(Integer, ForeignKey('records.id'))
    cell_id = Column(Integer, ForeignKey('cells.id'))

    app = Column(String)
    file = Column(String)
    content_type = Column(String, default='application/pickle')
    key = Column(String)

    parent = relationship("Record",
                          remote_side=[id],
                          back_populates="children")
    children = relationship("Record",
                            remote_side=[parent_id],
                            back_populates="parent")

    config = relationship("Config", back_populates="records")
    user = relationship("User")
    samples = relationship("Sample",
                           secondary=sample_records,
                           back_populates="records")
    cell = relationship("Cell")

    reports = relationship('Report',
                           secondary=record_reports,
                           back_populates='records')
    tags = relationship('Tag', secondary=record_tags, back_populates='records')
    comments = relationship('Comment', secondary=record_comments)


class Report(Base):
    __tablename__ = 'reports'

    id = Column(Integer, primary_key=True)
    ctime = Column(DateTime, default=utcnow)
    mtime = Column(DateTime, default=utcnow)
    atime = Column(DateTime, default=utcnow)
    user_id = Column(Integer, ForeignKey('users.id'))

    category = Column(String)
    title = Column(String)
    content = Column(Text)
    file = Column(String)
    key = Column(String)
    task_hash = Column(LargeBinary(32))

    user = relationship("User")
    samples = relationship("Sample",
                           secondary=sample_reports,
                           back_populates="reports")

    records = relationship('Record',
                           secondary=record_reports,
                           back_populates='reports')

    tags = relationship('Tag', secondary=report_tags, back_populates='reports')
    comments = relationship('Comment', secondary=report_comments)
    _parameters = relationship('ReportParameters')


def create_tables(engine, tables_only=False):
    Base.metadata.create_all(engine)
    if tables_only:
        return

    sys_role = Role(name='sys')
    kernel = User(name='BIG BROTHER')
    kernel.roles.append(sys_role)

    root_role = Role(name='root')
    admin_role = Role(name='admin')
    root_user = User(name='root')
    root_user.setPassword('123')
    root_user.roles.append(root_role)
    root_user.roles.append(admin_role)

    guest_role = Role(name='guest')
    guest_user = User(name='guest')
    guest_user.setPassword('')
    guest_user.roles.append(guest_role)

    t1 = SampleAccountType(name='factory')
    t2 = SampleAccountType(name='destroyed')
    t3 = SampleAccountType(name='storage')
    t4 = SampleAccountType(name='fridge')
    a = SampleAccount(name='destroyed')
    a.type = t2

    Session = sessionmaker(bind=engine)
    session = Session()

    session.add(root_user)
    session.add(guest_user)
    session.add(kernel)
    session.add_all([t1, t2, t3, t4, a])
    try:
        session.commit()
    except:
        session.rollback()
