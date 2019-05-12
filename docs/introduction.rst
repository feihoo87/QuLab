Installation
============

We encourage installing QuLab via the pip tool (a python package manager)::

   $ python -m pip install QuLab

To install from the latest source, you need to clone the GitHub repository on your machine::

   $ git clone https://github.com/feihoo87/QuLab.git

Then dependencies and QuLab can be installed in this way::

   $ cd QuLab
   $ python -m pip install -r requirements.txt
   $ python -m pip install -e .

Usage
=====

Running Tests
=============
To run tests::

   $ python -m pip install -r requirements-dev.txt
   $ python -m pytest


Reporting Issues
================
Please report all issues `on github <https://github.com/feihoo87/QuLab/issues>`_.

License
=======

`MIT <https://opensource.org/licenses/MIT>`_
