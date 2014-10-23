================
Salsita git-flow
================

Pure-Python implementation of Git extensions to provide high-level
repository operations for Vincent Driessen's
`branching model <http://nvie.com/git-model>`_.

We've added a few tweaks to make it cooperate with Pivotal Tracker, Review Board and Jenkins.


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

Salsita GitFlow basically follows the same guidelines, it just interacts with some other tools as well.
Features are tied to Pivotal Tracker stories and Review Board review requests. Here is a quick summary
of how it works:

* ``feature start`` lets you choose a Pivotal Tracker story to be started.
* ``feature finish`` finishes the PT story and posts the feature diff into Review Board. You can call ``feature finish`` multiple times and it will detect existing review request and update it. Every time you run ``feature finish``, the assocciated Jenkins doploy job is triggered and the develop branch is deployed to the develop environment.
* ``release start`` adds labels to the currently finished Pivotal Tracker stories, thus assigning them to the release of your choice. The newly created release branch is deployed to the QA environment so that it can be tested.
* ``release stage`` checks if all relevant stories have been reviewed and QA'd and if that is the case, the release branch is deployed into the client environment so that the PT stories can be tested and accepted by the client.
* ``release finish`` checks if all relevant stories were accepted by the client and if that is the case, the release is finished and closed, i.e. all the branches are merged and review requests submitted.
* There is also ``deploy`` family of subcommands, which lets you perform the deployment step alone for a release branch of your choice.


Installing salsita-gitflow
==========================

You can install ``salsita-gitflow`` using::

    pip install --allow-external rbtools --allow-unverified rbtools salsita-gitflow

To upgrade the package to the current version, just add ``-U`` flag to the command::

    pip install -U --allow-external rbtools --allow-unverified rbtools salsita-gitflow

Please not that ``salsita-gitflow`` requires Python 2.7.

Setting it up
-------------
Global (same for all projects)::

* git config --global reviewboard.url https://example.com/rb/ (the trailing slash is REQUIRED)
* git config --global reviewboard.server https://example.com/rb/
* git config --global gitflow.pt.token <YOUR PIVOTAL TRACKER TOKEN>

(Fill in your Pivotal Tracker token and ReviewBoard URLs.)

You will be prompted for the project-specific settings during ``git flow init`` or other commands when the need arises.

If you have the original `git-flow <https://github.com/nvie/gitflow>` installed, just go to the git bin folder and delete everything that starts with ``git-flow``.

On the cutting edge
-------------------

If you want to install salsita-gitflow from the develop or a release branch, follow these steps:

#. Use `virtualenv <https://pypi.python.org/pypi/virtualenv>`_ to create the testing environment.
#. Once the environment is activated, get the sources:

   #. ``git clone https://github.com/salsita/gitflow.git``
   #. ``git checkout develop`` or ``git checkout release/X.Y.Z``
   #. ``python setup.py install``
   #. The git flow commands should be available to you now, just make sure you are using the right one (``man which``)

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

git flow usage
==============

Initialization
--------------

**Before you start, make sure that you are using SSH for communication with origin.**

To initialize a new repo with the basic branch structure, use::
  
    git flow init [-d] [-f]
  
This will then interactively prompt you with some questions like what
branches you would like to use as development and production branches,
and how you would like your prefixes be named. You may simply press
Return on any of those questions to accept the (sane) default
suggestions.

The ``-d`` flag will accept all defaults.

The ``-f`` flag will make gitflow overwrite existing settings.

Note: Please use the ``-d`` flag it will make your life much easier.

init will also check your git config to see if the required records for
Review Board and Pivotal Tracker are in place, failing if that is not the case.

Since not long time ago, there is support for multiple repositories for a
single Pivotal Tracker project. It works by choosing an include or a set of exclude
labels during flow init. It you specify an include label, only the stories labeled
with it will be listed during ``feature start``. If you define some exclude labels,
that is a list of comma-separated labels, all stories NOT labeled with any of the
label defined will be listed.

Creating feature/release/hotfix/support branches
----------------------------------------------------

The list of command line flags listed here is not complete. Check the wiki for
a more complete list. The best documentation is, however,::

      git flow <subcmd> <subsubcmd> -h

* To list/start/finish feature branches, use::
  
      git flow feature
      git flow feature start [--for-release|-R RELEASE]
      git flow feature finish [<name>]
  
  ``feature start`` will list unstarted & started stories from
  current & backlog iterations in Pivotal Tracker. Select one and its state
  will change to `started`. This command creates a feature branch as well, so
  switch between stories using ``git checkout``, not ``git flow feature start``.
  If you wish to base your story on a release branch,
  use ``--for-release RELEASE``. This will also assign the story in Pivotal
  Tracker to the release as a part of starting it.
  
  If the story of your choice is not present in the list of available stories,
  it means that it is not unstarted, the feature branch is already present in
  your local repository or it is not marked with include label or it is excluded
  by an exclude label. Or in general, the story state is wrong :-)

  ``feature finish`` will finish the currently active story (merge it into
  `develop`, push develop, change the story state in PT to `finished` and
  post a review request to Pivotal Tracker). It will do its best to find
  the corersponding review request in ReviewBoard and update the review but
  if it can't then it will post a new review. You can force posting a new
  review by setting the ``-n/--new-review`` flag.

* To push/pull a feature branch to the remote repository, use::

      git flow feature publish <name>
      git flow feature pull <remote> <name>

* To list/start/deploy/finish release branches, use::

      git flow release
      git flow release start <major.minor.release> [<base>]
      git flow release stage [-R|--ignore-missing-reviews] <major.minor.release>
      git flow release finish [-R|--ignore-missing-reviews] [<major.minor.release>]

  ``release start`` creates a new release branch on top of <base> and pushes it.

  ``release stage`` checks all the stories that are included in the release for
  their QA and review status. If the check passes, the branch is deployed to the client
  staging environment to be accepted by the client. You can use ``-R`` to disable code
  review check altogether or just append ``no review`` label into Pivotal Tracker to
  disable the check just for one particular story. If the story is labeled with ``dupe``,
  ``wontfix`` or ``cannot reproduce``, the QA check will be disabled as well.

  You will be asked for a few of questions when you run ``release stage`` for
  the first time. Jenkins security token can be a bit confusing. This string can
  be found on the Jenkins job configuration page, or set there if it is not
  activated for the chosen project yet. The checkbox you are looking for is
  called ``Trigger builds remotely (e.g., from scripts)``.

  ``release finish`` makes sure that all the stories were accepted by the client.
  Then the release branch is merged into master, tagged, then merged into develop and
  deleted.

* To extend the release to include additional features, use::

      git flow release append <major.minor.release>

  which adds the relevant label to all unassigned Pivotal Tracker stories and then
  merges develop into the current release branch.

* To list/start/finish hotfix branches (not supported by Salsita), use::

      git flow hotfix
      git flow hotfix start <release> [<base>]
      git flow hotfix finish <release>

* To list/start support branches (not supported by Salsita), use::
  
      git flow support
      git flow support start <release> <base>
  
  For support branches, the ``<base>`` arg must be a commit on ``master``.

Deploying Projects with gitflow
-------------------------------

There is one more subcommand that does not really fit into the original GitFlow.
It is ``git flow deploy``. It is invoked by ``release start|finish|deliver``
automatically, but you can as well trigger deployment separately by typing::

        git flow deploy develop
        git flow deploy release <version> {qa|client}
        git flow deploy master

Only the release version accepts additional parameters since the other two forms
imply what branch and what environment to use.

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
    $ git flow init # Pick the project from PT and the repo from RB.
    $ git checkout develop
    $ git flow feature start # Pick the story from PT.
    # Code code code
    $ git add *
    $ git commit -s
    # Enter a beautiful and descriptive commit message.
    $ git flow feature finish
    # Go to the Review Board to submit the generated review request.
    # PROFIT!
    # Well, not so fast ...
    $ git flow release start 1.0.0
    # ... review ... qa ...
    $ git flow release stage 1.0.0
    # ... wait for the client, mmmmmmmmmm ...
    $ git flow release finish 1.0.0
    # PROFIT NOW!


Known Issues
------------

- ``AssertionError`` is a bug in one of the libraries that we failed to get rid of, it is not worth the time.
  When you get this error, just repeat the command again, it happens only occasionally.
- ``feature finish`` hangs when posting the review. This usually means that it is prompting your for
  username and password, but you cannot see it because there is a bug in ``rbt``. The bug is fixed in ``0.5.3``
  of ``rbt``, but other things are broken there so it cannot be used. Just try to insert your Review Board
  username and password and see if that helped.
- ``Api10`` error on ``feature finish`` usually means there was an HTTP error and ``rbt`` received a weird response.
  Try again after making sure that your ``git config reviewboard.url|reviewboard.server`` points to the right server.
- ``feature finish`` saying the diff is empty can happen when you change a submodule. This is a wrong usage
  of gitflow. You should be using the multi-repo mode and call ``git flow feature start`` from the repository
  containing the submodule.

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

Please help out
===============

This project is still under development. Feedback and suggestions are
very welcome and I encourage you to use the `Issues list
<http://github.com/salsita/gitflow/issues>`_ on Github to provide that
feedback.

Feel free to fork this repo and to commit your additions. For a list
of all contributors, please see the :file:`AUTHORS.txt`.

You will need :module:`unittest2` to run the tests (which are completely broken as of now, so nevermind).

License terms
==================

git-flow is published under the liberal terms of the BSD License, see
the :file:`LICENSE.txt`. Although the BSD License does not
require you to share any modifications you make to the source code,
you are very much encouraged and invited to contribute back your
modifications to the community, preferably in a Github fork, of
course.
