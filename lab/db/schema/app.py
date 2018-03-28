import warnings

from .base import *
from .code_mod import makeUniqueCodeSnippet, makeUniqueModule


class Application(Document):
    name = StringField(max_length=50)
    package = StringField(default='')
    author = ReferenceField('User')
    version = EmbeddedDocumentField(Version, default=Version())
    created_time = ComplexDateTimeField(default=now)
    discription = StringField()
    module = ReferenceField('Module')
    is_middle_layer = BooleanField(default=False)
    hidden = BooleanField(default=False)

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
            lastapp.hidden = True
            lastapp.save()
        appdata.save()

    if version is not None and version != appdata.version.text:
        appdata.version.text = version
        appdata.version.num += 1
        appdata.save()


def listApplication(package=''):
    ret = {}
    query = {'hidden': {'$ne': True}, 'is_middle_layer': {'$ne': True}}
    if package != '':
        query['package'] = {'$regex': r'^%s(\.\w+)*$' % package}

    for app in Application.objects(__raw__ = query).order_by('package'):
        if app.package != '':
            name = '%s.%s' % (app.package, app.name)
        else:
            name = app.name
        if name not in ret.keys() or ret[name].version.num < app.version.num:
            ret[name] = app
    return ret.values()
