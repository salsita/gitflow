================
Salsita git-flow
================

Pure-Python implementation of Git extensions to provide high-level
repository operations for Vincent Driessen's
`branching model <http://nvie.com/git-model>`_.

We've added a few tweaks to make it cooperate with Pivotal Tracker and Review Board.


Getting started
================

For the best introduction to get started with ``git flow``, please read
Jeff Kreeftmeijer's blog post http://jeffkreeftmeijer.com/2010/why-arent-you-using-git-flow.

Or have a look at one of these screen casts:

* `How to use a scalable Git branching model called git-flow
  <http://buildamodule.com/video/change-management-and-version-control-deploying-releases-features-and-fixes-with-git-how-to-use-a-scalable-git-branching-model-called-gitflow>`_
  (by Build a Module)

* `A short introduction to git-flow <http://vimeo.com/16018419>`_
  (by Mark Derricutt)

* `On the path with git-flow
  <http://codesherpas.com/screencasts/on_the_path_gitflow.mov>`_
  (by Dave Bock)


Installing salsita-gitflow
==========================

You can install ``salsita gitflow``, using::

    pip install salsita-gitflow

Or, if you'd like to use ``easy_install`` instead::

    easy_install salsita-gitflow

``salsita-gitflow`` requires Python 2.7.

Setting it up
-------------
Global (same for all projects)::

* git config --global reviewboard.url https://example.com/rb/ (the trailing slash is REQUIRED)
* git config --global reviewboard.server https://example.com/rb/
* git config --global gitflow.pt.token 12345678910

You will be prompted for the project-specific settings during ``git flow init``.

If you have the original `git-flow <https://github.com/nvie/gitflow>` installed, just go to the git bin folder and delete everything that starts with ``git-flow``.


Integration with your shell
---------------------------

For those who use the `Bash <http://www.gnu.org/software/bash/>`_ or
`ZSH <http://www.zsh.org>`_ shell, please check out the excellent work
on the
`git-flow-completion <http://github.com/bobthecow/git-flow-completion>`_
project by `bobthecow <http://github.com/bobthecow>`_. It offers
tab-completion for all git-flow subcommands and branch names.

Please note that some subcommands have changed in this gitflow fork, so it is
questionable if the completions still make sense.

Please help out
===============

This project is still under development. Feedback and suggestions are
very welcome and I encourage you to use the `Issues list
<http://github.com/salsita/gitflow/issues>`_ on Github to provide that
feedback.

Feel free to fork this repo and to commit your additions. For a list
of all contributors, please see the :file:`AUTHORS.txt`.

Salsita is using `Gerrit <https://dev.salsitasoft.com/gerrit/#/q/status:open+project:gitflow,n,z>`_
for code review.

You will need :module:`unittest2` to run the tests (which are completely broken as of now, so nevermind).

On the cutting edge
===================

The source code here on GitHub is the one that has been code reviewed.
If you, however, wish to try the changes that are still yet to be reviewed,
you can visit `Gerrit <https://dev.salsitasoft.com/gerrit/#/q/status:open+project:gitflow,n,z>`_
and checkout the commit you want to try/test. If that is the case, we advice you to:

#. Use `virtualenv <https://pypi.python.org/pypi/virtualenv>`_ to create the testing environment.
#. Once the environment is activated, get the commit you want:

   #. ``mkdir src && cd src``
   #. ``git init``
   #. Go to the commit page in Gerrit, get the exact command to execute, e.g. ``git fetch https://dev.salsitasoft.com/gerrit/gitflow refs/changes/02/2/1 && git checkout FETCH_HEAD``
   #. ``python setup.py install``
   #. The git flow commands should be available to you now, just make sure you are using the right one (``man which``)

License terms
==================

git-flow is published under the liberal terms of the BSD License, see
the :file:`LICENSE.txt`. Although the BSD License does not
require you to share any modifications you make to the source code,
you are very much encouraged and invited to contribute back your
modifications to the community, preferably in a Github fork, of
course.


git flow usage
==============

Initialization
--------------

**Before you start, make sure that you are using SSH for communication with origin.**

To initialize a new repo with the basic branch structure, use::
  
    git flow init [-d]
  
This will then interactively prompt you with some questions on which
branches you would like to use as development and production branches,
and how you would like your prefixes be named. You may simply press
Return on any of those questions to accept the (sane) default
suggestions.

The ``-d`` flag will accept all defaults.

Note: Please use the ``-d`` flag it will make your life much easier.

init will also check your git config to see if the required records for
Review Board and Pivotal Tracker are in place, failing if that is not the case.

Creating feature/release/hotfix/support branches
----------------------------------------------------

The list of command line flags listed here is not complete. Check the wiki for
a more complete list. The best documentation is, however,::

      git flow <subcmd> <subsubcmd> -h

* To list/start/finish feature branches, use::
  
      git flow feature
      git flow feature start [--for-release RELEASE]
      git flow feature finish [<name>]
  
  ``feature start`` will list unstarted & started stories from
  current & backlog iterations in Pivotal Tracker. Select one and its state
  will change to `started`. This command creates a feature branch as well, so
  switch between stories using ``git checkout``, not ``git flow feature start``.
  If you wish to base your story on a release branch,
  use ``--for-release RELEASE``. This will also assign the story in Pivotal
  Tracker as a part of starting it.

  ``feature finish`` will finish the currently active story (merge it into
  `develop`, push develop, change the story state in PT to `finished` and
  post a review request to Pivotal Tracker). It will do its best to find
  the corersponding review request in ReviewBoard and update the review but
  if it can't then it will post a new review. You can force posting a new
  review by setting the ``-n/--new-review`` flag.

* To push/pull a feature branch to the remote repository, use::

      git flow feature publish <name>
      git flow feature pull <remote> <name>

* To list/start/finish release branches, use::
  
      git flow release
      git flow release start <major.minor.release> [<base>]
      git flow release finish [-R|--ignore-missing-reviews] [<major.minor.release>]
  
  If you are not using Review Board for your project, you can use
  ``-R`` or ``--ignore-missing-reviews`` to skip the reviews check while doing
  a release.

* To list/start/finish hotfix branches (not supported by Salsita), use::
  
      git flow hotfix
      git flow hotfix start <release> [<base>]
      git flow hotfix finish <release>

* To list/start support branches (not supported by Salsita), use::
  
      git flow support
      git flow support start <release> <base>
  
  For support branches, the ``<base>`` arg must be a commit on ``master``.

Demo
----

A small demo how a complete feature implementation could look like::

    $ git config --global reviewboard.server https://example.com/rb/
    $ git config --global reviewboard.url https://example.com/rb/
    $ git config --global workflow.token 0123456789
    $ mkdir project
    $ cd project
    $ git remote add origin git@github.com:salsita/project.git
    $ git pull
    $ git flow init -d # Pick the project from PT and the repo from RB.
    $ git checkout develop
    $ git flow feature start # Pick the story from PT.
    # Code code code
    $ git add *
    $ git commit -s
    # Enter a beautiful and descriptive commit message.
    $ git flow feature finish
    # Go to the Review Board to submit the generated review request.
    # PROFIT!

History of the Project
=========================

gitflow was originally developed by Vincent Driessen as a set of
shell-scripts. In Juni 2007 he started a Python rewrite but did not
finish it. In February 2012 Hartmut Goebel started completing the
Python rewrite and asked Vincent to pull his changes. But in June 2012
Vincent closed the pull-request and deleted his ``python-rewrite``
branch. So Hartmut decided to release the Python rewrite on his own.


Showing your appreciation to the original authors
=================================================

Of course, the best way to show your appreciation for the git-flow
tool itself remains contributing to the community. If you'd like to
show your appreciation in another way, however, consider donating
to the original authors through PayPal: |Donate|_


.. |Donate| image:: https://www.paypalobjects.com/en_US/i/btn/btn_donate_SM.gif
.. _Donate: https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=8PS63EM4XPFDY&item_name=gitflow%20donation&no_note=0&cn=Some%20kind%20words%20to%20the%20author%3a&no_shipping=1&rm=1&return=https%3a%2f%2fgithub%2ecom%2fhtgoebel%2fgitflow&cancel_return=https%3a%2f%2fgithub%2ecom%2fhtgoebel%2fgitflow&currency_code=EUR
