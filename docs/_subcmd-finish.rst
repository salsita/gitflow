.. -*- mode: rst ; ispell-local-dictionary: "american" -*-


git flow |BRANCH| finish - Finish a |BRANCH| branch
======================================================


Synopsis
-----------

.. parsed-literal::

  `git flow` |`BRANCH`| `finish` [-F|--fetch] [-r|--rebase]
                    [-k|--keep] [-D|--force-delete] [nameprefix]


Description
-----------

Finish an existing |BRANCH| branch.

If ``nameprefix`` is not given, finish the current branch if it is a
|BRANCH| branch.

If ``nameprefix`` is given and exactly one |BRANCH| branch starts with
``nameprefix``, finish that one.



Options
-----------

  -h, --help          Show help message and exit.
  -F, --fetch         Fetch from origin before performing local operation.
  -r, --rebase        Finish branch by rebasing first.
  -k, --keep          Keep branch after performing finish.
  -D, --force-delete  Force delete |BRANCH| branch after finish.
