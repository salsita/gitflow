import re
import datetime
import subprocess as sub
import difflib as diff
import gitflow.pivotal as pivotal
import reviewboard.extensions as rb_ext
import gitflow.core as core
import sys

from gitflow.core import GitFlow
from gitflow.exceptions import (GitflowError, MultipleReviewRequestsForBranch,
                                NoSuchBranchError, AncestorNotFound, EmptyDiff,
                                PostReviewError)

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

def _get_existing_review_requests(story):
    pass

def list_repos():
    repos = _get_client().repositories()
    return [(r.id, r.name) for r in repos]


class ReviewRequestSet(object):
    # ReviewRequestSet represents all the review requests associated with
    # one particular Pivotal Tracker story.
    def __init__(self, story):
        self._story = story
        self._client = _get_client()

    def add_review_request(self, from_rev, to_rev, summary_from_story=False):
        cmd = ['rbt', 'post',
               '--branch', self._branch]

        last = self._get_last_rr()
        if last != None:
            cmd.append('--depends-on={0}'.format(last.id))

        desc_cmd = ['git', 'log',
                    "--pretty="
                        "--------------------%n"
                        "Author:    %an <%ae>%n"
                        "Committer: %cn <%ce>%n"
                        "%n"
                        "%s%n%n"
                        "%b",
                    '{0}...{1}'.format(from_rev, to_rev)]
        desc_prefix = '> Story being reviewed: {0}\n'.format(story.get_url())
        desc = desc_prefix + '\nCOMMIT LOG\n' + sub.check_output(desc_cmd)

        if summary_from_story:
            summary = story.get_name()
        else:
            # 7 is the magical offset to get the first commit subject
            summary = desc.split('\n')[7]

        cmd.append('--summary=' + summary.decode('utf8'))
        cmd.append('--description=' + desc.decode('utf8'))
        cmd.append('{0}...{1}'.format(from_rev, to_rev))

        p = sub.Popen(cmd, stdout=sub.PIPE, stderr=sub.PIPE)
        (outdata, errdata) = p.communicate()

        if p.returncode == 0:
            print('OK')
            print('>>>> rbt output')
            print(outdata)
            print('<<<< rbt output')
        else:
            debug_cmd = ' '.join(cmd[:-2])
            debug_cmd += " --summary='{0}' --description='{1}' --debug" \
                         .format(summary, desc_prefix)
            print('FAIL')
            print('>>>> rbt error output')
            print(errdata)
            print('<<<< rbt error output')
            print('If the error output is not sufficient, execute')
            print('\n    $ {0}\n'.format(debug_cmd))
            print('and see what happens.')
            raise PostReviewError('Failed to post review request.')

    def verify_submit(self):
        assert self._status
        if self._status == 'submitted':
            return
        assert self._rid
        if not self.is_accepted():
            raise ReviewNotAcceptedYet('Review %s has not been accepted yet' \
                                       % str(self._rid))

    def submit(self):
        rrs = self._get_existing_rrs()
        for rr in rrs:
            if self._status == 'submitted':
                continue
            self._update(rr, status='submitted')

    def is_accepted(self):
        assert self._rid
        reviews = self._client.get_reviews_for_review_request(self._rid)
        return any(r['ship_it'] for r in reviews)

    def _update(self, rr, **kwargs):
        self._client.update_request(rr.id, fields=kwargs, publish=True)

    def _get_last_rr(self):
        # Get existing review requests.
        rrs = self._get_existing_rrs()
        if len(rrs) == 0:
            return None

        # Choose the most recent review request from the set.
        last = rss[0]
        last_timestamp = datetime.strftime(last.time_added, '%Y-%m-%d %H:%M:%S')
        for rr in rrs[1:]:
            timestamp = datetime.strftime(last.time_added, '%Y-%m-%d %H:%M:%S')
            if timestamp > last_timestamp:
                last = rr
                last_timestamp = timestamp
        return last

    def _get_existing_rrs(self):
        # Reuse what was already downloaded, if possible.
        if self._rrs:
            return self._rrs

        # Unfortunately here we have to fetch all the review requests
        # associated with the project repository since we need to check
        # the branch prefix. The good thing is that we only fetch the review
        # requests owned by the user that is running gitflow.
        options = {
                'repository': _get_repo_id(),
                'from-user': _get_rb_username(),
                'max-results': 200
        }
        candidates = self._client.get_review_requests(options=options)

        # Get only the branches matching the same story prefix.
        branch_prefix = self._get_branch_prefix()
        self._rrs = [rr for rr in candidates if rr.branch.startswith(branch_prefix)]
        return self._rrs

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
