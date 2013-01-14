from gitflow.core import GitFlow
import busyflow.pivotal as pt
from colorama import Style
import sys
import re

from gitflow.exceptions import (NotInitialized, GitflowError)

def print_story(index, story):
    sys.stdout.write(Style.BRIGHT + str(index) + ' : ' + Style.RESET_ALL)
    sys.stdout.write(colorize_string(story['name']))
    sys.stdout.write(' ' + Style.DIM + str(story.get('labels', "")) + Style.RESET_ALL)
    sys.stdout.write(' (' + Style.DIM + str(story['current_state']) +
        Style.RESET_ALL + ')')
    sys.stdout.write('\n')


def filter_stories(stories):
    return [s for s in stories if s['current_state'] in ['unstarted', 'started']]


def prompt_user_to_select_story():
    [current, backlog] = get_iterations()

    current_stories = []
    for iter in current['iterations']:
        current_stories = current_stories + filter_stories(iter['stories'])
    for i, s in enumerate(current_stories):
        print_story(i+1, s)

    offset = len(current_stories)
    backlog_stories = []
    for iter in backlog['iterations']:
        backlog_stories = backlog_stories + filter_stories(iter['stories'])
    for i, s in enumerate(backlog_stories):
        print_story(offset+i+1, s)

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
