#!/usr/bin/env python
#
# This file is part of `gitflow`.
# Copyright (c) 2010-2011 Vincent Driessen
# Copyright (c) 2012 Hartmut Goebel
# Distributed under a BSD-like license. For full terms see the file LICENSE.txt
#

import os
import codecs
try:
    from setuptools import setup, find_packages
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

import gitflow as distmeta

long_description = codecs.open('README.rst', "r", "utf-8").read()

install_requires = [
    'colorama==0.2.5',
    'gitdb>=0.5.1',
    'GitPython>=0.3.2c1',
    'httplib2==0.8',
    'jenkinsapi==0.2.12',
    'poster==0.8.1',
    'python-dateutil',
    'rbtools==0.6.2',
    'setuptools',
    'simplejson==3.1.2',
    'xmlbuilder==1.0'
]

setup(
    name="salsita-gitflow",
    scripts=['bin/git-flow'],
    version=distmeta.__version__,
    description="Git extensions to provide high-level repository operations for Vincent Driessen's branching model.",
    author=distmeta.__author__,
    author_email=distmeta.__contact__,
    url=distmeta.__homepage__,
    platforms=["any"],
    license="BSD",
    packages=find_packages(),
    package_data={'':['gitflow/busyflow/pivotal/tzmap.txt']},
    include_package_data=True,
    install_requires=install_requires,
    zip_safe=False,
    classifiers=[
        # Picked from
        #    http://pypi.python.org/pypi?:action=list_classifiers
        #"Development Status :: 1 - Planning",
        #"Development Status :: 2 - Pre-Alpha",
        #"Development Status :: 3 - Alpha",
        "Development Status :: 4 - Beta",
        #"Development Status :: 5 - Production/Stable",
        #"Development Status :: 6 - Mature",
        #"Development Status :: 7 - Inactive",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Operating System :: POSIX",
        "Programming Language :: Python",
        "Topic :: Software Development :: Version Control",
    ],
    long_description=long_description,
)
