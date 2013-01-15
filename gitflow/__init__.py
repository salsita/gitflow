"""
git-flow -- A collection of Git extensions to provide high-level
repository operations for Vincent Driessen's branching model.
"""
#
# This file is part of `gitflow`.
# Copyright (c) 2010-2011 Vincent Driessen
# Copyright (c) 2012 Hartmut Goebel
# Distributed under a BSD-like license. For full terms see the file LICENSE.txt
#

VERSION = (0, 6, 10, 'dev')

__version__ = ".".join(map(str, VERSION[0:3])) + "".join(VERSION[3:])
__author__ = "Tomas Brambora, Hartmut Goebelm, Vincent Driessen"
__contact__ = "tomas@salsitasoft.com, h.goebel@crazy-compilers.com, vincent@datafox.nl"
__homepage__ = "http://github.com/salsita/gitflow/"
__docformat__ = "restructuredtext"
__copyright__ = "2010-2011 Vincent Driessen; 2012 Hartmut Goebel; 2013 Tomas Brambora"
__license__ = "BSD"
