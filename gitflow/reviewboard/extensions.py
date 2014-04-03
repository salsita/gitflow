""" Extensions and utility functions for Python Review Board API.
"""

import urllib
from .rb import Api20Client, make_rbclient
from operator import itemgetter


def is_story_approved(rb_server_url, story_id, auth=None):
    if not auth:
        auth = {'username': '', 'password': ''}
    rb_api = make_rbclient(rb_server_url, auth['username'], auth['password'])

    reviews_for_branch = rb_api.get_review_requests(branch=story_id)

    def is_shipited(review_request):
        # Get all the reviews for review requestr with id @review_request.
        reviews = rb_api.get_reviews_for_review_request(
            review_request['id'])
        # Return True if the review has been approved.
        return any(r['ship_it'] for r in reviews)

    return (len(reviews_for_branch) > 0 and
        all(is_shipited(r) for r in reviews_for_branch))

def get_latest_review_request_for_branch(rb_server_url, branch):
    """ Returns the most recently created review request in Reviewboard
        for a given branch (i.e., the request with the greatest id).
    """
    # Let the username and password be read from the cookie file.
    rb_api = make_rbclient(rb_server_url, '', '')
    reviews_for_branch = rb_api.get_review_requests(options=None, branch=branch)
    if reviews_for_branch:
        return max(reviews_for_branch, key=itemgetter('id'))
    else:
        return None


def get_reviews_for_review_request(self, rev_req_id):
    rsp = self._api_request(
        'GET', '/api/review-requests/%s/reviews/' % rev_req_id)
    return rsp['reviews']

Api20Client.get_reviews_for_review_request = get_reviews_for_review_request


def get_review_requests(self, options=None, branch=None):
    options = options or {}
    rsp = self._api_request(
        'GET', '/api/review-requests/?%s' % urllib.urlencode(options))
    requests = rsp['review_requests']
    if branch:
        return [r for r in requests if r['branch'] == branch]
    else:
        return requests

Api20Client.get_review_requests = get_review_requests
