from setuptools import find_packages, setup

# This reads the __version__ variable from lab/_version.py
exec(open('lab/_version.py').read())

requirements = [
    'numpy>=1.13.3', 'scipy>=1.0.0', 'matplotlib>=2.1.0', 'jupyter>=1.0.0',
    'ipywidgets>=7.0.5', 'requests>=2.18.4', 'tornado>=4.5.2',
    'mongoengine>=0.15.0', 'scikit-rf>=0.14.5', 'pyvisa>=1.8', 'pyvisa-py>=0.2']

# Readme file as long_description:
long_description = open('README.md','rb').read().decode('utf-8')

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
)
