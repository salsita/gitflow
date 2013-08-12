import ConfigParser
import getpass
import sys

from .core import GitFlow

MAGIC_STRING = 'dKkvQvtBsd9DkQfMJkya'

def ask(option, question, set_globally=False, secret=False):
    gitflow = GitFlow()
    git = gitflow.repo.git

    answer = None
    while not answer:
        try:
            answer = gitflow.get(option)
            if isinstance(answer, basestring):
                answer = answer.replace(MAGIC_STRING, '-')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            while not answer:
                if secret:
                    answer = getpass.getpass(question)
                else:
                    answer = raw_input(question)
            raw_answer = answer.replace('-', MAGIC_STRING)
            if set_globally:
                git.config('--global', option, raw_answer)
            else:
                gitflow.set(option, raw_answer)
    assert answer
    return answer

def pick(option, title, source):
    # Try to get the option from config first.
    gitflow = GitFlow()
    try:
        opt = gitflow.get(option)
        if isinstance(opt, basestring):
            opt = opt.replace(MAGIC_STRING, '-')
        return opt
    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
        pass

    # If that fails, ask the user to pick up one of the values.
    print
    print 'Please choose one of the following %s:' % title
    msg = '    Loading...'
    sys.stdout.write(msg)
    sys.stdout.flush()
    suggestions = source()
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

    if isinstance(answer, basestring):
        answer = answer.replace('-', MAGIC_STRING)
    gitflow.set(option, answer)
    return answer
