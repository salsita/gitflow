import ConfigParser
import getpass
import sys

from .core import GitFlow, MAGIC_STRING

def ask(option, question, set_globally=False, secret=False, is_valid=None,
        reuse_existing=True):

    gitflow = GitFlow()
    git = gitflow.repo.git

    answer = None
    try:
        if not reuse_existing:
            raise ConfigParser.NoOptionError(option, 'Not using the existing value')

        answer = gitflow.get(option)
        if isinstance(answer, basestring):
            answer = answer.replace(MAGIC_STRING, '-')
    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
        while True:
            if secret:
                answer = getpass.getpass(question)
            else:
                answer = raw_input(question)
            if is_valid is None or is_valid(answer):
                break

        raw_answer = answer.replace('-', MAGIC_STRING)
        if set_globally:
            git.config('--global', option, raw_answer)
        else:
            gitflow.set(option, raw_answer)
    return answer

def pick(option, title, source, reuse_existing=True):
    # Try to get the option from config first.
    gitflow = GitFlow()
    try:
        if not reuse_existing:
            raise ConfigParser.NoOptionError(option, 'Not using the existing value')

        opt = gitflow.get(option)
        if isinstance(opt, basestring):
            opt = opt.replace(MAGIC_STRING, '-')
        return opt
    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
        pass

    # Get the suggestions list.
    suggestions = source()
    if len(suggestions) == 0:
        raise SystemExit('No {0} available, exiting...'.format(title))

    # If that fails, ask the user to pick up one of the values.
    print
    print 'Please choose one of the following %s:' % title
    msg = '    Loading...'
    sys.stdout.write(msg)
    sys.stdout.flush()
    sys.stdout.write('\r' * len(msg))

    answer = None
    while not answer:
        i = 0
        for sid, sname in suggestions:
            i += 1
            print '    [%d] %s' % (i, sname)
        inpt = raw_input("Insert the sequence number (or 'q' to quit): ")
        if inpt == 'q':
            raise SystemExit('Operation canceled.')
        try:
            a = int(inpt)
        except ValueError:
            print 'Please specify a number betweet 1 and %i:' % i
            continue
        if a >= 1 and a <= i:
            answer = suggestions[a-1][0]

    value = answer
    if isinstance(answer, basestring):
        value = answer.replace('-', MAGIC_STRING)
    gitflow.set(option, value)
    return answer
