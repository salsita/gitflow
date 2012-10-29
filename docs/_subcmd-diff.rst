.. -*- mode: rst ; ispell-local-dictionary: "american" -*-


git flow |BRANCH| diff - Show a diff since this |BRANCH| branched off
=======================================================================


Synopsis
-----------

.. parsed-literal::

  `git flow` |`BRANCH`| `diff` [nameprefix]


Description
-----------

Show all changes since this |BRANCH| branched off from |BASE|.

If ``nameprefix`` is not given, diff the current branch if it is a
|BRANCH| branch.

If ``nameprefix`` is given and exactly one |BRANCH| branch starts with
``nameprefix``, diff that one.


Options
-----------

  -h, --help          Show help message and exit.
