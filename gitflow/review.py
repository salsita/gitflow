import re
import subprocess as sub
import difflib as diff
import gitflow.pivotal as pivotal
import reviewboard.extensions as rb_ext
import gitflow.core as core
import sys

from gitflow.core import GitFlow
from gitflow.exceptions import (GitflowError, MultipleReviewRequestsForBranch,
                                NoSuchBranchError, AncestorNotFound, EmptyDiff)


class ReviewNotAcceptedYet(GitflowError): pass

_gitflow = GitFlow()

def _get_repo_id():
    return _gitflow._safe_get('gitflow.rb.repoid')

def _get_server():
    return _gitflow._safe_get('reviewboard.server')

def _get_url():
    return _gitflow._safe_get('reviewboard.url')

def _get_client():
    return rb_ext.make_rbclient(_get_server(), '', '')

def _get_develop_name():
    return _gitflow.develop_name()

def _get_branch(identifier, name):
    prefix = _gitflow.get_prefix(identifier)
    name = _gitflow.nameprefix_or_current(identifier, name)
    return prefix + name


def list_repos():
    repos = _get_client().repositories()
    return [(r.id, r.name) for r in repos]


class BranchReview(object):
    def __init__(self, branch, rev_range=None):
        assert rev_range is None or len(rev_range) == 2
        self._branch = branch
        self._client = _get_client()
        if rev_range:
            self._rev_range = rev_range

    def __getattr__(self, name):
        if name == '_rid':
            self._rid = self._branch_to_rid(self._branch)
            return self._rid
        raise AttributeError

    def get_id(self):
        return self._rid

    def get_url(self):
        if self._url:
            return self._url
        elif self.get_id():
            return '{0}r/{1}/'.format(_get_url(), self.get_id())
        else:
            raise AttributeError('Neither review id nor review url is defined.')

    def post(self, summary=None, desc=None):
        assert self._rev_range
        cmd = ['rbt', 'post',
               '--branch', self._branch,
               '--revision-range={0[0]}:{0[1]}'.format(self._rev_range)]
        if summary is None or desc is None:
            cmd.append('--guess-fields')
        else:
            cmd.append('--summary=' + str(summary))
            cmd.append('--description=' + str(desc))

        if self._rid:
            sys.stdout.write('updating %s ... ' % str(self._rid))
            cmd.append('--review-request-id')
            cmd.append(str(self._rid))
        else:
            sys.stdout.write('new review ... ')
        output = sub.check_output(cmd)
        print
        print
        print '>>> rbt output'
        print output
        print '<<< rbt output'

        # Use list comprehension to get rid of emply trailing strings.
        self._url = [line for line in output.split('\n') if line != ''][-1]
        self._rid = [f for f in self._url.split('/') if f != ''][-1]

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
    def from_prefix(cls, prefix):
        client = _get_client()
        options = dict(repository=_get_repo_id(), status='all')
        reviews = [r for r in client.get_review_requests(options=options)
                     if r['branch'].startswith(prefix)]
        if len(reviews) == 0:
            raise NoSuchBranchError(
                    'No review request found for branch prefixed with ' + prefix)
        elif len(reviews) == 1:
            r = reviews[0]
            t = type('BranchReview', (cls,), dict(_rid=r['id']))
            return t(r['branch'])
        else:
            raise MultipleReviewRequestsForBranch(r['branch'])

    @classmethod
    def from_identifier(cls, identifier, name, rev_range=None):
        prefix = _gitflow.get_prefix(identifier)
        name = _gitflow.nameprefix_or_current(identifier, name)
        return cls(prefix + name, rev_range)


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

def get_feature_ancestor(feature):
    repo = _gitflow.repo
    develop = _gitflow.develop_name()

    # Check if we are not looking for the ancestor of the same commit.
    # If that is the case, the algorithm used further fails.
    fc = repo.commit(feature)
    dc = repo.commit(develop)
    if fc == dc:
        raise EmptyDiff('{0} and {1} are pointing to the same commit.' \
                .format(develop, feature))

    # Get all commits being a part of the respective branches.
    develop_ancestors = sub.check_output(
            ['git', 'rev-list', '--first-parent', develop])
    feature_ancestors = sub.check_output(
            ['git', 'rev-list', '--first-parent', feature])

    # Compute the diff between the lists.
    ancestor_diff = diff.unified_diff(
            develop_ancestors.split('\n'), feature_ancestors.split('\n'))

    ancestor = None
    # The first line to match this is the ancestor we are looking for.
    pattern = re.compile(' [0-9a-f]{40}$')
    for line in ancestor_diff:
        if pattern.match(line):
            ancestor = line.strip()
            break

    # Not sure this can really happen, but just to be sure.
    # This happens usually when you compare a commit with itself,
    # but that is already being taken care of at the beginning of the function.
    if ancestor is None:
        raise AncestorNotFound('No common ancestor of {0} and {1} found.' \
                .format(develop, feature))

    # Just to be sure, explode as soon as possible.
    assert ancestor
    return ancestor
