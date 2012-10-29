.. -*- mode: rst ; ispell-local-dictionary: "american" -*-


git flow |BRANCH| publish - Publish a |BRANCH| branch to `origin`
=======================================================================


Synopsis
-----------

.. parsed-literal::

  `git flow` |`BRANCH`| `publish` [version]


Description
-----------

Publish a |BRANCH| branch, with the given version, on ``origin`` (or
whatever is configured as ``remote`` for gitflow.)


Positional arguments
-----------------------

  :version:   Version of the |BRANCH| branch to publish. Defaults to
              the current branch, if it is a |BRANCH| branch.


Options
-----------

  -h, --help          Show help message and exit.
