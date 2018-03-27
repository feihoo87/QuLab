import datetime
import functools
import io
import logging
import lzma
import os
import pickle
import tokenize
import warnings

import gridfs
from mongoengine import (BooleanField, ComplexDateTimeField, DictField,
                         Document, DynamicDocument, DynamicField, EmailField,
                         EmbeddedDocument, EmbeddedDocumentField,
                         EmbeddedDocumentListField, FileField, ImageField,
                         IntField, ListField, ReferenceField, StringField,
                         signals)
from mongoengine.connection import get_db

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


def now():
    return datetime.datetime.now()


def to_pickle(obj):
    buff = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
    cbuff = lzma.compress(buff, format=lzma.FORMAT_XZ)
    return io.BytesIO(cbuff)


def from_pickle(buff):
    return pickle.loads(lzma.decompress(buff.read(), format=lzma.FORMAT_XZ))


def handler(event):
    """Signal decorator to allow use of callback functions as class decorators."""

    def decorator(fn):
        def apply(cls):
            event.connect(fn, sender=cls)
            return cls

        fn.apply = apply
        return fn

    return decorator


@handler(signals.pre_save)
def update_modified(sender, document, **kwargs):
    if kwargs.get('finished', False):
        document.finished_time = now()
    document.modified_time = now()


@handler(signals.pre_delete)
def delete_children(sender, document):
    for attrname in ['datafield']:
        attr = getattr(document, attrname, None)
        if attr is not None:
            attr.delete()
    # if hasattr(document, 'datafield') and document.datafield is not None:
    #    document.datafield.delete()
    for child in document.children:
        child.delete()


class Version(EmbeddedDocument):
    major = IntField(default=0)
    minor = IntField(default=0)
    micro = IntField(default=1)
    num = IntField(default=1)

    @property
    def text(self):
        return '%d.%d.%d' % (self.major, self.minor, self.micro)

    @text.setter
    def text(self, tag):
        nums = [int(s) for s in tag.split('.')]
        self.major = nums[0]
        self.minor = nums[1] if len(nums) > 1 else 0
        self.micro = nums[2] if len(nums) > 2 else 0

    def __iadd__(self, num):
        self.num += num
        self.micro += num
