import platform
from codecs import open
from os import getcwd, getenv, listdir, path

from setuptools import find_packages, setup

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()


def dirtree(p):
    flist = []
    for f in listdir(p):
        if path.isdir(path.join(p, f)):
            flist.extend([path.join(f, item) for
                item in dirtree(path.join(p, f))])
        else:
            flist.append(f)
    return flist

driverFiles = [
    path.join('drivers', f) for f in dirtree(path.join(here, 'drivers'))]

# This reads the __version__ variable from lab/_version.py
exec(open('lab/_version.py').read())

requirements = [
    'numpy>=1.13.3',
    'scipy>=1.0.0',
    'matplotlib>=2.1.0',
    'jupyter>=1.0.0',
    'requests>=2.18.4',
    'tornado>=4.5.2',
    'mongoengine>=0.15.0',
    'blinker>=1.4',
    'pyvisa>=1.8',
    'pyvisa-py>=0.2',
    'PyYAML>=3.12'
]

setup(
    name="QuLab",
    version=__version__,
    author="feihoo87",
    author_email="feihoo87@gmail.com",
    url="https://github.com/feihoo87/QuLab",
    license = "MIT",
    keywords="experiment laboratory",
    description="contral instruments and manage data",
    long_description=long_description,
    packages = find_packages(),
    include_package_data = True,
    data_files=[('QuLab/Drivers', driverFiles)],
    install_requires=requirements,
    python_requires='>=3.6',
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Pick your license as you wish (should match "license" above)
         'License :: OSI Approved :: MIT License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 3.6',
    ],
    project_urls={  # Optional
        'Bug Reports': 'https://github.com/feihoo87/QuLab/issues',
        'Source': 'https://github.com/feihoo87/QuLab/',
    },
)
