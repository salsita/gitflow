.. -*- mode: rst ; ispell-local-dictionary: "american" -*-

.. include:: _manpage-header.rst

==========================
git flow feature
==========================
.. |BRANCH| replace:: feature
.. |`BRANCH`| replace:: `feature`
.. |BASE| replace:: `develop`


Manage your |BRANCH| branches
#################################

Synopsis
+++++++++++++++

.. parsed-literal::

  `git flow` |`BRANCH`| [-h|--help]
  `git flow` |`BRANCH`| `list` [-v|--verbose]
  `git flow` |`BRANCH`| `finish` [-F|--fetch] [-r|--rebase]
                    [-k|--keep] [-D|--force-delete] [nameprefix]
  `git flow` |`BRANCH`| `checkout` nameprefix
  `git flow` |`BRANCH`| `diff` [nameprefix]
  `git flow` |`BRANCH`| `rebase` [nameprefix]
  `git flow` |`BRANCH`| `publish` [nameprefix]
  `git flow` |`BRANCH`| `pull` remote [name]
  `git flow` |`BRANCH`| `track` name


.. contents:: Subcommands
    :depth: 1
    :local:

.. include:: _subcmd-list.rst
.. include:: _subcmd-start.rst
.. include:: _subcmd-finish.rst
.. include:: _subcmd-checkout.rst
.. include:: _subcmd-diff.rst
.. include:: _subcmd-rebase.rst
.. include:: _subcmd-publish.rst
.. include:: _subcmd-pull.rst
.. include:: _subcmd-track.rst


.. include:: _manpage-footer.rst
