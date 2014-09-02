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

import re
import sys
import argparse
import subprocess as sub

from gitflow.core import GitFlow, info, GitCommandError
from gitflow.util import itersubclasses
from gitflow.jenkins import Jenkins, DeploymentRequestError
from gitflow.exceptions import (GitflowError, AlreadyInitialized,
                                NotInitialized, BranchTypeExistsError,
                                BaseNotOnBranch, NoSuchBranchError,
                                BaseNotAllowed, BranchExistsError,
                                IllegalVersionFormat, InconsistencyDetected,
                                OperationsError)
import gitflow.pivotal as pivotal
import gitflow.review as review
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
        cls.register_purge(sub)
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
                              'in the local and optionally remote repository.')
        p.set_defaults(func=cls.run_list)
        p.add_argument('-a', '--all', action='store_true',
                help='List remote feature branches as well.')
        p.add_argument('-v', '--verbose', action='store_true',
                help='Be verbose (more output).')

    @staticmethod
    def run_list(args):
        gitflow = GitFlow()
        gitflow.start_transaction()
        gitflow.list('feature', 'name', use_tagname=False,
                     verbose=args.verbose, include_remote=args.all)

    #- select
    @classmethod
    def register_start(cls, parent):
        p = parent.add_parser('start', help='Select a story in PT and create'
            'a new feature branch.')
        p.set_defaults(func=cls.run_start)
        p.add_argument('-F', '--no-fetch', action='store_true',
                help='Do not fetch from origin before performing local operation.')
        p.add_argument('-r', '--for-release',
                help='Base the feature branch on a release branch.')
        p.add_argument('-m', '--match',
                help='Filter stories by regular expression')

    @staticmethod
    def run_start(args):
        if args.for_release:
            pivotal.check_version_format(args.for_release)
        gitflow = GitFlow()
        git     = gitflow.git

        base = None
        if args.for_release is not None:
            # Make sure --for-release matches the requirements.
            pivotal.check_version_format(args.for_release)
            base = gitflow.get_prefix('release') + args.for_release
        else:
            base = gitflow.managers['feature'].default_base()

        if not args.no_fetch:
            sys.stderr.write('Fetching origin ... ')
            gitflow.origin().fetch()
            print 'OK'

        # Check if the base exists and is in sync as soon as possible.
        sys.stdout.write('Checking the base branch ({0}) ... '.format(base))
        origin_base = gitflow.require_origin_branch(base)
        try:
            gitflow.must_be_uptodate(base)
        except NoSuchBranchError:
            sys.stdout.write('found remote counterpart ... ')
            git.branch(base, origin_base.name)
        print('OK')

        [story, name] = pivotal.prompt_user_to_select_story(match=args.match)

        sys.stdout.write('Setting myself as the story owner ... ')
        try:
            story.set_me_as_owner()
        except:
            print('FAIL')
        print('OK')

        if args.for_release is not None:
            sys.stdout.write('Assigning the chosen story to release {0} ... '.format(args.for_release))
            story.assign_to_release(args.for_release)
            print('OK')

        if story.is_rejected():
            sid = str(story.get_id())
            gitflow.start_transaction('restart story {0}'.format(sid))
            sys.stdout.write('Checking out the feature branch ... ')
            try:
                gitflow.checkout('feature', sid)
                print('OK')
            except NoSuchBranchError as e:
                print('FAIL')
                raise InconsistencyDetected(
                    'The branch is missing for story {0}.'.format(sid))
            sys.stdout.write('Updating Pivotal Tracker ... ')
            story.start()
            print('OK')
            return

        # :fixme: Why does the sh-version not require a clean working dir?
        gitflow.start_transaction('start feature branch %s (from %s)' % \
                (name, base))
        try:
            # fetch=False because we are already fetching at the beginning.
            branch = gitflow.create('feature', name, base, fetch=False)
        except (NotInitialized, BaseNotOnBranch):
            # printed in main()
            raise
        except Exception, e:
            die("Could not create feature branch %r" % name, e)

        # Mark beginning of the feature branch with another branch
        sys.stdout.write('Inserting feature base marker ... ')
        base_marker = gitflow.managers['feature'].base_marker_name(str(branch))
        git.branch(base_marker, base)
        print('OK')

        sys.stdout.write('Updating Pivotal Tracker ... ')
        story.start()
        print('OK')

        print
        print "Summary of actions:"
        print "- A new branch", branch, "was created, based on", base
        print "- You are now on branch", branch
        print ""
        print "Now, start committing on your feature. When done, use:"
        print ""
        print "     git flow feature finish", name
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
        p.add_argument('-S', '--summary-from-commit',
                action='store_true', default=False,
                help='Use the last commit title instead of Pivotal Tracker '
                'story name for summary in Review Board.')
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
        story_id = pivotal.get_story_id_from_branch_name('feature', name)
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

        # Fail as soon as possible if something is not right so that we don't
        # get Pivotal Tracker into an inconsistent state.
        rev_range = [get_feature_ancestor(full_name, upstream),
                     repo.commit(full_name).hexsha]

        #+++ Git manipulation
        sys.stdout.write('Finishing feature branch ... upstream %s ... ' \
                         % upstream)
        gitflow.finish('feature', name, upstream=upstream,
                       fetch=True, rebase=args.rebase,
                       keep=True, force_delete=args.force_delete,
                       tagging_info=None, push=(not args.no_push))
        print 'OK'

        #+++ Review Request
        if not args.no_review:
            sys.stdout.write('Posting review ... upstream %s ... ' % upstream)
            review = BranchReview.from_identifier('feature', name, rev_range)
            review.post(story, summary_from_story=(not args.summary_from_commit))
            print('OK')

            sys.stdout.write('Posting code review url into Pivotal Tracker ... ')
            comment = 'New patch was uploaded into Review Board: ' + review.get_url()
            story.add_comment(comment)
            print('OK')

        #+++ Finish PT story
        sys.stdout.write('Updating Pivotal Tracker ... ')
        if story.is_finished():
            sys.stdout.write('story already finished, skipping ... ')
        else:
            sys.stdout.write('finishing %s ... ' % story.get_id())
            story.finish()
        print 'OK'

        #+++ Git modify merge message
        #sys.stdout.write('Amending merge commit message to include links ... ')
        #msg  = 'Finished {0} {1}\n\n'.format(f_prefix, name)
        #msg += 'PT-Story-URL: {0}\n'.format(story.get_url())
        #msg += 'RB-Review-Request-URL: {0}\n'.format(review.get_url())
        #git.commit('--amend', '-m', msg)
        #if not args.no_push:
        #    git.push(gitflow.origin_name(), upstream)
        #print 'OK'

    #- purge
    @classmethod
    def register_purge(cls, parent):
        p = parent.add_parser('purge',
                help='Purge accepted feature branches.')
        p.set_defaults(func=cls.run_purge)

    @staticmethod
    def run_purge(args):
        gitflow = GitFlow()
        git = gitflow.git
        mgr = gitflow.managers['feature']
        origin_name = gitflow.origin_name()

        def prompt_user(question):
            return raw_input(question).strip().lower() == 'y'

        story_cache = {}
        def get_story(story_id):
            try:
                return story_cache[story_id]
            except KeyError:
                sys.stdout.write('Fetching story {0} ... '.format(story_id))
                sys.stdout.flush()
                story = pivotal.Story(story_id)
                story_cache[story_id] = story
                print('')
                return story

        def get_confirmed_branch_set(features, markers):
            to_delete = set()
            # Go through the branches and ask the user.
            for branch in features:
                story_id = pivotal.get_story_id_from_branch_name('feature', branch)
                story = get_story(story_id)
                if not story.is_accepted():
                    continue
                if not prompt_user('Delete {0}? [y/N]: '.format(branch)):
                    continue
                to_delete.add(branch)
                # Check the associated base markers as well.
                base = mgr.base_marker_name(branch)
                if base in markers:
                    to_delete.add(base)
            # Check the markers that were potentially left behind.
            for base in markers:
                if base in to_delete:
                    continue
                story_id = pivotal.get_story_id_from_base_marker(base)
                story = get_story(story_id)
                if not story.is_accepted():
                    continue
                if not prompt_user('Delete {0} (base marker left behind)? [y/N]: '.format(base)):
                    continue
                to_delete.add(base)
            return to_delete

        print('---> Local branches')
        local_branches = [str(b) for b in mgr.iter()]
        local_markers = [str(b) for b in mgr.iter_markers()]
        to_delete = get_confirmed_branch_set(local_branches, local_markers)
        if len(to_delete) != 0:
            print('')
            for branch in to_delete:
                sys.stdout.write('Deleting {} ... '.format(branch))
                sys.stdout.flush()
                try:
                    git.branch('-d', branch)
                    print('OK')
                except Exception as ex:
                    sys.stderr.write('ERR: ' + str(ex) + '\n')
        else:
            print('\nNo local branches selected, skipping...')

        print('\n---> Remote branches')
        remote_branches = [str(b)[len(origin_name)+1:] for b in mgr.iter(remote=True)]
        remote_markers = [str(b)[len(origin_name)+1:] for b in mgr.iter_markers(remote=True)]
        to_delete = get_confirmed_branch_set(remote_branches, remote_markers)
        if len(to_delete) != 0:
            to_push = []
            for branch in to_delete:
                to_push.append(':' + branch)
            sys.stdout.write('\nDeleting the selected remote branches (push) ... ')
            sys.stdout.flush()
            gitflow.origin().push(to_push)
            print('OK')
        else:
            print('\nNo remote branches selected, skipping...')

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
        branch = gitflow.checkout('feature', args.nameprefix)
        print 'Checking out feature {0}.'.format(branch.name)

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
        git     = gitflow.git
        name = gitflow.nameprefix_or_current('feature', args.nameprefix)
        gitflow.start_transaction('publishing feature branch %s' % name)
        branch = gitflow.publish('feature', name)
        print(branch)
        base_marker = gitflow.managers['feature'].base_marker_name(str(branch))
        git.push(gitflow.origin_name(), base_marker)
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
        cls.register_append(sub)
        cls.register_stage(sub)
        cls.register_finish(sub)
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
        p = parent.add_parser('start', help='Start a new release.')
        p.set_defaults(func=cls.run_start)
        p.add_argument('-F', '--no-fetch', action='store_true',
                help='Do not fetch from origin before performing local operation.')
        p.add_argument('version', action=NotEmpty)

    @staticmethod
    def run_start(args):
        gitflow = GitFlow()
        base = gitflow.develop_name()

        #+ Pivotal Tracker modifications.
        pivotal.prompt_user_to_confirm_release(args.version)

        #+ Git modifications.
        sys.stdout.write('Creating release branch (base being %s) ... ' \
                         % base)
        try:
            branch = gitflow.create('release', args.version, base,
                                    fetch=(not args.no_fetch))
        except BranchExistsError:
            sys.stdout.write('branch already exists ... ')
        except (NotInitialized, BranchTypeExistsError, BaseNotOnBranch):
            # printed in main()
            raise
        except Exception, e:
            die("could not create release branch %r" % args.version, e)
        print 'OK'

        pivotal.start_release(args.version)
        gitflow.checkout('release', args.version)

        print
        print "Follow-up actions:"
        print "- Bump the version number now!"
        print "- Start committing last-minute fixes in preparing your release"
        print "- Wait for all the stories to be QA'd and reviewed"
        print "- When done, run:"
        print
        print "     git flow release stage", args.version
        print
        print "  to push the release to the client staging environment."

    #- append
    @classmethod
    def register_append(cls, parent):
        p = parent.add_parser('append', help='Append stories to an existing release.')
        p.set_defaults(func=cls.run_append)
        p.add_argument('-F', '--no-fetch', action='store_true',
                help='Do not fetch from origin before performing local operation.')
        p.add_argument('version', action=NotEmpty)

    @staticmethod
    def run_append(args):
        # Print info and ask for confirmation.
        pivotal.prompt_user_to_confirm_release(args.version)

        # Merge, push and insert PT labels.
        gitflow = GitFlow()
        git = gitflow.git
        current_branch = gitflow.repo.active_branch

        develop = gitflow.develop_name()
        gitflow.name_or_current('release', args.version)
        release = gitflow.get_prefix('release') + str(args.version)

        print('')
        sys.stdout.write('Merging develop into ' + release + ' ... ')
        gitflow.checkout('release', str(args.version))
        git.merge(gitflow.develop_name())
        print('OK')

        sys.stdout.write('Pushing ' + release + ' ... ')
        gitflow.origin().push([release])
        print('OK')

        sys.stdout.write('Moving back to ' + str(current_branch) + ' ... ')
        current_branch.checkout()
        print('OK')

        sys.stdout.write('Marking Pivotal Tracker stories ... ')
        pivotal.start_release(args.version)
        print('OK')

    #- stage
    @classmethod
    def register_stage(cls, parent):
        p = parent.add_parser('stage', help='Stage a release branch for the client.')
        p.set_defaults(func=cls.run_stage)
        p.add_argument('-F', '--no-fetch', action='store_true',
                help='Do not fetch from origin before performing local operation.')
        p.add_argument('-R', '--ignore-missing-reviews', action='store_true',
                       help='Just print a warning if there is no review for '
                            'a feature branch that is assigned to this release,'
                            ' do not fail.')
        p.add_argument('-D', '--skip-deployment', action='store_true',
                help='Do not deploy to the client staging environment.')
        p.add_argument('version', action=NotEmpty, help="Release to be staged for the client.")

    @staticmethod
    def run_stage(args):
        assert args.version
        pivotal.check_version_format(args.version)

        gitflow = GitFlow()

        # Check the repository if CircleCI is enabled.
        if gitflow.is_circleci_enabled():
            _try_deploy_circleci(gitflow, args.version)

        # Check if all stories were QA'd
        pt_release = pivotal.Release(args.version)
        print('Checking Pivotal Tracker stories ... ')
        pt_release.try_stage()
        print('OK')

        # Check if all relevant review requests are there
        rb_release = review.Release(pt_release)
        print('Checking Review Board review requests ... ')
        rb_release.try_stage(args.ignore_missing_reviews)
        print('OK')

        # Deliver all relevant PT stories
        print('Delivering all relevant Pivotal Tracker stories ... ')
        pt_release.stage()
        print('OK')

        # Trigger the deployment job
        if not args.skip_deployment:
            args.environ = 'client'
            args.no_check = True
            DeployCommand.run_release(args)

        print
        print "Follow-up actions:"
        print "- Wait for the client to accept all the stories."
        print "- When all is done, run"
        print
        print "     git flow release finish", args.version
        print
        print "  to perform the final merge, tagging and cleanup."

    #- finish
    @classmethod
    def register_finish(cls, parent):
        p = parent.add_parser('finish', help='Finish and close a release.')
        p.set_defaults(func=cls.run_finish)
        # fetch by default
        p.add_argument('-F', '--no-fetch', action='store_true',
                help='Do not fetch from origin before performing local operation.')
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
        p.add_argument('version', action=NotEmpty, help="Release to be finished and closed.")

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

        #+++ Check if all stories were QA'd
        pt_release = pivotal.Release(args.version)
        print('Checking Pivotal Tracker stories ... ')
        pt_release.try_finish()
        print('OK')

        #+++ Check all relevant review requests in Review Board, to be sure
        rb_release = review.Release(pt_release)
        print('Checking Review Board review requests ... ')
        rb_release.try_finish(args.ignore_missing_reviews)
        print('OK')

        #+++ Merge the release branch into develop and master
        sys.stdout.write('Merging release branch %s ... ' % version)

        # Save the current position of master and develop in case we need to roll back.
        master_hexsha = _branch_hexsha(gitflow.master_name())
        develop_hexsha = _branch_hexsha(gitflow.develop_name())

        tagging_info = None
        if not args.notag:
            tagging_info = dict(
                sign=args.sign or args.signingkey,
                signingkey=args.signingkey,
                message=args.message)
        gitflow.finish('release', version,
                                 fetch=(not args.no_fetch), rebase=False,
                                 keep=True, force_delete=False,
                                 tagging_info=tagging_info, push=False)
        print('OK')

        #+++ Close all relevant review requests
        try:
            sys.stdout.write('Submitting all relevant review requests ... ')
            rb_release.finish()
            print('OK')
        except Exception as ex:
            print('FAIL')
            ReleaseCommand.rollback(tag=args.version,
                    master_hexsha=master_hexsha, develop_hexsha=develop_hexsha)
            raise ex

        #+++ Collect local and remote branches to be deleted
        sys.stdout.write('Collecting branches to be deleted ... ')
        local_branches  = list()
        remote_branches = list()

        #+ Collect features to be deleted.
        origin_prefix = str(origin) + '/'
        feature_prefix = gitflow.get_prefix('feature')
        # refs = [<type>/<id>/...]
        refs = [str(ref)[len(origin_prefix):] for ref in origin.refs]
        for story in pt_release:
            if story.is_rejected():
                continue
            # prefix = <feature-prefix>/<id>
            prefix = feature_prefix + str(story.get_id())
            base_marker = gitflow.managers['feature'].base_marker_name(prefix)
            try:
                name = gitflow.nameprefix_or_current('feature', prefix)
                local_branches.append(feature_prefix + name)
                if base_marker in gitflow.repo.refs:
                    local_branches.append(base_marker)
            except NoSuchBranchError:
                pass
            for ref in refs:
                # if <feature-prefix>/... startswith <feature-prefix>/<id>
                if ref.startswith(prefix) or ref == base_marker:
                    remote_branches.append(ref)
        #+ Collect releases to be deleted.
        if not args.keep:
            release_branch = gitflow.get_prefix('release') + version
            try:
                gitflow.name_or_current('release', version)
                local_branches.append(release_branch)
            except NoSuchBranchError:
                pass
            if release_branch in refs:
                remote_branches.append(release_branch)
            print 'OK'

        #+++ Delete local and remote branches that are a part of this release
        sys.stdout.write('Checking out {0} ...'.format(gitflow.develop_name()))
        try:
            git.checkout(gitflow.develop_name())
        except Exception as ex:
            print('FAIL')
            ReleaseCommand.rollback(tag=args.version,
                    master_hexsha=master_hexsha, develop_hexsha=develop_hexsha)
            raise ex
        print('OK')
        #+ Delete local branches.
        print('Deleting local branches ...')
        try:
            for branch in local_branches:
                print('    ' + branch)
                git.branch('-D', branch)
        except Exception as ex:
            print('FAIL (the last branch printed)')
            ReleaseCommand.rollback(tag=args.version,
                    master_hexsha=master_hexsha, develop_hexsha=develop_hexsha)
            raise ex
        print('    OK')
        #+ Delete remote branches.
        print('Deleting remote branches and pushing the rest ...')
        for branch in remote_branches:
            print('    ' + branch)
        refspecs = [(':' + b) for b in remote_branches]
        refspecs.append(gitflow.develop_name())
        refspecs.append(gitflow.master_name())
        try:
            git.push(str(origin), '--tags', *refspecs)
        except Exception as ex:
            print('    FAIL')
            ReleaseCommand.rollback(tag=args.version,
                    master_hexsha=master_hexsha, develop_hexsha=develop_hexsha)
            raise ex
        print('    OK')

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

    @staticmethod
    def rollback(tag=None, master_hexsha=None, develop_hexsha=None):
        gitflow = GitFlow()

        try:
            if not tag is None:
                sys.stdout.write('Deleting the release tag ... ')
                gitflow.git.tag('-d', tag)
                print ('OK')
        except Exception:
            print ('FAIL')

        try:
            if not master_hexsha is None:
                sys.stdout.write('Resetting master to the original position ... ')
                _reset_branch(gitflow.master_name(), master_hexsha)
                print('OK')
        except Exception:
            print ('FAIL')

        try:
            if not develop_hexsha is None:
                sys.stdout.write('Resetting develop to the original position ... ')
                _reset_branch(gitflow.develop_name(), develop_hexsha)
                print ('OK')
        except Exception:
            print ('FAIL')


def _branch_hexsha(branch):
    return sub.check_output(['git', 'rev-parse', branch]).replace('\n', '')

def _reset_branch(branch, hexsha):
    current = sub.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).replace('\n', '')
    sub.check_output(['git', 'checkout', branch], stderr=sub.STDOUT)
    sub.check_output(['git', 'reset', '--keep', hexsha], stderr=sub.STDOUT)
    sub.check_output(['git', 'checkout', current], stderr=sub.STDOUT)


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


class DeployCommand(GitFlowCommand):
    @classmethod
    def register_parser(cls, parent):
        p = parent.add_parser('deploy', help='Deploy a Git branch.')
        p.add_argument('-v', '--verbose', action='store_true',
           help='Be verbose (more output).')
        sub = p.add_subparsers(title='Actions')
        cls.register_develop(sub)
        cls.register_release(sub)
        cls.register_master(sub)

    #- develop
    @classmethod
    def register_develop(cls, parent):
        p = parent.add_parser('develop', help='Deploy the develop branch.')
        p.set_defaults(func=cls.run_develop)

    @staticmethod
    def run_develop(args):
        args.environ = 'develop'
        DeployCommand._run_deploy(args)

    #- release
    @classmethod
    def register_release(cls, parent):
        p = parent.add_parser('release', help='Deploy a release branch.')
        p.set_defaults(func=cls.run_release)
        p.add_argument('-F', '--no-fetch', action='store_true',
                help='Do not fetch from origin before performing local operation.')
        p.add_argument('-R', '--ignore-missing-reviews', action='store_true',
                       help='Just print a warning if there is no review for '
                            'a feature branch that is assigned to this release,'
                            ' do not fail.')
        p.add_argument('-C', '--no-check', action='store_true',
                help="Do not perform any checking before deployment.")
        p.add_argument('version', action=NotEmpty, metavar='VERSION',
                help="Release to be deployed.")
        p.add_argument('environ', action=NotEmpty, metavar='ENVIRON',
                help="Environment to deploy into. " \
                     "Must be one of 'qa' or 'client'.")

    @staticmethod
    def run_release(args):
        assert args.version
        assert args.environ
        pivotal.check_version_format(args.version)

        gitflow = GitFlow()

        # Fetch remote refs.
        if not args.no_fetch:
            sys.stderr.write('Fetching origin ... ')
            gitflow.origin().fetch()
            print('OK')

        # Check the environ argument.
        branch = GitFlow().managers['release'].full_name(args.version)
        if args.environ not in ('qa', 'client'):
            raise DeploymentRequestError(branch, args.environ)

        if args.environ == 'client' and not args.no_check:
            #+++ Check if all stories were accepted by the client
            pt_release = pivotal.Release(args.version)
            print('Checking Pivotal Tracker stories ... ')
            pt_release.try_stage()
            print('OK')

            #+++ Check all relevant review requests in Review Board, to be sure
            rb_release = review.Release(pt_release)
            print('Checking if all relevant stories have been reviewed ... ')
            rb_release.try_stage(args.ignore_missing_reviews)
            print('OK')

        DeployCommand._run_deploy(args)

    #- master
    @classmethod
    def register_master(cls, parent):
        p = parent.add_parser('master', help='Deploy the master branch.')
        p.set_defaults(func=cls.run_master)

    @staticmethod
    def run_master(args):
        args.environ = 'production'
        DeployCommand._run_deploy(args)

    #- deploy helper method
    @staticmethod
    def _run_deploy(args):
        assert args.environ
        if args.environ in ('qa', 'client'):
            assert args.version

        gitflow = GitFlow()

        branches = {
                'develop':    gitflow.develop_name(),
                'qa':         gitflow.managers['release'].full_name(args.version),
                'production': gitflow.master_name(),
        }

        if gitflow.is_circleci_enabled():
            branches['client'] = gitflow.client_name()
            _deploy_circleci(gitflow, branches, args.environ)
        else:
            branches['client'] = gitflow.managers['release'].full_name(args.version)
            _deploy_jenkins(gitflow, branches, args.environ)


def _try_deploy_circleci(gitflow, version):
    # The repository must be completely clean for this step to proceed.
    try:
        output = sub.check_output(["git", "status", "--porcelain"])
    except sub.CalledProcessError as ex:
        sys.stderr.write("git status --porcelain failed\n")
        raise OperationsError(ex)

    lines = output.split('\n')
    for line in lines:
        # The only allowed files are these that are untracked. Any other scenario
        # can lead to git reset failing for one reason or another.
        if line == '' or line.startswith('??'):
            continue
        print("The repository is dirty!")
        print("git status --porcelain:")
        print(output)
        print("Commit or stash your changes, then retry.")
        raise SystemExit("Operation canceled.")

    # The release branch must exist.
    gitflow.name_or_current("release", version)

def _deploy_circleci(gitflow, branches, environ):
    repo = gitflow.repo
    git = repo.git

    sys.stdout.write('Pushing branch for CircleCI  ... ')
    sys.stdout.flush()

    # Make sure that the client branch is pointing to the right place.
    if environ == 'client':
        release = branches['qa']
        gitflow.must_be_uptodate(release)
        if gitflow.client_exists():
            current = gitflow.current_branch()
            git.checkout(gitflow.client_name())
            # Use --keep to make sure that local modification are not discarded.
            git.reset('--keep', release)
            git.checkout(current)
        else:
            git.branch(gitflow.client_name(), release)

    # Push the relevant branch to deploy it.
    branch = branches[environ]
    sys.stdout.write('pushing {0} ... '.format(branch))
    sys.stdout.flush()
    gitflow.origin().push([branch])
    print('OK')

def _deploy_jenkins(gitflow, branches, environ):
    # Make sure that the branch being deployed exists in origin.
    branch = branches[environ]
    sys.stderr.write("Checking whether branch '{0}' exists in origin ... " \
                     .format(branch))
    gitflow.require_origin_branch(branch)
    print('OK')

    # Trigger the job.
    jenkins = Jenkins.from_prompt()

    print('Triggering the deployment job (env being {0}) ... job {1} ... ' \
            .format(environ, jenkins.get_deploy_job_name(environ)))
    cause = 'Triggered by ' + gitflow.get('user.name') + \
        ' using the GitFlow plugin'
    url = jenkins.get_url_for_next_invocation(environ)
    invocation = jenkins.trigger_deploy_job(environ, cause)
    print('OK')

    print('\nThe job has been enqueued. You can visit\n\n\t{0}\n\n' \
            'to see the progress.'.format(url))


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
