import subprocess as sub
from gitflow.exceptions import GitflowError
import gitflow.core
import gitflow.pivotal as pivotal


def post_review(self, identifier, name, summary):
    mgr = self.managers[identifier]
    branch = mgr.by_name_prefix(name)

    proc = sub.Popen(
        ['git', 'reflog', 'show', branch.name],
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
    if not parent:
        raise GitflowError("Could not find parent for branch '%s'!" %
        branch.name)
        return

    story_id = pivotal.get_story_id_from_branch_name(branch.name)
    story = pivotal.get_story(story_id)

    cmd = ['post-review', '--branch', branch.name,
        '--guess-description', '--summary', "'%s'" % story['story']['name'],
        '--revision-range', '%s:%s' % (parent, branch.name)]

    print "Posting a review using command: %s" % ' '.join(cmd)
    sub.call(cmd)

def find_last_patch(self, branch_name):
    proc = sub.Popen(
        ['git', 'reflog', 'show', self.develop_name()],
        env={'GIT_PAGER': 'cat'}, stdout=sub.PIPE)


gitflow.core.GitFlow.post_review = post_review
