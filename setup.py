import platform
from codecs import open
from os import getcwd, getenv, listdir, path

from setuptools import find_packages, setup

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# This reads the __version__ variable from lab/_version.py
exec(open('qulab/_version.py').read())

requirements = [
    'cryptography>=2.6.1',
    'numpy>=1.13.3',
    'scipy>=1.0.0',
    'PyYAML>=5.1',
]

if platform.system() == 'Windows':
    requirements.extend([
        'pywin32>=224'
    ])

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
    #data_files=[('QuLab/Drivers', driverFiles)],
    install_requires=requirements,
    extras_require={
        'test': [
            'pytest>=4.4.0',
        ],
        'docs': [
            'Sphinx',
            'sphinxcontrib-napoleon',
            'sphinxcontrib-zopeext',
        ],
    },
    python_requires='>=3.6',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX :: Linux',
        'Operating System :: MacOS :: MacOS X',
        'Topic :: Scientific/Engineering :: Interface Engine/Protocol Translator',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    project_urls={  # Optional
        'Bug Reports': 'https://github.com/feihoo87/QuLab/issues',
        'Source': 'https://github.com/feihoo87/QuLab/',
    },
)
