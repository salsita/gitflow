import re
import subprocess as sub
import difflib as diff
import gitflow.pivotal as pivotal
import reviewboard.extensions as rb_ext
import gitflow.core as core
import sys

from gitflow.core import GitFlow
from gitflow.exceptions import (GitflowError, MultipleReviewRequestsForBranch,
                                NoSuchBranchError, AncestorNotFound, EmptyDiff,
                                PostReviewError, SubmitReviewError)

class ReviewRequestLimitError(GitflowError):
    def __str__(self):
        return 'Too many code review requests: {0}'.format(self.args[0])

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
            self._update_from_existing_review()
            return self._rid
        if name == '_summary':
            return None
        if name == '_description':
            return None
        raise AttributeError

    def get_id(self):
        assert self._rid
        return self._rid

    def get_url(self):
        if self._url:
            return self._url
        elif self.get_id():
            return '{0}r/{1}/'.format(_get_url(), self.get_id())
        else:
            raise AttributeError('Neither review id nor review url is defined.')

    def post(self, story, summary_from_story=True):
        assert self._rev_range

        def to_unicode(s):
            try:
                return unicode(s)
            except UnicodeDecodeError:
                return unicode(s, encoding='utf8')

        def to_string(us):
            try:
                return str(us)
            except UnicodeEncodeError:
                return us.encode(encoding='utf8')

        cmd = ['rbt', 'post',
               '--branch', self._branch]

        self._check_for_existing_review()

        desc_cmd = ['git', 'log',
                    "--pretty="
                        "--------------------%n"
                        "Author:    %an <%ae>%n"
                        "Committer: %cn <%ce>%n"
                        "%n"
                        "%s%n%n"
                        "%b",
                    '{0[0]}...{0[1]}'.format(self._rev_range)]
        desc_prefix = u'> Story being reviewed: {0}\n'.format(story.get_url())
        desc = desc_prefix + u'\nCOMMIT LOG\n' + to_unicode(sub.check_output(desc_cmd))

        if summary_from_story:
            summary = story.get_name()
        else:
            # 7 is the magical offset to get the first commit subject
            summary = desc.split('\n')[7]

        # If we are updating an existing review, reuse its summary.
        if self._summary is not None:
            summary = self._summary

        # If we are updating an existing review, reuse part of its description.
        if self._description is not None:
            lines = self._description.split('\n')
            kept_desc = []
            for line in lines:
                if line.startswith('> Story being reviewed'):
                    break
                kept_desc.append(to_unicode(line))
            desc = u'\n'.join(kept_desc) + u'\n' + to_unicode(desc)

        if self._rid:
            sys.stdout.write('updating %s ... ' % str(self._rid))
            cmd.append('--review-request-id')
            cmd.append(str(self._rid))
        else:
            sys.stdout.write('new review ... ')

        cmd.append(u'--summary=' + to_unicode(summary))
        cmd.append(u'--description=' + to_unicode(desc))
        cmd.extend([str(rev) for rev in self._rev_range])
        cmd = [to_string(itm) for itm in cmd]

        p = sub.Popen(cmd, stdout=sub.PIPE, stderr=sub.PIPE)
        (outdata, errdata) = p.communicate()

        if p.returncode == 0:
            print('OK')
            print('>>>> rbt output')
            print(outdata)
            print('<<<< rbt output')
        else:
            debug_cmd = ' '.join(cmd[:-4])
            debug_cmd += " --summary='{0}' --description='{1}' --debug " \
                         .format(summary, desc_prefix)
            debug_cmd += ' '.join(cmd[-2:])
            print('FAIL')
            print('>>>> rbt error output')
            print(errdata)
            print('<<<< rbt error output')
            print('If the error output is not sufficient, execute')
            print('\n    $ {0}\n'.format(debug_cmd))
            print('and see what happens.')
            raise PostReviewError('Failed to post review request.')

        # Use list comprehension to get rid of emply trailing strings.
        self._url = [line for line in outdata.split('\n') if line != ''][-1]
        self._rid = [f for f in self._url.split('/') if f != ''][-1]

    def verify_submit(self):
        assert self._status
        if self._status == 'submitted':
            return
        assert self._rid
        if not self.is_accepted():
            raise ReviewNotAcceptedYet('Review %s has not been accepted yet' \
                                       % str(self._rid))

    def submit(self):
        assert self._status
        if self._status == 'submitted':
            return

        cmd = ['rbt', 'close', '--close-type', 'submitted', str(self.get_id())]
        p = sub.Popen(cmd, stdout=sub.PIPE, stderr=sub.PIPE)
        (outdata, errdata) = p.communicate()

        if p.returncode != 0:
            print('>>>> rbt error output')
            print(errdata)
            print('<<<< rbt error output')
            print('If the error output is not sufficient, execute')
            print('\n    $ rbt close --debug --close-type submitted {0}\n'.format(self.get_id()))
            print('and see what happens.')
            raise SubmitReviewError('Failed to submit review request.')

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
            r = reviews[0]
            self._summary = r['summary']
            self._description = r['description']
            return r['id']

    def _check_for_existing_review(self):
        assert self._branch
        self._rid = self._branch_to_rid(self._branch)

    @classmethod
    def from_prefix(cls, prefix):
        client = _get_client()
        options = {'repository': _get_repo_id(), 'status': 'pending', 'max-results': 200}
        requests = client.get_review_requests(options=options)
        if len(requests) == 200:
            raise ReviewRequestLimitError(200)

        reviews = [r for r in requests if r['branch'].startswith(prefix) and \
                                          r['status'] != 'discarded']
        if len(reviews) == 0:
            raise NoSuchBranchError(
                    'No review request found for branch prefixed with ' + prefix)
        elif len(reviews) == 1:
            r = reviews[0]
            t = type('BranchReview', (cls,),
                    dict(_rid=r['id'], _status=r['status']))
            return t(r['branch'])
        else:
            raise MultipleReviewRequestsForBranch(reviews[0]['branch'])

    @classmethod
    def from_identifier(cls, identifier, name, rev_range=None):
        prefix = _gitflow.get_prefix(identifier)
        name = _gitflow.nameprefix_or_current(identifier, name)
        return cls(prefix + name, rev_range)


class Release(object):
    def __init__(self, stories):
        self._G = GitFlow()
        self._stories = stories

    def try_stage(self, ignore_missing_reviews):
        assert self._stories
        feature_prefix = self._G.get_prefix('feature')

        self._reviews = []
        reviews_expected = 0
        err = None

        for story in self._stories:
            label = None
            for l in ('no review', 'dupe', 'wontfix', 'cannot reproduce'):
                if story.is_labeled(l):
                    label = l
                    print("    Story {0} labeled '{1}', skipping...".format(story.get_id(), l))
                    break
            if label is not None:
                continue

            prefix = feature_prefix + str(story.get_id())
            try:
                reviews_expected += 1
                review = BranchReview.from_prefix(prefix)
                review.verify_submit()
                print('    ' + str(review.get_id()))
                self._reviews.append(review)
            except (ReviewNotAcceptedYet, NoSuchBranchError) as e:
                print('    ' + str(e))
            except Exception as e:
                print('    ' + str(e))
                err = e
        if err is not None:
            raise SystemExit(str(err))
        if not ignore_missing_reviews and len(self._reviews) != reviews_expected:
            raise SystemExit('Some stories have not been reviewed yet,' \
                    ' aborting...')

    try_finish = try_stage

    def finish(self):
        assert self._reviews is not None
        for review in self._reviews:
            review.submit()

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

def get_feature_ancestor(feature, upstream):
    repo = _gitflow.repo

    # Check if we are not looking for the ancestor of the same commit.
    # If that is the case, the algorithm used further fails.
    fc = repo.commit(feature)
    uc = repo.commit(upstream)
    if fc == uc:
        raise EmptyDiff('{0} and {1} are pointing to the same commit.' \
                .format(upstream, feature))

    base_marker = _gitflow.managers['feature'].base_marker_name(feature)
    for ref in repo.refs:
        if str(ref) == base_marker:
            return ref

    raise AncestorNotFound('Base marker missing for ' + feature)
