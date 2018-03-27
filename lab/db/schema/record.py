import functools

from .app import getApplication
from .base import *


@update_modified.apply
@delete_children.apply
class Record(Document):
    title = StringField(max_length=50)
    comment = StringField()
    created_time = ComplexDateTimeField(default=now)
    finished_time = ComplexDateTimeField(default=now)
    modified_time = ComplexDateTimeField(default=now)
    hidden = BooleanField(default=False)
    app = ReferenceField('Application')
    user = ReferenceField('User')
    project = ReferenceField('Project')
    samples = ListField(ReferenceField('Sample'))
    children = ListField(ReferenceField('Record'))
    tags = ListField(StringField(max_length=50))
    settings = DictField()
    rc = DictField()
    params = DictField()
    datafield = FileField(collection_name='data')

    def __repr__(self):
        return 'Record(title=%s, finished_time=%s, params=%s)' % (
            self.title, self.finished_time, self.params)

    @property
    @functools.lru_cache(maxsize=1)
    def data(self):
        return from_pickle(self.datafield)

    @data.setter
    def data(self, obj):
        if self.datafield is None:
            self.datafield.put(
                to_pickle(obj), content_type='application/octet-stream')
        else:
            self.datafield.replace(
                to_pickle(obj), content_type='application/octet-stream')
        # self.save()

def newRecord(**kwds):
    return Record(**kwds)

@update_modified.apply
class Report(DynamicDocument):
    title = StringField(max_length=50)
    records = ListField(ReferenceField('Record'))
    created_time = ComplexDateTimeField(default=now)
    modified_time = ComplexDateTimeField(default=now)


class Project(Document):
    name = StringField(max_length=50)
    created_time = ComplexDateTimeField(default=now)
    comment = StringField()

    @property
    def records(self):
        return Record.objects(project=self)


class Sample(Document):
    name = StringField(max_length=50)
    discription = StringField()
    images = ListField(FileField(collection_name='images'))

    @property
    def _imageFS(self):
        return gridfs.GridFS(get_db(), collection='images')

    @property
    def collection(self):
        return get_db()[self._get_collection_name()]

    @property
    def DBObject(self):
        return self.collection.find_one({'_id': self.id})

    def appendFile(self, data, filename, content_type):
        fid = self._imageFS.put(
            data, filename=filename, version=1, content_type=content_type)
        if self.id is None:
            self.save()
        files = self.DBObject['images']
        files.append(fid)
        self.collection.update({'_id': self.id}, {"$set": {'images': files}})

    def replaceFile(self, data, filename, content_type):
        files = self.DBObject['images']
        filenames = [f.filename for f in self.files]
        if not filename in filenames:
            return
        i = filenames.index(filename)
        oldfid = files[i]
        if self._imageFS.get(oldfid).read() == data:
            return
        files[i] = self._imageFS.put(
            data,
            filename=filename,
            version=self.files[i].version + 1,
            content_type=content_type)
        self.collection.update({'_id': self.id}, {"$set": {'images': files}})
        self._imageFS.delete(oldfid)


def query_records_by_app_name(app_name, show_hidden=False, version=None):
    rec_q = {'app__in': []}
    for app in getApplication(name=app_name, version=version, many=True):
        rec_q['app__in'].append(app)
    if not show_hidden:
        rec_q['hidden'] = False
    return Record.objects(**rec_q).order_by('-finished_time')


def query_records(q=None, app=None, show_hidden=False, **kwds):
    if q is not None:
        return Record.objects(q).order_by('-finished_time')
    else:
        if app is not None:
            if isinstance(app, str):
                return query_by_app_name(app, show_hidden, version=kwds.pop('version', None))
            elif hasattr(app, '__DBDocument__'):
                kwds['app'] = app.__DBDocument__
            elif isinstance(app, _schema.Application):
                kwds['app'] = app
        if not show_hidden:
            kwds['hidden'] = False
        return Record.objects(**kwds).order_by('-finished_time')
