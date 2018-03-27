import datetime
import importlib
import logging
import os
import sys

from lab.config import caches_dir

from . import db

#log = logging.getLogger('qulab.core.importer')
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


class Finder(importlib.abc.MetaPathFinder):

    def __init__(self, before=None):
        self._before = before

    def before(self, before):
        self._before = before

    def find_spec(self, fullname, path=None, target=None):
        log.debug("find_spec: fullname=%r, path=%r, target=%r",
                  fullname, path, target)
        module_data = db.query.getModuleByFullname(fullname, self._before)
        if module_data is not None:
            log.debug("find_spec: module %r found", fullname)
            loader = ModuleLoader(module_data)
            return importlib.util.spec_from_loader(fullname, loader)
        else:
            log.debug("find_spec: module %r not found", fullname)
            return None


class ModuleLoader(importlib.abc.FileLoader, importlib.abc.SourceLoader):
    def __init__(self, module_data):
        self._data = module_data
        self._is_package = module_data.is_package

    def is_package(self, fullname):
        return self._is_package

    def get_filename(self, fullname):
        filename = self._data.fullname.split('.')
        if self.is_package(fullname):
            filename.append('__init__.py')
        else:
            filename[-1] = '%s.py' % filename[-1]
        filename.insert(0, str(self._data.id))
        return "db://id-%s" % '/'.join(filename)

    # def get_source(self, fullname):
    #    print('get_source', fullname)
    #    fullname = self._data.fullname
    #    if self._data.source is None:
    #        for mod in self._data.modules:
    #            if mod.fullname.find(fullname) == 0 and mod.fullname[len(fullname):] == '.__init__':
    #                if mod.source is None:
    #                    return ''
    #                else:
    #                    return mod.source.text
    #        return ''
    #    else:
    #        return self._data.source.text

    def get_data(self, path):
        fullname = self._data.fullname
        source = ''
        if self._data.source is None:
            if self.is_package():
                log.debug(
                    "get_data: try to find %r.__init__ in sub_modules", fullname)
                for mod in self._data.modules:
                    if mod.fullname.find(fullname) == 0 and mod.fullname[len(fullname):] == '.__init__':
                        log.debug("get_data: %r.__init__ found", fullname)
                        if mod.source is not None:
                            source = mod.source.text
                        break
                else:
                    log.debug("get_data: __init__ not found")
        else:
            source = self._data.source.text
        return source.encode()


_installed_meta_cache = {}


def install_meta(before=None):
    key = 'default' if before is None else before
    if key not in _installed_meta_cache:
        finder = Finder(before)
        _installed_meta_cache[key] = finder
        for i, v in enumerate(sys.meta_path):
            if isinstance(v, Finder):
                sys.meta_path.insert(i, finder)
                break
        else:
            sys.meta_path.append(finder)
        log.debug('%r installed on sys.meta_path', finder)


def remove_meta(before=None):
    key = 'default' if before is None else before
    if key in _installed_meta_cache:
        finder = _installed_meta_cache.pop(key)
        sys.meta_path.remove(finder)
        log.debug('%r removed from sys.meta_path', finder)
