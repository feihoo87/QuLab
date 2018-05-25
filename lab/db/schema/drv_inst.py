from .base import *
from .code_mod import savePackageFile


@update_modified.apply
class Driver(Document):
    name = StringField(max_length=50, unique=True)
    version = IntField(default=0)
    created_time = ComplexDateTimeField(default=now)
    modified_time = ComplexDateTimeField(default=now)
    module = ReferenceField('Module')


def uploadDriver(path, author=None):
    module_name, _ = os.path.splitext(os.path.basename(path))
    fullname = 'qulab.drivers.%s' % module_name
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
