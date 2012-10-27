.. -*- mode: rst ; ispell-local-dictionary: "american" -*-


git flow |BRANCH| rebase - Rebase a |BRANCH| branch on top of |BASE|
=======================================================================


Synopsis
-----------

``git flow |BRANCH| rebase`` [-h] [nameprefix]


Description
-----------

Rebase a |BRANCH| branch on top of |BASE| (or whatever is configured
as |BASE| for gitflow.)

If `nameprefix` is not given, rebase the current branch if it is a
|BRANCH| branch.

If `nameprefix` is given and exactly one |BRANCH| branch starts with
`nameprefix`, rebase that one.


Options
-----------

  -h, --help         Show help message and exit.
  -i, --interactive  Start an interactive rebase.
