# -*- coding: utf-8 ; ispell-local-dictionary: "american" -*-
"""
git-flow init
"""
#
# This file is part of `gitflow`.
# Copyright (c) 2010-2011 Vincent Driessen
# Copyright (c) 2012 Hartmut Goebel
# Distributed under a BSD-like license. For full terms see the file LICENSE.txt
#

import sys
import re

try:
    # this will trigger readline functionality for raw_input
    import readline
except:
    # readline is optional and may not be available on all installations
    pass

from gitflow.core import GitFlow as CoreGitFlow, warn, info
from gitflow.prompt import pick, ask

from gitflow.exceptions import (AlreadyInitialized, NotInitialized,
                                NoSuchLocalBranchError, NoSuchBranchError,
                                IllegalCommunicationProtocol, RemoteNotFound)

import gitflow.review as rb
import gitflow.pivotal as pt

__copyright__ = "2010-2011 Vincent Driessen; 2012 Hartmut Goebel"
__license__ = "BSD"


def _ensure_SSH():
    gitflow_origin = gitflow.get('gitflow.origin')
    try:
        origin_url = gitflow.get('remote.' + gitflow_origin + '.url')
    except Exception:
        raise RemoteNotFound(
                "Please configure git remote '{0}' before proceeding further." \
                        .format(gitflow_origin))
    if re.match('(https?://|git://)', origin_url):
        raise IllegalCommunicationProtocol("Only SSH remotes are supported.")
    if origin_url.startswith('ssh://'):
        origin_url = origin_url[6:].replace('/', ':', 1)
    if not origin_url.endswith('.git'):
        origin_url += '.git'
    CoreGitFlow().git.remote('set-url', gitflow_origin, origin_url)

class GitFlow(CoreGitFlow):

    @staticmethod
    def _has_configured(branch_func):
        try:
            branch_func()
        except (NotInitialized, IndexError):
            return False
        return True

    def has_master_configured(self):
        return self._has_configured(self.master)

    def has_stage_configured(self):
        return self._has_configured(self.stage)

    def has_develop_configured(self):
        return self._has_configured(self.develop)

    def get_default(self, setting):
        return self.get(setting, self.defaults[setting])
        

def _ask_branch(args, name, desc1, desc2, suggestions, filter=[]):
    # Two cases are distinguished:
    # 1. A fresh git repo (without any branches)
    #    We will create a new master/develop branch for the user
    # 2. Some branches do already exist
    #    We will disallow creation of new master/develop branches and
    #    rather allow to use existing branches for git-flow.
    askingForStage = name is 'stage'
    name = 'gitflow.branch.' + name
    default_name = gitflow.get_default(name)
    local_branches = [b
                      for b in gitflow.branch_names()
                      if b not in filter]
    if not local_branches:
        if not filter:
            print "No branches exist yet. Base branches must be created now."
        should_check_existence = False
        default_suggestion = default_name
    else:
        # Check unless we are picking up the stage branch.
        # That one is created automatically on deploy, it doesn't have to exist.
        should_check_existence = not askingForStage
        print
        print "Which branch should be used for %s?" % desc1
        for b in local_branches:
            print '  -', b
        for default_suggestion in [default_name] + suggestions:
            if default_suggestion in local_branches:
                break
        else:
            if askingForStage:
                # Show the default suggesting even though the local branch doesn't exist.
                # The stage branch is created automatically by GitFlow later.
                default_suggestion = default_name
            else:
                default_suggestion = ''

    if args.use_defaults and default_suggestion:
        print "Branch name for %s:" % desc2, default_suggestion
        branch_name = default_suggestion
    else:
        answer = raw_input("Branch name for %s: [%s] "
                           % (desc2, default_suggestion))
        branch_name = answer.strip() or default_suggestion
    if not branch_name:
        raise SystemExit('You need to give a branch name.')
    # check existence in case of an already existing repo
    if branch_name in filter:
        raise SystemExit("Production and integration branches should differ.")
    if should_check_existence:
        # if no local branch exists and a remote branch of the same
        # name exists, checkout that branch and use it for the local branch
        if not branch_name in local_branches:
            remote_name = gitflow.origin_name(branch_name)
            if remote_name in gitflow.branch_names(remote=True):
                branch = gitflow.repo.create_head(branch_name, remote_name)
                info("Created local branch %s based on %s."
                     % (branch_name, remote_name))
            else:
                raise NoSuchLocalBranchError(branch_name)

    # store the name of the develop branch
    gitflow.set(name, branch_name)
    return branch_name


def _ask_config(args, name, question):
    default_suggestion = gitflow.get_default(name)
    if args.use_defaults:
        print question +':', default_suggestion
        answer = default_suggestion
    else:
        answer = raw_input(question + '? [' + str(default_suggestion) + '] ')
        answer = answer.strip() or default_suggestion
        if answer == '-':
            answer = ''
    gitflow.set(name, answer)

def _ask_prefix(args, name, question):
    name = 'gitflow.prefix.' + name
    if not gitflow.get(name, None) or args.force:
        _ask_config(args, name, question)

def _ask_name(args, name, question):
    name = 'gitflow.' + name
    if not gitflow.get(name, None) or args.force:
        _ask_config(args, name, question)

def _ask_pt_projid(reuse_existing):
    pick('gitflow.pt.projectid', 'Pivotal Tracker projects', pt.list_projects,
         reuse_existing=reuse_existing)

def _ask_pt_labels(reuse_existing):
    include = ask('gitflow.pt.includelabel',
                  'Pivotal Tracker label to associate this repository with: ',
                  reuse_existing=reuse_existing)
    if include:
        gitflow.set('gitflow.pt.excludelabels', '')
        return
    ask('gitflow.pt.excludelabels',
        'Pivotal Tracker lables to exclude from this repository: ',
        reuse_existing=reuse_existing)

def _ask_rb_repoid(reuse_existing):
    pick('gitflow.rb.repoid', 'Review Board repositories', rb.list_repos,
         reuse_existing=reuse_existing)

def run_default(args):
    global gitflow
    gitflow = GitFlow()
    gitflow._enforce_git_repo()
    gitflow._enforce_services()

    if gitflow.is_initialized():
        if not args.force:
            raise AlreadyInitialized()

    if args.use_defaults:
        warn("Using default branch names.")

    #-- ask about Circle CI
    _ask_name(args, 'circleci.enabled',
            'Enable Circle CI integration [Y/n]')

    _ask_name(args, "origin", "Remote name to use as origin in git flow")
 
    # Make sure that origin uses SSH protocol for communication,
    # otherwise Review Board is going to fail.
    _ensure_SSH()

    #-- add a master branch if no such branch exists yet
    if gitflow.has_master_configured() and not args.force:
        master_branch = gitflow.master_name()
    else:
        master_branch = _ask_branch(args,
            'master',
            'bringing forth production releases',
            'production releases',
            ['production', 'main', 'master'])

    #-- add a develop branch if no such branch exists yet
    if gitflow.has_develop_configured() and not args.force:
        develop_branch = gitflow.develop_name()
    else:
        develop_branch = _ask_branch(args,
            'develop',
            'integration of the "next release"',
            '"next release" development',
            ['develop', 'int', 'integration', 'master'],
            filter=[master_branch])

    #-- ask for the staging branch in case CircleCI is enabled.
    if gitflow.is_circleci_enabled():
        if gitflow.has_stage_configured() and not args.force:
            stage_branch = gitflow.stage_branch()
        else:
            stage_branch = _ask_branch(args,
                'stage',
                'release client acceptance',
                'release client acceptance',
                ['stage'])

    if not gitflow.is_initialized() or args.force:
        print
        print "How to name your supporting branch prefixes?"

    _ask_prefix(args, "feature", "Feature branches")
    _ask_prefix(args, "release", "Release branches")
    _ask_prefix(args, "hotfix", "Hotfix branches")
    _ask_prefix(args, "support", "Support branches")
    _ask_prefix(args, "versiontag", "Version tag prefix")

    _ask_name(args, 'release.versionmatcher',
            'Regular expression for matching release numbers')

    _ask_name(args, 'pagination',
            'Number of stories to list on one page')

    _ask_pt_projid(args.use_defaults)
    _ask_pt_labels(args.use_defaults)
    _ask_rb_repoid(args.use_defaults)

    # assert the gitflow repo has been correctly initialized
    assert gitflow.is_initialized()

    gitflow.init(master_branch, develop_branch)
