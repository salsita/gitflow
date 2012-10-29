.. -*- mode: rst ; ispell-local-dictionary: "american" -*-


git flow |BRANCH| publish - Publish a |BRANCH| branch to `origin`
=======================================================================


Synopsis
-----------

.. parsed-literal::

  `git flow` |`BRANCH`| `publish` [nameprefix]


Description
-----------

Publish a |BRANCH| branch, with the given name or name-prefix, on
``origin`` (or whatever is configured as ``remote`` for gitflow.)


If ``nameprefix`` is not given, publish the current branch if it is a
|BRANCH| branch.

If ``nameprefix`` is given and exactly one |BRANCH| branch starts with
``nameprefix``, publish that one.


Options
-----------

  -h, --help          Show help message and exit.
