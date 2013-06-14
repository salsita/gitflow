#!/usr/bin/env python
"""
git-flow

.. program:: git flow

.. cmdoption:: -v, --verbose

       Produce more output.

.. cmdoption:: -h, --help

       Print usage, help and information on the available commands.

"""
#
# This file is part of `gitflow`.
# Copyright (c) 2010-2011 Vincent Driessen
# Copyright (c) 2012 Hartmut Goebel
# Distributed under a BSD-like license. For full terms see the file LICENSE.txt
#

import sys
import argparse
import subprocess as sub

from gitflow.core import GitFlow, info, GitCommandError
from gitflow.util import itersubclasses
from gitflow.exceptions import (GitflowError, AlreadyInitialized,
                                NotInitialized, BranchTypeExistsError,
                                BaseNotOnBranch, NoSuchBranchError)
import gitflow.pivotal as pivotal
from gitflow.review import (BranchReview, ReviewNotAcceptedYet,
                            get_feature_ancestor)

__copyright__ = "2010-2011 Vincent Driessen; 2012 Hartmut Goebel"
__license__ = "BSD"

def die(*texts):
    raise SystemExit('\n'.join(map(str, texts)))

class NotEmpty(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if not values:
            raise argparse.ArgumentError(self, 'must not by empty.')
        setattr(namespace, self.dest, values)


class GitFlowCommand(object):
    """
    This is just an empty class to serve as the base class for all command line
    level sub commands.  Since the git-flow loader will auto-detect all
    subclasses, implementing a new subcommand is as easy as subclassing the
    :class:`GitFlowCommand`.
    """
    @classmethod
    def register_parser(cls, parent):
        raise NotImplementedError("Implement this method in a subclass.")

    @staticmethod
    def run(args):
        raise NotImplementedError("Implement this method in a subclass.")


class VersionCommand(GitFlowCommand):
    @classmethod
    def register_parser(cls, parent):
        p = parent.add_parser('version', help='Show the version of gitflow.')
        p.set_defaults(func=cls.run)

    @staticmethod
    def run(args):
        from gitflow import __version__
        print(__version__)


class StatusCommand(GitFlowCommand):
    @classmethod
    def register_parser(cls, parent):
        p = parent.add_parser('status', help='Show some status.')
        p.set_defaults(func=cls.run)

    @staticmethod
    def run(args):
        gitflow = GitFlow()
        for name, hexsha, is_active_branch in gitflow.status():
            if is_active_branch:
                prefix = '*'
            else:
                prefix = ' '
            info('%s %s: %s' % (prefix, name, hexsha[:7]))


class InitCommand(GitFlowCommand):
    @classmethod
    def register_parser(cls, parent):
        p = parent.add_parser('init',
                              help='Initialize a repository for gitflow.')
        p.add_argument('-f', '--force', action='store_true',
                       help='Force reinitialization of the gitflow preferences.')
        p.add_argument('-d', '--defaults', action='store_true',
                       dest='use_defaults',
                       help='Use default branch naming conventions and prefixes.')
        p.set_defaults(func=cls.run)
        return p

    @staticmethod
    def run(args):
        gitflow = GitFlow()
        err = False
        for option in ('workflow.token',
                       'reviewboard.url',
                       'reviewboard.server'):
            try:
                value = gitflow.get(option)
                if option == 'reviewboard.url' and not value.endswith('/'):
                    err = True
                    print """
Git config key 'reviewboard.url' must contain a trailing slash.
Update your configuration by executing

    $ git config [--global] reviewboard.url %s
""" % (value + '/')
            except Exception:
                err = True
                print """
Git config '%s' missing, please fill it in by executing

    $ git config [--global] %s <value>
""" % (option, option)

        if err:
            raise SystemExit('Operation canceled.')

        from . import _init
        _init.run_default(args)


class FeatureCommand(GitFlowCommand):
    @classmethod
    def register_parser(cls, parent):
        p = parent.add_parser('feature', help='Manage your feature branches.')
        sub = p.add_subparsers(title='Actions')
        cls.register_list(sub)
        cls.register_start(sub)
        cls.register_finish(sub)
        cls.register_checkout(sub)
        cls.register_diff(sub)
        cls.register_rebase(sub)

        cls.register_publish(sub)
        cls.register_pull(sub)
        cls.register_track(sub)

    #- list
    @classmethod
    def register_list(cls, parent):
        p = parent.add_parser('list',
                              help='List all existing feature branches '
                              'in the local repository.')
        p.set_defaults(func=cls.run_list)
        p.add_argument('-v', '--verbose', action='store_true',
                help='Be verbose (more output).')

    @staticmethod
    def run_list(args):
        gitflow = GitFlow()
        gitflow.start_transaction()
        gitflow.list('feature', 'name', use_tagname=False,
                     verbose=args.verbose)

    #- select
    @classmethod
    def register_start(cls, parent):
        p = parent.add_parser('start', help='Select a story in PT and create'
            'a new feature branch.')
        p.set_defaults(func=cls.run_start)
        p.add_argument('-F', '--fetch', action='store_true',
                help='Fetch from origin before performing local operation.')
        p.add_argument('base', nargs='?')

    @staticmethod
    def run_start(args):
        try:
            [story_id, args.name] = pivotal.prompt_user_to_select_story()
        except NotInitialized:
            raise
        pivotal.update_story(story_id, current_state='started')
        gitflow = GitFlow()
        # :fixme: Why does the sh-version not require a clean working dir?
        # :fixme: get default value for `base`
        gitflow.start_transaction('start feature branch %s (from %s)' % \
                (args.name, args.base))
        try:
            branch = gitflow.create('feature', args.name, args.base,
                                    fetch=args.fetch)
        except (NotInitialized, BaseNotOnBranch):
            # printed in main()
            raise
        except Exception, e:
            die("Could not create feature branch %r" % args.name, e)
        print
        print "Summary of actions:"
        print "- A new branch", branch, "was created, based on", args.base
        print "- You are now on branch", branch
        print ""
        print "Now, start committing on your feature. When done, use:"
        print ""
        print "     git flow feature finish", args.name
        print

    #- finish
    @classmethod
    def register_finish(cls, parent):
        p = parent.add_parser('finish', help='Finish a feature branch ' +
            '(with PTintegration).')
        p.set_defaults(func=cls.run_finish)
        #p.add_argument('-F', '--no-fetch', action='store_true', default=True,
        #        help='Fetch from origin before performing local operation.')
        p.add_argument('-r', '--rebase', action='store_true',
                help='Finish branch by rebasing first.')
        #p.add_argument('-k', '--keep', action='store_true', default=True,
        #        help='Keep branch after performing finish.')
        p.add_argument('-D', '--force-delete', action='store_true',
            default=False, help='Force delete feature branch after finish.')
        p.add_argument('-R', '--no-review', action='store_true',
            default=False, help='Do not post a review request.'
                'not just for the last commit.')
        p.add_argument('-P', '--no-push', action='store_true',
            default=False, help='Do not push the develop branch to origin '
            'after merging with the feature branch.')
        p.add_argument('nameprefix', nargs='?')

    @staticmethod
    def run_finish(args):
        gitflow = GitFlow()
        repo = gitflow.repo
        git = repo.git

        f_prefix = gitflow.get_prefix('feature')
        name = gitflow.nameprefix_or_current('feature', args.nameprefix)
        full_name = f_prefix + name

        #+++ PT story stuff
        sys.stdout.write('Getting data from Pivotal Tracker ... ')
        story_id = pivotal.get_story_id_from_branch_name(name)
        story = pivotal.Story(story_id)
        release = story.get_release()
        print 'OK'

        # Decide on the upstream branch.
        if release:
            # Merge into the release branch.
            r_prefix = gitflow.get_prefix('release')
            short_name = gitflow.nameprefix_or_current('release', release)
            upstream = r_prefix + short_name
        else:
            # Merge into the develop branch.
            upstream = gitflow.develop_name()

        #+++ Git manipulation
        sys.stdout.write('Finishing feature branch ... upstream %s ... ' \
                         % upstream)
        gitflow.finish('feature', name, upstream=upstream,
                       fetch=True, rebase=args.rebase,
                       keep=True, force_delete=args.force_delete,
                       tagging_info=None, push=False)
        print 'OK'

        # Get and set the state of the feature.
        sys.stdout.write('Updating Pivotal Tracker ... ')
        if story.is_finished():
            sys.stdout.write('story already finished, skipping ... ')
        else:
            sys.stdout.write('finishing %s ... ' % story.get_id())
            story.finish()
        print 'OK'

        #+++ Review Request
        if not args.no_review:
            sys.stdout.write('Posting review ... upstream %s ... ' % upstream)
            rev_range = [get_feature_ancestor(full_name),
                         repo.commit(full_name).hexsha]
            desc_cmd = ['git', 'log',
                        "--pretty="
                            "--------------------%n"
                            "Author:   %an <%ae>%n"
                            "Comitter: %cn <%ce>%n"
                            "%n"
                            "%s%n%n"
                            "%b",
                        '{0[0]}...{0[1]}'.format(rev_range)]
            desc = '> Story being reviewed: {0}\n'.format(story.get_url()) + \
                   '\n' \
                   'COMMIT LOG\n' \
                    + sub.check_output(desc_cmd)
            # 7 is the magical offset to get the first commit subject
            summary = desc.split('\n')[7]
            review = BranchReview.from_identifier('feature', name, rev_range)
            review.post(summary, desc)
            print 'OK'

            sys.stdout.write('Posting code review url into Pivotal Tracker ... ')
            comment = 'New patch was uploaded into Review Board: ' + review.get_url()
            story.add_comment(comment)
            print 'OK'

        #+++ Git modify merge message
        sys.stdout.write('Amending merge commit message to include links ... ')
        msg  = 'Finished {0} {1}\n\n'.format(f_prefix, name)
        msg += 'PT-Story-URL: {0}\n'.format(story.get_url())
        msg += 'RB-Review-Request-URL: {0}\n'.format(review.get_url())
        git.commit('--amend', '-m', msg)
        if not args.no_push:
            git.push(gitflow.origin_name(), upstream)
        print 'OK'

    #- checkout
    @classmethod
    def register_checkout(cls, parent):
        p = parent.add_parser('checkout',
                help='Check out (switch to) the given feature branch.')
        p.set_defaults(func=cls.run_checkout)
        p.add_argument('nameprefix', action=NotEmpty)

    @staticmethod
    def run_checkout(args):
        gitflow = GitFlow()
        # NB: Does not default to the current branch as `nameprefix` is required
        name = gitflow.nameprefix_or_current('feature', args.nameprefix)
        gitflow.start_transaction('checking out feature branch %s' % name)
        gitflow.checkout('feature', name)

    #- diff
    @classmethod
    def register_diff(cls, parent):
        p = parent.add_parser('diff',
                help='Show a diff of changes since this feature branched off.')
        p.set_defaults(func=cls.run_diff)
        p.add_argument('nameprefix', nargs='?')

    @staticmethod
    def run_diff(args):
        gitflow = GitFlow()
        name = gitflow.nameprefix_or_current('feature', args.nameprefix)
        gitflow.start_transaction('diff for feature branch %s' % name)
        gitflow.diff('feature', name)

    #- rebase
    @classmethod
    def register_rebase(cls, parent):
        p = parent.add_parser('rebase',
                help='Rebase a feature branch on top of develop.')
        p.set_defaults(func=cls.run_rebase)
        p.add_argument('-i', '--interactive', action='store_true',
                help='Start an interactive rebase.')
        p.add_argument('nameprefix', nargs='?')

    @staticmethod
    def run_rebase(args):
        gitflow = GitFlow()
        name = gitflow.nameprefix_or_current('feature', args.nameprefix)
        gitflow.start_transaction('rebasing feature branch %s' % name)
        gitflow.rebase('feature', name, args.interactive)

    #- publish
    @classmethod
    def register_publish(cls, parent):
        p = parent.add_parser('publish',
                help='Publish this feature branch to origin.')
        p.set_defaults(func=cls.run_publish)
        p.add_argument('nameprefix', nargs='?')

    @staticmethod
    def run_publish(args):
        gitflow = GitFlow()
        name = gitflow.nameprefix_or_current('feature', args.nameprefix)
        gitflow.start_transaction('publishing feature branch %s' % name)
        branch = gitflow.publish('feature', name)
        print
        print "Summary of actions:"
        print "- A new remote branch '%s' was created" % branch
        print "- The local branch '%s' was configured to track the remote branch" % branch
        print "- You are now on branch '%s'" % branch
        print

    #- pull
    @classmethod
    def register_pull(cls, parent):
        p = parent.add_parser('pull',
                help='Pull a feature branch from a remote peer.')
        p.set_defaults(func=cls.run_pull)
        p.add_argument('remote', action=NotEmpty,
                       help="Remote repository to pull from.")
        p.add_argument('name', nargs='?',
                help='Name of the feature branch to pull. '
                'Defaults to the current branch, if it is a feature branch.')
        # :todo: implement --prefix
        #p.add-argument('-p', '--prefix',
        #               help='Alternative remote feature branch name prefix.')

    @staticmethod
    def run_pull(args):
        gitflow = GitFlow()
        name = gitflow.name_or_current('feature', args.name, must_exist=False)
        gitflow.start_transaction('pulling remote feature branch %s '
                                  'into local banch %s' % (args.remote, name))
        gitflow.pull('feature', args.remote, name)

    #- track
    @classmethod
    def register_track(cls, parent):
        p = parent.add_parser('track',
                help='Track a feature branch from origin.')
        p.set_defaults(func=cls.run_track)
        p.add_argument('name', action=NotEmpty)

    @staticmethod
    def run_track(args):
        gitflow = GitFlow()
        # NB: `args.name` is required since the branch must not yet exist
        gitflow.start_transaction('tracking remote feature branch %s'
                                  % args.name)
        branch = gitflow.track('feature', args.name)
        print
        print "Summary of actions:"
        print "- A new remote tracking branch '%s' was created" % branch
        print "- You are now on branch '%s'" % branch
        print


class ReleaseCommand(GitFlowCommand):
    @classmethod
    def register_parser(cls, parent):
        p = parent.add_parser('release', help='Manage your release branches.')
        p.add_argument('-v', '--verbose', action='store_true',
           help='Be verbose (more output).')
        sub = p.add_subparsers(title='Actions')
        cls.register_list(sub)
        cls.register_list_stories(sub)
        cls.register_start(sub)
        cls.register_finish(sub)
        cls.register_publish(sub)
        cls.register_track(sub)

    #- list
    @classmethod
    def register_list(cls, parent):
        p = parent.add_parser('list',
                              help='Lists all existing release branches '
                              'in the local repository.')
        p.set_defaults(func=cls.run_list)
        p.add_argument('-v', '--verbose', action='store_true',
                help='Be verbose (more output).')

    @staticmethod
    def run_list(args):
        gitflow = GitFlow()
        gitflow.start_transaction()
        gitflow.list('release', 'version', use_tagname=True,
                     verbose=args.verbose)

    @classmethod
    def register_list_stories(cls, parent):
        p = parent.add_parser('list_stories',
                              help='Lists all stories that are going to be'
                              'released in the release of your choice.')
        p.set_defaults(func=cls.run_list_stories)
        p.add_argument('--version')

    @staticmethod
    def run_list_stories(args):
        print
        if args.version is None:
            pivotal.Release.dump_all_releases()
        else:
            release = pivotal.Release(args.version)
            release.dump_stories()

    #- start
    @classmethod
    def register_start(cls, parent):
        p = parent.add_parser('start', help='Start a new release branch.')
        p.set_defaults(func=cls.run_start)
        p.add_argument('-F', '--fetch', action='store_true',
                help='Fetch from origin before performing local operation.')
        p.add_argument('version', action=NotEmpty)

    @staticmethod
    def run_start(args):
        gitflow = GitFlow()
        base = gitflow.develop_name()

        #+ Pivotal Tracker modifications.
        release = pivotal.Release(args.version)
        any_assigned = False
        print
        print 'Stories already assigned to this release:'
        for story in release.iter_stories():
            sys.stdout.write('    ')
            story.dump()
            any_assigned = True
        if not any_assigned:
            print '    None'
        print
        any_candidate = False
        print 'Stories to be newly assigned to this release:'
        for story in release.iter_candidates():
            sys.stdout.write('    ')
            story.dump()
            any_candidate = True
        if not any_candidate:
            print '    None'
        print

        if not any_assigned and not any_candidate:
            raise SystemExit('No stories to be released, aborting...')

        if not release.prompt_for_confirmation():
            raise SystemExit('Aborting...')

        #+ Git modifications.
        sys.stdout.write('Creating release branch (base being %s) ... ' \
                         % base)
        try:
            branch = gitflow.create('release', args.version, base,
                                    fetch=args.fetch)
        except (NotInitialized, BranchTypeExistsError, BaseNotOnBranch):
            print
            # printed in main()
            raise
        except Exception, e:
            die("Could not create release branch %r" % args.version, e)
        print 'OK'

        release.start()

        print
        print "Follow-up actions:"
        print "- Bump the version number now!"
        print "- Start committing last-minute fixes in preparing your release"
        print "- When done, run:"
        print
        print "     git flow release finish", args.version
        print

    #- finish
    @classmethod
    def register_finish(cls, parent):
        p = parent.add_parser('finish', help='Finish a release branch.')
        p.set_defaults(func=cls.run_finish)
        # fetch by default
        p.add_argument('-F', '--no-fetch', action='store_true',
                help='Fetch from origin before performing local operation.')
        # push by default
        p.add_argument('-P', '--no-push', action='store_true',
                       #:todo: get "origin" from config
                       help="Push to origin after performing finish.")
        p.add_argument('-k', '--keep', action='store_true',
                help='Keep branch after performing finish.')
        p.add_argument('-R', '--ignore-missing-reviews', action='store_true',
                       help='Just print a warning if there is no review for '
                            'a feature branch that is assigned to this release,'
                            ' do not fail.')
        p.add_argument('version', nargs='?')

        g = p.add_argument_group('tagging options')
        g.add_argument('-n', '--notag', action='store_true',
                       help="Don't tag this release.")
        g.add_argument('-m', '--message',
                       help="Use the given tag message.")
        g.add_argument('-s', '--sign', action='store_true',
                help="Sign the release tag cryptographically.")
        g.add_argument('-u', '--signingkey',
                help="Use the given GPG-key for the digital signature "
                     "instead of the default git uses (implies -s).")

    @staticmethod
    def run_finish(args):
        gitflow = GitFlow()
        git     = gitflow.git
        origin  = gitflow.origin()
        version = gitflow.name_or_current('release', args.version)

        #+++ Check QA
        release = pivotal.Release(version)
        print "Checking if all relevant stories have been QA'd ... "
        try:
            release.try_deliver()
        except GitflowError:
            raise SystemExit('FAIL')
        print 'OK'

        #+++ Close (submit) all relevant reviews in Review Board
        print 'Submitting all relevant review requests ... '
        feature_prefix = gitflow.get_prefix('feature')
        err = None
        for story in release.iter_stories():
            prefix = feature_prefix + str(story.get_id())
            try:
                r = BranchReview.from_prefix(prefix)
            except NoSuchBranchError, e:
                err = e
                print '    ' + str(e)
                continue
            r.submit()
            print '    ' + str(r.get_id())
        if not args.ignore_missing_reviews and err is not None:
            raise SystemExit('FAIL')
        print 'OK'

        #+++ Merge release branch into develop and master
        sys.stdout.write('Finishing release branch %s ... ' % version)
        tagging_info = None
        if not args.notag:
            tagging_info = dict(
                sign=args.sign or args.signingkey,
                signingkey=args.signingkey,
                message=args.message)
        gitflow.finish('release', version,
                                 fetch=(not args.no_fetch), rebase=False,
                                 keep=args.keep, force_delete=False,
                                 tagging_info=tagging_info, push=(not args.no_push))
        print 'OK'

        #+++ Collect local and remote branches to be deleted
        sys.stdout.write('Collecting branches to be deleted ... ')
        local_branches  = list()
        remote_branches = list()

        #+ Collect features to be deleted.
        origin_prefix = str(origin) + '/'
        feature_prefix = gitflow.get_prefix('feature')
        # refs = [<type>/<id>/...]
        refs = [str(ref)[len(origin_prefix):] for ref in origin.refs]
        for story in release.iter_stories():
            # prefix = <feature-prefix>/<id>
            prefix = feature_prefix + str(story.get_id())
            try:
                name = gitflow.nameprefix_or_current('feature', prefix)
                local_branches.append(feature_prefix + name)
            except NoSuchBranchError:
                pass
            for ref in refs:
                # if <feature-prefix>/... startswith <feature-prefix>/<id>
                if ref.startswith(prefix):
                    remote_branches.append(ref)
        #+ Collect releases to be deleted.
        release_branch = gitflow.get_prefix('release') + version
        try:
            gitflow.nameprefix_or_current('release', version)
            local_branches.append(release_branch)
        except NoSuchBranchError:
            pass
        if release_branch in refs:
            remote_branches.append(release_branch)
        print 'OK'

        #+++ Delete local and remote branches that are a part of this release
        sys.stdout.write('Checking out %s ... ' % gitflow.develop_name())
        git.checkout(gitflow.develop_name())
        print 'OK'
        #+ Delete local branches.
        print 'Deleting local branches ...'
        for branch in local_branches:
            git.branch('-D', branch)
            print '    ' + branch
        print '    OK'
        #+ Delete remote branches.
        print 'Deleting remote branches ...'
        for branch in remote_branches:
            print '    ' + branch
        refspecs = [(':' + b) for b in remote_branches]
        git.push(str(origin), *refspecs)
        print '    OK'

        #+++ Deliver all relevant stories in Pivotal Tracker
        release.deliver()

    #- publish
    @classmethod
    def register_publish(cls, parent):
        p = parent.add_parser('publish',
                help='Publish this release branch to origin.')
        p.set_defaults(func=cls.run_publish)
        p.add_argument('version', nargs='?')

    @staticmethod
    def run_publish(args):
        gitflow = GitFlow()
        version = gitflow.name_or_current('release', args.version)
        gitflow.start_transaction('publishing release branch %s' % version)
        branch = gitflow.publish('release', version)
        print
        print "Summary of actions:"
        print "- A new remote branch '%s' was created" % branch
        print "- The local branch '%s' was configured to track the remote branch" % branch
        print "- You are now on branch '%s'" % branch
        print

    #- track
    @classmethod
    def register_track(cls, parent):
        p = parent.add_parser('track',
                help='Track a release branch from origin.')
        p.set_defaults(func=cls.run_track)
        p.add_argument('version', action=NotEmpty)

    @staticmethod
    def run_track(args):
        gitflow = GitFlow()
        # NB: `args.version` is required since the branch must not yet exist
        gitflow.start_transaction('tracking remote release branch %s'
                                  % args.version)
        branch = gitflow.track('release', args.version)
        print
        print "Summary of actions:"
        print "- A new remote tracking branch '%s' was created" % branch
        print "- You are now on branch '%s'" % branch
        print


class HotfixCommand(GitFlowCommand):
    @classmethod
    def register_parser(cls, parent):
        p = parent.add_parser('hotfix', help='Manage your hotfix branches.')
        p.add_argument('-v', '--verbose', action='store_true',
           help='Be verbose (more output).')
        sub = p.add_subparsers(title='Actions')
        cls.register_list(sub)
        cls.register_start(sub)
        cls.register_finish(sub)
        cls.register_publish(sub)

    #- list
    @classmethod
    def register_list(cls, parent):
        p = parent.add_parser('list',
                              help='Lists all existing hotfix branches '
                              'in the local repository.')
        p.set_defaults(func=cls.run_list)
        p.add_argument('-v', '--verbose', action='store_true',
                help='Be verbose (more output).')

    @staticmethod
    def run_list(args):
        gitflow = GitFlow()
        gitflow.start_transaction()
        gitflow.list('hotfix', 'version', use_tagname=True,
                     verbose=args.verbose)

    #- start
    @classmethod
    def register_start(cls, parent):
        p = parent.add_parser('start', help='Start a new hotfix branch.')
        p.set_defaults(func=cls.run_start)
        p.add_argument('-F', '--fetch', action='store_true',
                       #:todo: get "origin" from config
                help='Fetch from origin before performing local operation.')
        p.add_argument('version', action=NotEmpty)
        p.add_argument('base', nargs='?')

    @staticmethod
    def run_start(args):
        gitflow = GitFlow()
        # NB: `args.version` is required since the branch must not yet exist
        # :fixme: get default value for `base`
        gitflow.start_transaction('create hotfix branch %s (from %s)' % \
                (args.version, args.base))
        try:
            branch = gitflow.create('hotfix', args.version, args.base,
                                    fetch=args.fetch)
        except (NotInitialized, BranchTypeExistsError, BaseNotOnBranch):
            # printed in main()
            raise
        except Exception, e:
            die("Could not create hotfix branch %r" % args.version, e)
        print
        print "Summary of actions:"
        print "- A new branch", branch, "was created, based on", args.base
        print "- You are now on branch", branch
        print ""
        print "Follow-up actions:"
        print "- Bump the version number now!"
        print "- Start committing your hot fixes"
        print "- When done, run:"
        print
        print "     git flow hotfix finish", args.version

    #- finish
    @classmethod
    def register_finish(cls, parent):
        p = parent.add_parser('finish', help='Finish a hotfix branch.')
        p.set_defaults(func=cls.run_finish)
        p.add_argument('-F', '--fetch', action='store_true',
                help='Fetch from origin before performing local operation.')
        p.add_argument('-p', '--push', action='store_true',
                       #:todo: get "origin" from config
                       help="Push to origin after performing finish.")
        p.add_argument('-k', '--keep', action='store_true',
                help='Keep branch after performing finish.')
        p.add_argument('version', nargs='?')

        g = p.add_argument_group('tagging options')
        g.add_argument('-n', '--notag', action='store_true',
                       help="Don't tag this hotfix.")
        g.add_argument('-m', '--message',
                       help="Use the given tag message.")
        g.add_argument('-s', '--sign', action='store_true',
                help="Sign the hotfix tag cryptographically.")
        g.add_argument('-u', '--signingkey',
                help="Use this given GPG-key for the digital signature "
                     "instead of the default git uses (implies -s).")

    @staticmethod
    def run_finish(args):
        gitflow = GitFlow()
        version = gitflow.name_or_current('hotfix', args.version)
        gitflow.start_transaction('finishing hotfix branch %s' % version)
        tagging_info = None
        if not args.notag:
            tagging_info = dict(
                sign=args.sign or args.signingkey,
                signingkey=args.signingkey,
                message=args.message)
        release = gitflow.finish('hotfix', version,
                                 fetch=args.fetch, rebase=False,
                                 keep=args.keep, force_delete=False,
                                 tagging_info=tagging_info)

    #- publish
    @classmethod
    def register_publish(cls, parent):
        p = parent.add_parser('publish',
                help='Publish this hotfix branch to origin.')
        p.set_defaults(func=cls.run_publish)
        p.add_argument('version', nargs='?')

    @staticmethod
    def run_publish(args):
        gitflow = GitFlow()
        version = gitflow.name_or_current('hotfix', args.version)
        gitflow.start_transaction('publishing hotfix branch %s' % version)
        branch = gitflow.publish('hotfix', version)
        print
        print "Summary of actions:"
        print "- A new remote branch '%s' was created" % branch
        print "- The local branch '%s' was configured to track the remote branch" % branch
        print "- You are now on branch '%s'" % branch
        print


class SupportCommand(GitFlowCommand):
    @classmethod
    def register_parser(cls, parent):
        p = parent.add_parser('support', help='Manage your support branches.')
        p.add_argument('-v', '--verbose', action='store_true',
           help='Be verbose (more output).')
        sub = p.add_subparsers(title='Actions')
        cls.register_list(sub)
        cls.register_start(sub)

    #- list
    @classmethod
    def register_list(cls, parent):
        p = parent.add_parser('list',
                              help='Lists all existing support branches '
                              'in the local repository.')
        p.set_defaults(func=cls.run_list)
        p.add_argument('-v', '--verbose', action='store_true',
                help='Be verbose (more output).')

    @staticmethod
    def run_list(args):
        gitflow = GitFlow()
        gitflow.start_transaction()
        gitflow.list('support', 'version', use_tagname=True,
                     verbose=args.verbose)

    #- start
    @classmethod
    def register_start(cls, parent):
        p = parent.add_parser('start', help='Start a new support branch.')
        p.set_defaults(func=cls.run_start)
        p.add_argument('-F', '--fetch', action='store_true',
                help='Fetch from origin before performing local operation.')
        p.add_argument('name', action=NotEmpty)
        p.add_argument('base', nargs='?')

    @staticmethod
    def run_start(args):
        gitflow = GitFlow()
        # NB: `args.name` is required since the branch must not yet exist
        # :fixme: get default value for `base`
        gitflow.start_transaction('create support branch %s (from %s)' %
                (args.name, args.base))
        try:
            branch = gitflow.create('support', args.name, args.base,
                                    fetch=args.fetch)
        except (NotInitialized, BranchTypeExistsError, BaseNotOnBranch):
            # printed in main()
            raise
        except Exception, e:
            die("Could not create support branch %r" % args.name, e)
        print
        print "Summary of actions:"
        print "- A new branch", branch, "was created, based on", args.base
        print "- You are now on branch", branch
        print ""


def main():
    parser = argparse.ArgumentParser(prog='git flow')
    placeholder = parser.add_subparsers(title='Subcommands')
    for cls in itersubclasses(GitFlowCommand):
        cls.register_parser(placeholder)
    args = parser.parse_args()
    try:
        args.func(args)
    except KeyboardInterrupt:
        raise SystemExit('Aborted by user request.')


if __name__ == '__main__':
    try:
        main()
    except (GitflowError, GitCommandError), e:
        raise SystemExit('Error: %s' %e)
