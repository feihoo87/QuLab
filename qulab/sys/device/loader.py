import importlib
from pathlib import Path
from typing import Type

from .basedevice import BaseDevice

path = {}


def _make_device(module, args, kwds) -> BaseDevice:
    importlib.reload(module)
    try:
        return module.device(*args, **kwds)
    except AttributeError:
        return module.Device(*args, **kwds)


def create_device_from_file(filepath: str | Path, package_name: str, args,
                            kwds) -> BaseDevice:
    """
    Create a device from a file.

    Parameters
    ----------
    filepath : str | Path
        The path to the driver file.
    package_name : str
        The name of the package in which .filepath is located.
    args : tuple
        The positional arguments to pass to the device maker.
    kwds : dict
        The keyword arguments to pass to the device maker.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise RuntimeError(f"File {filepath} does not exist")
    module_name = f"{package_name}.{filepath.stem}"
    spec = importlib.util.spec_from_file_location(module_name, filepath)
    module = importlib.util.module_from_spec(spec)
    return _make_device(module, args, kwds)


def create_device_from_module(module_name: str, args, kwds) -> BaseDevice:
    """
    Create a device from a module.

    Parameters
    ----------
    module_name : str
        The name of the module to import.
    args : tuple
        The positional arguments to pass to the device maker.
    kwds : dict
        The keyword arguments to pass to the device maker.
    """
    module = importlib.import_module(module_name)
    return _make_device(module, args, kwds)


def create_device(driver_name: str, *args, **kwds) -> BaseDevice:
    """
    Create a device from a driver.

    Parameters
    ----------
    driver_name : str
        The name of the driver to use.
    args : tuple
        The positional arguments to pass to the device maker.
    kwds : dict
        The keyword arguments to pass to the device maker.
    """
    try:
        for package_name, p in path.items():
            try:
                dev = create_device_from_file(
                    Path(p) / f"{driver_name}.py", package_name, args, kwds)
                return dev
            except:
                pass

        dev = create_device_from_module(f"waveforms.sys.drivers.{driver_name}",
                                        args, kwds)
        return dev
    except:
        raise RuntimeError(f"Can not find driver {driver_name!r}")
