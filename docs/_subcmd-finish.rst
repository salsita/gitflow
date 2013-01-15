.. -*- mode: rst ; ispell-local-dictionary: "american" -*-


git flow |BRANCH| finish - Finish a |BRANCH| branch
======================================================


Synopsis
-----------

.. parsed-literal::

  `git flow` |`BRANCH`| `finish` [-r|--rebase]
                    [-D|--force-delete] [nameprefix]


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
  -r, --rebase        Finish branch by rebasing first.
  -D, --force-delete  Force delete |BRANCH| branch after finish.
  -P, --no-push       Do not push to origin after performing finish.
  -n, --new-review    Post a new review (do not update an existing one).
