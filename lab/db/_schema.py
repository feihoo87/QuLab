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
                         EmbeddedDocument, EmbeddedDocumentField, FileField,
                         ImageField, IntField, ListField, ReferenceField,
                         StringField, signals)
from mongoengine.connection import get_db
from notebook.auth.security import passwd, passwd_check

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


def beforeSaveFile(fname):
    '''makesure the path exists before save file'''
    dirname = os.path.dirname(fname)
    if not os.path.exists(dirname):
        os.makedirs(dirname)


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


class User(Document):
    name = StringField(max_length=50, unique=True)
    email = EmailField(unique=True)
    fullname = StringField(max_length=50)
    hashed_passphrase = StringField(max_length=84)
    roles = ListField(ReferenceField('Role'))

    @property
    def password(self):
        return self.hashed_passphrase

    @password.setter
    def password(self, passphrase):
        self.hashed_passphrase = passwd(passphrase, algorithm='sha256')

    def check_password(self, passphrase):
        return passwd_check(self.hashed_passphrase, passphrase)

    def __repr__(self):
        return "User(name='%s', email='%s', fullname='%s')" % (self.name,
                                                               self.email,
                                                               self.fullname)


class Role(Document):
    name = StringField()


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
    return m


def saveModule(fullname, text, author):
    m = makeUniqueModule(fullname, author, makeUniqueCodeSnippet(text, author))
    if m.id is None:
        m.save()
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


class Application(Document):
    name = StringField(max_length=50)
    package = StringField(default='')
    author = ReferenceField('User')
    version = EmbeddedDocumentField(Version, default=Version())
    created_time = ComplexDateTimeField(default=now)
    discription = StringField()
    module = ReferenceField('Module')

    @property
    def source(self):
        if self.module is not None and self.module.source is not None:
            return self.module.source.text
        else:
            return ''

    @property
    def fullname(self):
        if self.package == '':
            return self.name
        else:
            return '%s.%s' % (self.package, self.name)

    def __str__(self):
        return 'App %s v%s by (%s, %s)' % (self.fullname,
            self.version.text, self.author.fullname,
            self.created_time.strftime('%Y-%m-%d %H:%M:%S'))


def __get_App_name_and_package(name, package):
    path = package.split('.') if package != '' else []
    path.extend(name.split('.'))
    name, package = path[-1], '.'.join(path[:-1])
    return name, package


def getApplication(name='', package='', version=None, id=None, many=False, **kwds):
    name, package = __get_App_name_and_package(name, package)
    kwds['name'] = name
    kwds['package'] = package
    if id is not None:
        kwds = {'id': id}
    elif isinstance(version, str):
        try:
            nums = [int(s) for version in tag.split('.')]
            kwds['version.major'] = nums[0]
            if len(nums) > 1:
                kwds['version.minor'] = nums[0]
            if len(nums) > 2:
                kwds['version.micro'] = nums[2]
        except:
            warnings.warn('illegal argument: version=%r' % version, UserWarning)
    elif isinstance(version, int):
        kwds['version.num'] = version
    if many:
        return Application.objects(**kwds).order_by('-version.num')
    else:
        return Application.objects(**kwds).order_by('-version.num').first()


def saveApplication(name,
                    source,
                    author,
                    package='',
                    discription='',
                    version=None):
    codeSnippet = makeUniqueCodeSnippet(source, author)
    name, package = __get_App_name_and_package(name, package)

    fullname = 'lab.apps.codeID%s' % codeSnippet.id

    module = makeUniqueModule(fullname, author, codeSnippet)
    if module.id is None:
        module.save()
    appdata = Application.objects(name=name, package=package, module=module).first()
    if appdata is None:
        lastapp = Application.objects(name=name).order_by('-version.num').first()
        appdata = Application(
            name=name,
            package=package,
            author=author,
            discription=discription,
            module=module)
        if lastapp is not None:
            appdata.version.major = lastapp.version.major
            appdata.version.minor = lastapp.version.minor
            appdata.version.micro = lastapp.version.micro + 1
            appdata.version.num = lastapp.version.num + 1
        appdata.save()

    if version is not None and version != appdata.version.text:
        appdata.version.text = version
        appdata.version.num += 1
        appdata.save()


def listApplication(package=''):
    ret = {}
    query = {}
    if package != '':
        query['package__istartswith']=package

    for app in Application.objects(**query).order_by('package'):
        if app.package != '':
            name = '%s.%s' % (app.package, app.name)
        else:
            name = app.name
        if name not in ret.keys() or ret[name].version.num < app.version.num:
            ret[name] = app
    return ret


@update_modified.apply
class Driver(Document):
    name = StringField(max_length=50, unique=True)
    version = IntField(default=0)
    created_time = ComplexDateTimeField(default=now)
    modified_time = ComplexDateTimeField(default=now)
    module = ReferenceField('Module')


def uploadDriver(path, author=None):
    module_name, _ = os.path.splitext(os.path.basename(path))
    fullname = 'lab.drivers.%s' % module_name
    module = savePackageFile(path, fullname, author)
    driver = Driver.objects(name=module_name).order_by('-version').first()
    if driver is None:
        driver = Driver(name=module_name, version=1, module=module)
    else:
        driver.module = module
        driver.version += 1
    driver.save()


class Instrument(Document):
    name = StringField(max_length=50, unique=True)
    host = StringField()
    address = StringField()
    driver = ReferenceField('Driver')
    created_time = ComplexDateTimeField(default=now)


def setInstrument(name, host, address, driver):
    driver = Driver.objects(name=driver).order_by('-version').first()
    if driver is None:
        raise Exception('Driver %r not exists, upload it first.' % driver)
    ins = Instrument.objects(name=name).first()
    if ins is None:
        ins = Instrument(name=name, host=host, address=address, driver=driver)
    else:
        ins.host = host
        ins.address = address
        ins.driver = driver
    ins.save()


def getInstrumentByName(name):
    return Instrument.objects(name=name).first()
