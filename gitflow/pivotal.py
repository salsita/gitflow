from gitflow.core import GitFlow
import busyflow.pivotal as pt
from colorama import Style
from colorama import init
init()
import sys
import re

from gitflow.exceptions import (NotInitialized, GitflowError)

def print_story(story, index=None, highlight_labels=[]):
    if index:
        sys.stdout.write(Style.BRIGHT + str(index) + ' : ' + Style.RESET_ALL)
    sys.stdout.write(colorize_string(story['name']))
    labels = []
    for label in story.get('labels', []):
        if label in highlight_labels:
            lblstr = Style.BRIGHT + str(label) + Style.RESET_ALL
        else:
            lblstr = str(label)
        labels.append(lblstr)
    sys.stdout.write(' ' + Style.DIM + ','.join(labels) + Style.RESET_ALL)
    sys.stdout.write(' (' + Style.DIM + str(story['current_state']) +
        Style.RESET_ALL + ')')
    sys.stdout.write('\n')


def filter_stories(stories, states, types=None):
    types = types or ['feature', 'chore', 'bug']
    return [s for s in stories if s['current_state'] in states and
        s['story_type'] in types]


def prompt_user_to_select_story():
    [current, backlog] = get_iterations()

    print Style.DIM + "--------- current -----------" + Style.RESET_ALL
    current_stories = filter_stories(
        [story for i in current['iterations'] for story in i['stories']],
        ['unstarted', 'started'])
    for i, s in enumerate(current_stories):
        print_story(s, i+1)

    print Style.DIM + "--------- backlog -----------" + Style.RESET_ALL

    offset = len(current_stories)
    backlog_stories = filter_stories(
        [story for i in backlog['iterations'] for story in i['stories']],
        ['unstarted', 'started'])
    for i, s in enumerate(backlog_stories):
        print_story(s, offset+i+1)

    stories = current_stories + backlog_stories
    # Prompt user to choose story index.
    print "Select story (or 'q' to quit): "
    index = raw_input()
    if index == "q":
        raise SystemExit("Operation canceled.")

    # We expect a number.
    try:
        index = int(index)
    except ValueError:
        raise GitflowError("Expected a number.")

    if not 0 < index <= len(stories):
        raise GitflowError("Invalid story index: %s." % index)

    # We're expecting input to start from 1, so we have to
    # subtract one here to get the list index.
    selected_story = stories[index - 1]

    slug = prompt_user_to_select_slug(selected_story)

    return [selected_story['id'], str(selected_story['id']) + '/' + slug]


def prompt_user_to_select_slug(story):
    print ("Please choose short story description (will be slugified " +
        "and used in the branch label).")
    slug_hint = slugify(get_story_bold_part(story['name']))
    print "Story description (default: '%s'):" % slug_hint
    slug = raw_input().strip() or slug_hint
    return slug


def get_story_bold_part(story_name):
    """
        >>> get_story_bold_part("*This is the bold part*, this is not.")
        'This is the bold part'
    """
    if not '*' in story_name:
        return story_name
    else:
        return re.sub(r'.*\*(.+)\*.*', r'\1', story_name)


def slugify(story_name, max_length=25):
    """
        >>> slugify(' Just a story name ')
        'just-a-story-name'
        >>> slugify('Just_a_story_name')
        'just_a_story_name'
        >>> slugify('Just_a_story_name_but_a_very_long_one_indeed...')
        'just_a_story_name_but_a_'
        >>> slugify('Just a story name but a very long one indeed...')
        'just-a-story-name-but-a'
    """
    # Inspired by Django.
    value = re.sub('[^\w\s-]', '', story_name).strip().lower()
    value = re.sub('[-\s]+', '-', value)
    if len(value) > max_length:
        value = value[:max_length]
        return value[:(value.rfind('-'))]
    else:
        return value


def get_iterations():
    gitflow = GitFlow()
    token = gitflow.get('workflow.token')
    project_id = gitflow.get('workflow.projectid')
    client = pt.PivotalClient(token=token)
    current = client.iterations.current(project_id)
    backlog = client.iterations.backlog(project_id)
    return [current, backlog]


def update_story(story_id, **kwargs):
    gitflow = GitFlow()
    token = gitflow.get('workflow.token')
    project_id = gitflow.get('workflow.projectid')
    client = pt.PivotalClient(token=token)
    client.stories.update(
        project_id=project_id, story_id=story_id, **kwargs)


def get_story(story_id):
    gitflow = GitFlow()
    token = gitflow.get('workflow.token')
    project_id = gitflow.get('workflow.projectid')
    client = pt.PivotalClient(token=token)
    return client.stories.get(project_id=project_id, story_id=story_id)


def finish_story(story_id):
    story = get_story(story_id)
    if story['story']['story_type'] == 'chore':
        labels = story['story'].get('labels', [])
        if not 'waiting-for-review' in labels:
            labels += ['waiting-for-review']
            update_story(story_id, labels=labels)
    else:
        update_story(story_id, current_state='finished')


def colorize_string(string):
    """ Use ANSI color codes to emulate a simple subset of textile formatting.
        We're supporting '*' (bold).

        Note: Requires 'termcolor' Python module. If not installed, this
        function just returns the string passed in.
    """
    # Remove escaped parts.
    tmp = re.sub('==.*==', '', string)
    bolds = re.findall('\*.+\*', tmp)
    for bold in bolds:
        stripped_asterisks = (Style.BRIGHT + bold.replace('*', '') +
            Style.RESET_ALL)
        tmp = tmp.replace(bold, stripped_asterisks)
    return tmp

def get_story_id_from_branch_name(branch_name):
    match = re.match('^.+/([0-9]+)[/-]?.*$', branch_name)
    if not match:
        # Gitflow identifier has already been stripped.
        match = re.match('^([0-9]+)[/-]?.*$', branch_name)
        if not match:
            raise GitflowError('Weird branch name format: %s' % branch_name)
    return match.groups()[0]


def show_release_summary(gitflow):
    current = get_iterations()[0]
    current_stories = [
        story for i in current['iterations'] for story in i['stories']]

    print Style.BRIGHT + 'Releasable stories:' + Style.RESET_ALL
    candidate_chores = filter_stories(
        current_stories, ['started'], types=['chore'])
    releasable_chores = [chore for chore in candidate_chores
        if 'reviewed' in chore.get('labels', [])]
    candidate_stories = filter_stories(
        current_stories, ['finished'], types=['bug', 'feature'])
    releasable_stories = [s for s in candidate_stories
        if set(['reviewed', 'qa+']).issubset(set(s.get('labels', [])))]
    for item in releasable_stories + releasable_chores:
        sys.stdout.write(' > ')
        print_story(item)

    print Style.BRIGHT + 'Unreleasable stories:' + Style.RESET_ALL
    unreleasable = [item for item in current_stories
        if not item in releasable_chores and not item in releasable_stories]
    for item in unreleasable:
        sys.stdout.write(' < ')
        print_story(item, highlight_labels=['qa+', 'reviewed'])

    #TODO(Tom): Better release summary based on what's already been merged...
    #lines = gitflow.git.log(
    #    '--show-notes=workflow', '--oneline', '--format="%H %N"').split('\n')
    #finished_stories = []
    #for line in lines:
    #    parts = line.split(' ')
    #    if len(parts) == 3:
    #        (hash, op, story_id) = parts
    #        if op == 'finish':
    #            finished_stories.append((hash, story_id))

    #lines = gitflow.git.log('--oneline', '--format="%h %s"').split('\n')
    ##merges = [l for l in lines if l.split(' ')[1].lower() == 'merge']
    #merged_branches = []
    #for line in lines:
    #    match = re.match(
    #        "(.+)\ Merge\ branch\ '(.+)'\ into %s" % gitflow.develop_name(),
    #        line)
    #    if match:
    #        (hash, branch) = match.groups()
    #        if not branch in merged_branches:
    #            merged_branches.append(branch)
    #print merged_branches
    #releasable = releasable_stories + releasable_chores
    #for story in releasable:
    #    stories_merged_before_this_story = \
    #        set([get_story_id_from_branch_name(s) for s in \
    #            merged_branches[merged_branches.index(story) + 1 : ]])
    #    blockers = stories_merged_before_this_story.intersection(
    #        [s['id'] for s in unreleasable])
    #    if blockers:
    #        print "Story '%s' is blocked by stories: %s" % (story, blockers)
    #import ipdb; ipdb.set_tracce()
