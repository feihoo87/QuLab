import functools

from mongoengine import (BooleanField, ComplexDateTimeField, Document,
                         FileField, IntField, ListField, ReferenceField,
                         StringField, DictField, BinaryField)

from .base import delete_children, from_pickle, now, to_pickle, update_modified


@update_modified.apply
@delete_children.apply
class Record(Document):
    title = StringField(max_length=100)
    comment = StringField()
    created_time = ComplexDateTimeField(default=now)
    finished_time = ComplexDateTimeField(default=now)
    modified_time = ComplexDateTimeField(default=now)
    hidden = BooleanField(default=False)
    children = ListField(ReferenceField('Record'))
    config=DictField()
    setting=DictField()
    tags = ListField(StringField(max_length=50))
    datafield = FileField(collection_name='data')
    imagefield = FileField(collection_name='images')
    imagefields = ListField(BinaryField())
    work = ReferenceField('CodeSnippet')
    notebook = ReferenceField('Notebook')
    notebook_index = IntField(min_value=0)

    def __repr__(self):
        return 'Record(title=%s, finished_time=%s, tags=%s)' % (
            self.title, self.finished_time, self.tags)

    @property
    def data(self):
        return from_pickle(self.datafield)

    @property
    @functools.lru_cache(maxsize=1)
    def image(self):
        return from_pickle(self.imagefield)

    def set_data(self, obj, content_type='application/octet-stream'):
        if self.datafield is None:
            self.datafield.put(to_pickle(obj), content_type=content_type)
        else:
            self.datafield.replace(to_pickle(obj), content_type=content_type)

    def set_image(self, img, content_type='image/png'):
        if self.imagefield is None:
            self.imagefield.put(to_pickle(img), content_type=content_type)
        else:
            self.imagefield.replace(to_pickle(img), content_type=content_type)
