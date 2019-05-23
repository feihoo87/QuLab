from mongoengine import (ComplexDateTimeField, Document, ListField,
                         ReferenceField, StringField)

from .base import now, update_modified


class CodeSnippet(Document):
    text = StringField()
    filename = StringField()
    created_time = ComplexDateTimeField(default=now)

    meta = {
        'indexes': [
            '#text',  # hashed index
        ]
    }

    def __repr__(self):
        return "< CodeSnippet(id='%s') >" % self.id


def createCodeSnippet(text, filename=None):
    c = CodeSnippet.objects(text=text).first()
    if c is None:
        c = CodeSnippet(text=text, filename=filename)
        c.save()
    return c


@update_modified.apply
class Notebook(Document):
    name = StringField()
    created_time = ComplexDateTimeField(default=now)
    modified_time = ComplexDateTimeField(default=now)
    inputCells = ListField(ReferenceField('CodeSnippet'))
