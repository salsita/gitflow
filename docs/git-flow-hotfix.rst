.. -*- mode: rst ; ispell-local-dictionary: "american" -*-

.. include:: _manpage-header.rst

==========================
git flow hotfix
==========================
.. |BRANCH| replace:: hotfix
.. |`BRANCH`| replace:: `hotfix`
.. |BASE| replace:: `master`


Manage your |BRANCH| branches
#################################

Synopsis
+++++++++++++++

.. parsed-literal::

  `git flow` |`BRANCH`| [-h|--help]
  `git flow` |`BRANCH`| `list` [-v|--verbose]
  `git flow` |`BRANCH`| `start` [-F|--fetch] version [base]
  `git flow` |`BRANCH`| `finish` [-F|--fetch] [-p|--push] [-k|--keep]
                    [-n|--notag] [-m MESSAGE|--message MESSAGE]
                    [-s|--sign] [-u SIGNINGKEY|--signingkey SIGNINGKEY]
                    [version]
  `git flow` |`BRANCH`| `publish` [version]


.. contents:: Subcommands
    :depth: 1
    :local:

.. include:: _subcmd-list.rst
.. include:: _subcmd-start_version.rst
.. include:: _subcmd-finish_version.rst
.. include:: _subcmd-publish_version.rst


.. include:: _manpage-footer.rst
