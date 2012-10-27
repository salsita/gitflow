.. -*- mode: rst ; ispell-local-dictionary: "american" -*-


git flow |BRANCH| finish - Finish a |BRANCH| branch
======================================================


Synopsis
-----------

``git flow |BRANCH| finish`` [-h] [-F] [-p] [-k] [-n] [-m MESSAGE] [-s]
                             [-u SIGNINGKEY]
                             [version]


Description
-----------

Finish an existing |BRANCH| branch.


Positional arguments
-----------------------

  :version:   Version of the |BRANCH| branch to publish. Defaults to
              the current branch, if it is a |BRANCH| branch.


Options
-----------

  -h, --help          Show help message and exit.
  -F, --fetch         Fetch from origin before performing local operation.
  -p, --push          Push to origin after performing finish.
  -k, --keep          Keep branch after performing finish.

Tagging Options
~~~~~~~~~~~~~~~~~

  -n, --notag           Don't tag this release.
  -m MESSAGE, --message MESSAGE
                        Use the given tag message.
  -s, --sign            Sign the release tag cryptographically.
  -u SIGNINGKEY, --signingkey SIGNINGKEY
                        Use the given GPG-key for the digital signature
                        instead of the default git uses (implies -s).
