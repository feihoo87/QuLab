from __future__ import annotations

import ast
import functools
import hashlib
import operator
import pickle
import re
from datetime import datetime
from itertools import islice
from typing import Any, Generator, NamedTuple, Optional, Union

from sqlalchemy import (BigInteger, Boolean, Column, DateTime, ForeignKey,
                        Integer, LargeBinary, String, event, inspect)
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import aliased, backref, declarative_base, relationship
from sqlalchemy.orm.session import Session

from waveforms.dicttree import (DELETE, NOTSET, UNKNOW, Create, Singleton,
                                Update, foldDict, merge)


@compiles(BigInteger, 'sqlite')
def bi_c(element, compiler, **kw):
    return "INTEGER"


Base = declarative_base()


class KeyPattern(NamedTuple):
    like: bool
    fuzzy: bool
    pattern: str
    index: tuple
    end: bool
    case_insensitive: bool = False

    def format(self, matched: str) -> str:

        def f(slices):
            ret = []
            for s in slices:
                if isinstance(s, slice):
                    start, stop, step = s.start, s.stop, s.step
                    start = '' if start is None else start
                    stop = '' if stop is None else stop
                    step = '' if step is None else step
                    if s.step is None:
                        ret.append(f"{start}:{stop}")
                    else:
                        ret.append(f"{start}:{stop}:{step}")
                else:
                    ret.append(repr(s))
            s = ','.join(ret)
            return f"[{s}]"

        index_str = ''.join(f(slices) for slices in self.index)
        return matched + index_str

    @functools.lru_cache(maxsize=1)
    def re(self) -> re.Pattern:
        pattern = re.escape(self.pattern)

        if self.like:
            pattern = pattern.replace('%', '.*?')
            pattern = f"^{pattern}$"
        else:
            pattern = pattern.replace('%', '.*?')
            pattern = f"^((?!{pattern}).)+$"
        if self.case_insensitive:
            pattern = f"^((?i){pattern})$"
        return re.compile(pattern)


_key_pattern = re.compile(
    r'(?P<unlike>!?)(?P<pattern>[_A-Za-z\*][^\[\]\.]*)(?P<index>(\[(.*?)\])*)(?P<end>\.?)'
)


def _parse_key(key):
    ret = []

    for m in _key_pattern.finditer(key):
        index = []
        if m.group('index'):
            for slices_s in m.group('index')[1:-1].split(']['):
                slices = []
                for s in slices_s.split(','):
                    lst = s.split(':')
                    lst = [
                        None if l == '' else ast.literal_eval(l) for l in lst
                    ]
                    if 2 <= len(lst) <= 3:
                        expr = slice(*lst)
                    else:
                        expr = ast.literal_eval(s)
                    slices.append(expr)
                index.append(tuple(slices))
        pattern = m.group('pattern')
        index = tuple(index)
        like = m.group('unlike') == ''
        end = m.group('end') == ''
        if '*' in pattern:
            fuzzy = True
            pattern = pattern.replace('*', '%')
        else:
            fuzzy = False
        ret.append(KeyPattern(like, fuzzy, pattern, index, end))
    return ret


def _getitem(obj, index: tuple):
    for slices in index:
        if isinstance(slices, tuple) and len(slices) == 1:
            slices = slices[0]
        obj = operator.getitem(obj, slices)
    return obj


class _TREE(metaclass=Singleton):
    __slots__ = ()


TREE = _TREE()


class TreeRef():
    __slots__ = ('id')

    def __init__(self, id):
        self.id = id

    def __repr__(self):
        return '{...}'


class RegistryValue(Base):
    __tablename__ = 'registry_values'

    id = Column(BigInteger, primary_key=True)
    hash = Column(LargeBinary(16), nullable=False, index=True)
    chunk = Column(LargeBinary)

    @property
    def value(self):
        return pickle.loads(self.chunk)

    @value.setter
    def value(self, value):
        self.set_value(value)

    def set_value(self, value):
        self.chunk = pickle.dumps(value, protocol=5)
        self.hash = hashlib.md5(self.chunk).digest()


class RegistryKey(Base):
    __tablename__ = 'registry_keys'

    left_id = Column(ForeignKey('registry_nodes.id'), primary_key=True)
    right_id = Column(ForeignKey('registry_nodes.id'), primary_key=True)
    key = Column(String(50), primary_key=True)

    value = relationship(
        "RegistryValue",
        secondary=
        "join(RegistryNode, RegistryValue, RegistryValue.id == RegistryNode.value_id)",
        primaryjoin="and_(RegistryKey.right_id == RegistryNode.id)",
        uselist=False,
        viewonly=True)

    def __repr__(self):
        return f'RegistryKey(key={self.key})'


class RegistryNode(Base):
    __tablename__ = 'registry_nodes'

    id = Column(BigInteger, primary_key=True)
    value_id = Column(ForeignKey('registry_values.id'), nullable=True)
    is_tree = Column(Boolean, default=False)

    value = relationship('RegistryValue')
    children = relationship("RegistryKey",
                            foreign_keys=[RegistryKey.left_id],
                            backref="parent")
    parents = relationship("RegistryKey",
                           foreign_keys=[RegistryKey.right_id],
                           backref="child")


class RegistrySnapshot(Base):
    __tablename__ = 'registry_snapshots'

    id = Column(BigInteger, primary_key=True)
    ctime = Column(DateTime, nullable=False, default=datetime.utcnow)
    root_id = Column(ForeignKey('registry_nodes.id'))
    previous_id = Column(BigInteger, ForeignKey('registry_snapshots.id'))

    followers = relationship("RegistrySnapshot",
                             backref=backref('previous', remote_side=[id]))

    root = relationship('RegistryNode')

    def __repr__(self):
        return f'RegistrySnapshot(id={self.id}, previous_id={self.previous_id})'


def create_tables(engine):
    Base.metadata.create_all(engine, checkfirst=True)


def _setitem(root: Union[RegistryNode, int], key: str,
             node: Union[RegistryNode, int]):
    edge = RegistryKey()
    edge.key = key
    if isinstance(root, RegistryNode):
        if root.id is None:
            edge.parent = root
        else:
            edge.left_id = root.id
    else:
        edge.left_id = root.id
    if isinstance(node, RegistryNode):
        if node.id is None:
            edge.child = node
        else:
            edge.right_id = node.id
    else:
        edge.right_id = node.id


def _create_value(session: Session, value: Any, cache: dict):
    value_obj = RegistryValue()
    value_obj.set_value(value)
    if value_obj.hash in cache:
        return cache[value_obj.hash]
    exist_value_id = session.query(RegistryValue.id).filter(
        RegistryValue.hash == value_obj.hash).one_or_none()
    if exist_value_id is None:
        return cache.setdefault(value_obj.hash, value_obj)
    else:
        return cache.setdefault(value_obj.hash, exist_value_id[0])


def _set_node_value(node: RegistryNode, value: Union[RegistryValue, int]):
    if isinstance(value, RegistryValue):
        if value.id is None:
            node.value = value
        else:
            node.value_id = value.id
    else:
        node.value_id = value


def _create_node(session: Session, value: dict,
                 value_cache: dict) -> RegistryNode:
    root = RegistryNode()
    if not isinstance(value, dict):
        root.is_tree = False
        if isinstance(value, (Create, Update)):
            value = value.n
        _set_node_value(root, _create_value(session, value, value_cache))
        return root

    root.is_tree = True
    _set_node_value(root, _create_value(session, TREE, value_cache))

    for k, v in value.items():
        if v is DELETE:
            continue
        elif isinstance(v, (Create, Update)):
            v = v.n
        _setitem(root, k, _create_node(session, v, value_cache))
    return root


def _patch(session: Session, root: Union[int, RegistryNode],
           diff: dict) -> RegistryNode:
    value_cache = {}
    if isinstance(root, int):
        root = session.get(RegistryNode, root)
    if not diff:
        return root

    if not isinstance(diff, dict):
        return _create_node(session, diff, value_cache)

    new_root = RegistryNode()
    new_root.is_tree = True
    _set_node_value(new_root, _create_value(session, TREE, value_cache))

    updated_keys = set()
    for edge in root.children:
        updated_keys.add(edge.key)
        if edge.key in diff:
            if diff[edge.key] is DELETE:
                continue
            elif isinstance(diff[edge.key], dict):
                node = _patch(session, edge.child, diff[edge.key])
            elif (isinstance(diff[edge.key], Create)
                  and not diff[edge.key].replace):
                node = _patch(session, edge.child, diff[edge.key].n)
            else:
                node = _create_node(session, diff[edge.key], value_cache)
        else:
            node = edge.child
        _setitem(new_root, edge.key, node)

    for k in set(diff.keys()) - updated_keys:
        if diff[k] is DELETE:
            continue
        elif isinstance(diff[k], (Create, Update)):
            _setitem(new_root, k, _create_node(session, diff[k].n,
                                               value_cache))
        else:
            _setitem(new_root, k, _create_node(session, diff[k], value_cache))

    return new_root


def _search_query(session, root_id, patterns):
    alias = [(k, aliased(RegistryKey)) for k in reversed(patterns)]

    node = aliased(RegistryNode)
    root = aliased(RegistryNode)

    path = tuple(a[1].key for a in reversed(alias))

    q = session.query(RegistryValue.chunk, node, *path)
    q = q.join(node, node.value_id == RegistryValue.id)
    right_side = None
    for k, a in alias:
        if right_side is None:
            join_codition = node.id == a.right_id
        else:
            join_codition = a.right_id == right_side.left_id
        q = q.join(a, join_codition)
        if k.pattern != '%':
            if k.case_insensitive:
                if k.like:
                    query_filter = a.key.ilike(k.pattern)
                else:
                    query_filter = a.key.not_ilike(k.pattern)
            else:
                if k.fuzzy:
                    if k.like:
                        query_filter = a.key.like(k.pattern)
                    else:
                        query_filter = a.key.not_like(k.pattern)
                else:
                    if k.like:
                        query_filter = a.key == k.pattern
                    else:
                        query_filter = a.key != k.pattern
            q = q.filter(query_filter)
        right_side = a
    q = q.join(root, root.id == right_side.left_id)
    if isinstance(root_id, int):
        q = q.filter(root.id == root_id)
    elif isinstance(root_id, (list, tuple, set)):
        q = q.filter(root.id.in_(root_id))
    else:
        raise TypeError('root_id must be int, list, tuple or set')
    #print(q.statement)
    return q


def search(session,
           root_id: int,
           patterns: list[KeyPattern],
           limit: Optional[int] = 100,
           offset: int = 0,
           depth: int = -1) -> Generator[tuple[str, Any], None, None]:
    if depth == 0:
        return
    q = _search_query(session, root_id, patterns).offset(offset)
    if limit is not None and limit >= 0:
        q = q.limit(limit)
    for chunk, node, *path in q:
        if node.is_tree:
            value = export(session, node.id, depth=depth - 1)
        else:
            value = pickle.loads(chunk)
        try:
            value = _getitem(value, patterns[-1].index)
        except (IndexError, TypeError):
            continue
        yield '.'.join(k.format(s) for s, k in zip(path, patterns)), value


def export(session, root_id, depth=-1):
    if depth == 0:
        return TreeRef(root_id)

    pattern = KeyPattern(like=True,
                         fuzzy=True,
                         pattern='%',
                         index=(),
                         end=True)
    patterns = []
    ret = {}
    while True:
        depth -= 1
        patterns.append(pattern)
        sub_tree_count = 0
        for k, v in search(session,
                           root_id,
                           patterns=patterns,
                           limit=-1,
                           depth=1):
            if isinstance(v, TreeRef) and depth != 0:
                sub_tree_count += 1
                continue
            ret[k] = v
        if sub_tree_count == 0:
            break

    return foldDict(ret)


def _search_dict_iter(d, patterns, prefix):
    if len(patterns) == 0:
        yield '.'.join(prefix), d
    elif isinstance(d, dict):
        for k in d:
            if patterns[0].re().match(k):
                yield from _search_dict_iter(_getitem(d[k], patterns[0].index),
                                             patterns[1:],
                                             [*prefix, patterns[0].format(k)])


def search_dict(d, key, offset=0, limit=-1):
    patterns = _parse_key(key)
    if limit < 0:
        stop = None
    else:
        stop = offset + limit
    yield from islice(_search_dict_iter(d, patterns, []), offset, stop)


def search_flatten_dict(d, key, offset=0, limit=-1):
    patterns = _parse_key(key)
    pattern = re.compile('\.'.join([p.re().pattern[1:-1] for p in patterns]))
    for k, v in search_dict(d, key, offset, limit):
        if pattern.match(k):
            offset -= 1
            if offset < 0:
                yield k, v
            if limit == 0:
                return
            limit -= 1


class Registry():
    """A registry is a collection of snapshots.

    A registry is a collection of snapshots. Each snapshot is a tree of
    RegistryNode. Each RegistryNode has a value, which is a RegistryValue.
    RegistryValue can be a string, a number, a boolean, a list, a dict, or a
    reference to another RegistryNode.
    """

    def __init__(self,
                 session: Session,
                 snapshot: Union[None, int, dict, RegistrySnapshot] = None):
        """Create a registry object.

        Args:
            session (Session): SQLAlchemy session.
            snapshot (Union[None, int, dict, RegistrySnapshot], optional):
                Snapshot to use. Defaults to None.
        """
        self.session = session
        if snapshot is None:
            self.snapshot = session.query(RegistrySnapshot).order_by(
                RegistrySnapshot.id.desc()).first()
            if self.snapshot is None:
                self.init({})
        elif isinstance(snapshot, dict):
            self.init(snapshot)
        elif isinstance(snapshot, int):
            self.snapshot = session.get(RegistrySnapshot, snapshot)
        elif isinstance(snapshot, RegistrySnapshot):
            self.snapshot = snapshot
        else:
            raise ValueError('Invalid snapshot type')
        self.updates = {}

    def search(self,
               pattern: str,
               depth: int = 1,
               sub_tree: Union[TreeRef, dict, None] = None,
               limit: Optional[int] = None,
               offset: int = 0) -> Generator[tuple[str, Any], None, None]:
        """Search for keys matching pattern.

        Args:
            pattern: A string pattern to match keys. The pattern can contain
                wildcards. For example, 'a.b.*.d' will match 'a.b.c.d' and
                'a.b.x.d'. The pattern can also contain index. For example,
                'a.b[0].d' will match 'a.b[0].d' but not 'a.b[1].d'.
            depth: The depth of the tree to return. For example, if depth is 0,
                only the leaf nodes will be returned. If depth is 1, the leaf
                nodes and the nodes with one depth of children will be returned.
                If depth is -1, the entire tree will be returned.
            limit: The maximum number of keys to return.
            offset: The offset of the first key to return.

        Returns:
            A generator that yields a tuple of the key and the value.
        """
        patterns = _parse_key(pattern)
        if sub_tree is None:
            root_id = self.snapshot.root_id
        else:
            root_id = sub_tree.id
        yield from search(self.session,
                          root_id,
                          patterns,
                          limit=limit,
                          offset=offset,
                          depth=depth)

    def get(self, key, depth=-1):
        """Get the value of a key.

        Args:
            key: The key to get the value of.

        Returns:
            The value of the key.
        """
        if depth >= 0:
            depth += 1
        for k, v in self.search(key, limit=1, offset=0, depth=depth):
            return v
        else:
            return None

    def set(self, key, value, lazy: bool = False):
        """Set a value in the registry.

        Args:
            key: The key to set.
            value: The value to set.
            lazy: If True, the value will be set only when the registry is
                committed.
        """
        self.updates = merge(self.updates,
                             foldDict({key: Update(UNKNOW, value)}))
        if not lazy:
            self.commit()

    def delete(self, key, lazy: bool = False):
        """Delete a key from the registry.

        Args:
            key: The key to delete.
            lazy: If True, the key will be deleted only when the registry is
                committed.
        """
        self.updates = merge(self.updates, foldDict({key: DELETE}))
        if not lazy:
            self.commit()

    def update(self, updates: dict, lazy: bool = False):
        """Update the registry.

        Args:
            updates: A dictionary of updates. The keys are the keys to update
                and the values are the values to set. If the value is DELETE,
                the key will be deleted.
            lazy: If True, the updates will be applied only when the registry
                is committed.
        """
        self.updates = merge(self.updates, {
            key: Create(value, replace=False)
            for key, value in updates.items()
        })
        if not lazy:
            self.commit()

    def commit(self):
        """Commit the updates to the registry."""
        root = _patch(self.session, self.snapshot.root_id, self.updates)
        snapshot = RegistrySnapshot(previous_id=self.snapshot.id)
        snapshot.root = root
        self.session.add(snapshot)
        try:
            self.session.commit()
        except:
            self.session.rollback()
            raise
        self.snapshot = snapshot
        self.updates.clear()

    def rollback(self):
        """Rollback the updates."""
        self.updates.clear()

    def init(self,
             value: Union[dict, RegistryNode] = None) -> RegistrySnapshot:
        value_cache = {}
        snapshot = RegistrySnapshot()
        if value is None:
            value = {}
        if isinstance(value, RegistryNode):
            snapshot.root = value
        else:
            snapshot.root = _create_node(self.session, value, value_cache)
        self.session.add(snapshot)
        try:
            self.session.commit()
        except:
            self.session.rollback()
            raise
        self.snapshot = snapshot

    def export(self, sub_tree: TreeRef = None, depth: int = -1):
        """Export the registry to a dictionary.

        Args:
            sub_tree: The sub-tree to export.
            depth: The depth of the tree to return. For example, if depth is 0,
                only the leaf nodes will be returned. If depth is 1, the leaf
                nodes and the nodes with one depth of children will be returned.
                If depth is -1, the entire tree will be returned.
        """
        if sub_tree is None:
            root_id = self.snapshot.root_id
        else:
            root_id = sub_tree.id
        return export(self.session, root_id, depth)

    def previous(self):
        """Get the previous snapshot."""
        return Registry(self.session, self.snapshot.previous)

    @staticmethod
    def from_file(path: str, snapshot: Optional[int] = None) -> Registry:
        """Create a registry from a file.

        Args:
            path: The path to the file.
            snapshot: The snapshot to use. If None, the latest snapshot will be
                used.
        """
        url = f'sqlite:///{path}'
        return Registry.from_url(url, snapshot)

    @staticmethod
    def from_url(url: str, snapshot: Optional[int] = None) -> Registry:
        """Create a registry from a URL.

        Args:
            url: The URL to the database.
            snapshot: The snapshot to use. If None, the latest snapshot will be
                used.
        """
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(url)
        Base.metadata.create_all(engine, checkfirst=True)
        Session = sessionmaker(bind=engine)
        session = Session()
        return Registry(session, snapshot)

    def __del__(self):
        self.session.close()
