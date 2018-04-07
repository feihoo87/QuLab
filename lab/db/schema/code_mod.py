from .base import *


class CodeSnippet(Document):
    text = StringField()
    filename = StringField()
    author = ReferenceField('User')
    created_time = ComplexDateTimeField(default=now)

    meta = {
        'indexes': [
            '#text',  # hashed index
        ]
    }

    def __repr__(self):
        return "< CodeSnippet(id='%s', author='%s') >" % (self.id,
                                                          self.author.name)


def makeUniqueCodeSnippet(text, author):
    c = CodeSnippet.objects(text=text).first()
    if c is None:
        c = CodeSnippet(text=text, author=author)
        c.save()
    return c


class Module(Document):
    fullname = StringField()
    author = ReferenceField('User')
    is_package = BooleanField(default=False)
    source = ReferenceField('CodeSnippet')
    modules = ListField(ReferenceField('Module'))
    created_time = ComplexDateTimeField(default=now)

    def __repr__(self):
        return "< Module(id='%s', fullname='%s') >" % (self.id, self.fullname)


def getModuleByFullname(fullname, before=None):
    before = now() if before is None else before
    return Module.objects(
        fullname=fullname,
        created_time__lt=before).order_by('-created_time').first()


def makeUniqueModule(fullname, author, codeSnippet, sub_modules=[]):
    parentname = '.'.join(fullname.split('.')[:-1])
    parentmodule = getModuleByFullname(parentname)
    m = Module(
        fullname=fullname,
        author=author,
        is_package=False if len(sub_modules) == 0 else True,
        source=codeSnippet,
        modules=sub_modules)
    [mod.save() for mod in m.modules if mod.id is None]
    mlast = Module.objects(fullname=fullname).order_by('-created_time').first()
    if mlast is not None:
        if mlast.fullname == m.fullname and mlast.source == m.source and mlast.modules == m.modules:
            return mlast
    m.save()
    if parentmodule is not None:
        parentmodule.modules.append(m)
        parentmodule.is_package = True
        parentmodule.save()
    return m


def saveModule(fullname, text, author):
    m = makeUniqueModule(fullname, author, makeUniqueCodeSnippet(text, author))
    return m


def savePackage(fullname, author, init=None, modules=[]):
    m = makeUniqueModule(fullname, author,
                         makeUniqueCodeSnippet(init, author)
                         if init is not None else None, modules)
    if m.id is None:
        m.save()
    return m


def saveModuleFile(path, fullname=None, author=None):
    log.debug('save module %r as %r', path, fullname)
    name, ext = os.path.splitext(os.path.basename(path))
    if fullname is None:
        fullname = name
    if ext == '.py':
        with tokenize.open(path) as f:
            return saveModule(fullname, f.read(), author)
    else:
        return None


def savePackageFile(path, fullname=None, author=None):
    log.debug('save package %r as %r', path, fullname)
    if os.path.isfile(path):
        return saveModuleFile(path, fullname, author)
    elif os.path.isdir(path):
        submods = []
        init = None
        for file in os.listdir(path):
            subpath = os.path.join(path, file)
            name, _ = os.path.splitext(file)
            if os.path.isdir(subpath):
                submod = savePackageFile(subpath, '%s.%s' % (fullname, name), author)
                if submod is not None:
                    submods.append(submod)
            elif os.path.isfile(subpath):
                if file == '__init__.py':
                    with tokenize.open(subpath) as f:
                        init = f.read()
                else:
                    submods.append(
                        saveModuleFile(subpath, '%s.%s' % (fullname, name),
                                       author))
        return savePackage(fullname, author, init, submods)
    else:
        pass


@update_modified.apply
class Notebook(Document):
    name = StringField()
    author = ReferenceField('User')
    created_time = ComplexDateTimeField(default=now)
    modified_time = ComplexDateTimeField(default=now)
    inputCells = ListField(ReferenceField('CodeSnippet'))
