import datetime
import io
import lzma
import pickle

from mongoengine import signals


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
    for child in document.children:
        child.delete()
