import subprocess as sub
import gitflow.pivotal as pivotal
import reviewboard.extensions as rb_ext
import gitflow.core as core
import sys

from gitflow.core import GitFlow
from gitflow.exceptions import (GitflowError, MultipleReviewRequestsForBranch,
                                NoSuchBranchError)


class ReviewNotAcceptedYet(GitflowError): pass

_gitflow = GitFlow()

def _get_repo_id():
    return _gitflow.get('reviewboard.repoid')

def _get_server():
    return _gitflow.get('reviewboard.server')

def _get_develop_name():
    return _gitflow.develop_name()

def _get_branch(identifier, name):
    prefix = _gitflow.get_prefix(identifier)
    name = _gitflow.nameprefix_or_current(identifier, name)
    return prefix + name


class BranchReview(object):
    def __init__(self, branch, upstream=None):
        assert branch in _gitflow.repo.refs
        self._branch = branch
        self._upstream = upstream
        self._client = rb_ext.make_rbclient(_get_server(), '', '')

    def __getattr__(self, name):
        if name == '_rid':
            self._rid = self._branch_to_rid(self._branch)
            return self._rid
        raise AttributeError

    def get_id(self):
        return self._rid

    def post(self):
        assert self._upstream
        cmd = ['rbt', 'post',
               '--branch', self._branch,
               '--parent', self._upstream,
               '--guess-fields']
        if self._rid:
            sys.stdout.write('updating %s ... ' % str(self._rid))
            cmd.append('--review-request-id')
            cmd.append(str(self._rid))
        else:
            sys.stdout.write('new review ... ')
        print
        print
        print '>>> rbt output'
        sub.check_call(cmd)
        print '<<< rbt output'
        print

    def submit(self):
        assert self._rid
        if not self.is_accepted():
            raise ReviewNotAcceptedYet('review %s not accepted yet' \
                                       % str(self._rid))
        self._update(status='submitted')

    def is_accepted(self):
        assert self._rid
        reviews = self._client.get_reviews_for_review_request(self._rid)
        return any(r['ship_it'] for r in reviews)

    def _update(self, **kwargs):
        self._client.update_request(self.get_id(), fields=kwargs, publish=True)

    def _branch_to_rid(self, branch):
        options = dict(repository=_get_repo_id())
        reviews = self._client.get_review_requests(options=options,
                                                   branch=self._branch)
        if len(reviews) > 1:
            raise MultipleReviewRequestsForBranch(self._branch)
        elif len(reviews) == 1:
            return reviews[0]['id']

    @classmethod
    def from_prefix(cls, prefix, upstream=None):
        client = rb_ext.make_rbclient(_get_server(), '', '')
        options = dict(repository=_get_repo_id())
        reviews = client.get_review_requests(options=options)
        for review in reviews:
            if review['branch'].startswith(prefix):
                t = type('BranchReview', (cls,), dict(_rid=review['id']))
                return t(review['branch'], upstream)
        raise NoSuchBranchError('no review for branch prefixed with ' + prefix)

    @classmethod
    def from_identifier(cls, identifier, name, upstream=None):
        prefix = _gitflow.get_prefix(identifier)
        name = _gitflow.nameprefix_or_current(identifier, name)
        return cls(prefix + name, upstream)


def post_review(self, identifier, name, post_new):
    mgr = self.managers[identifier]
    branch = mgr.by_name_prefix(name)

    sys.stdout.write("Walking the Git reflogs to find review request parent (might "
        "take a couple seconds)...\n")
    sys.stdout.flush()

    if not post_new:
        parent = find_last_patch_parent(self.develop_name(), branch.name)
        if not parent:
            print ("Could not find any merges into %s, using full patch." %
                self.develop_name())
    if not parent:
        parent = get_branch_parent(branch.name)

    if not parent:
        raise GitflowError("Could not find parent for branch '%s'!" %
            branch.name)

    story_id = pivotal.get_story_id_from_branch_name(branch.name)
    story = pivotal.get_story(story_id)

    cmd = ['post-review', '--branch', branch.name,
        '--guess-description',
        '--parent', self.develop_name(),
        '--revision-range', '%s:%s' % (parent, branch.name)]

    if post_new:
        # Create a new request.
        cmd += ['--summary', "'%s'" % story['story']['name']]
    else:
        req = rb_ext.get_latest_review_request_for_branch(
            _gitflow.get('reviewboard.server'), branch.name)
        if req:
            # Update an existing request.
            cmd += ['-r', str(req['id'])]
        else:
            # Create a new request.
            cmd += ['--summary', "'%s'" % story['story']['name']]

    print "Posting a review using command: %s" % ' '.join(cmd)
    proc = sub.Popen(cmd, stdout=sub.PIPE)
    (out, err) = proc.communicate()
    # Post a comment to the relevant Pivotal Tracker story (to make it easier to
    # track review requests).
    review_url = out.strip().split('\n')[-1]
    if not review_url.startswith('http'):
        print ("Could not determine review URL (probably an error when "
            "posting the review")
        return
    if '-r' in cmd:
        comment = "Review request %s updated."
    else:
        comment = "Review request posted: %s"
    pivotal.add_comment_to_story(story_id, comment % review_url)

core.GitFlow.post_review = post_review


def get_branch_parent(branch_name):
    proc = sub.Popen(
        ['git', 'reflog', 'show', branch_name],
        env={'GIT_PAGER': 'cat'}, stdout=sub.PIPE)
    (out, err) = proc.communicate()
    lines = out.strip().split('\n')
    parent = None
    for line in lines:
        parts = line.split(' ')
        if len(parts) >= 3 and (parts[2]).startswith('branch'):
            parent = parts[0]
    if not parent:
        parent = lines[-1].split(' ')[0]
    return parent


def find_last_patch_parent(develop_name, branch_name):
    proc = sub.Popen(
        ['git', 'reflog', 'show', develop_name],
        env={'GIT_PAGER': 'cat'}, stdout=sub.PIPE)
    (out, err) = proc.communicate()
    lines = out.strip().split('\n')
    lines = [l for l in lines if ("merge %s" % branch_name) in l]
    if len(lines) < 2:
        return None
    else:
        # Get the hash of the second most recent merge.
        return lines[1].split(' ')[0]

