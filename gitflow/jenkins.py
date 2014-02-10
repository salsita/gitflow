import ConfigParser
import getpass
import jenkinsapi.jenkins
import requests
import signal
import sys
import urlparse

from .core import GitFlow, requires_initialized
from .prompt import ask, pick
from .exceptions import (ObjectError, GitflowError)


class DeployJobNotFoundError(ObjectError):
    def __str__(self):
        return 'Jenkins job {0} not found'.format(self.args[0])

class DeploymentRequestError(GitflowError):
    def __str__(self):
        return "You cannot deploy branch {0[0]} into the {0[1]} environment" \
                .format(self.args)

class Jenkins(object):
    def __init__(self, username, password):
        assert username
        assert password
        self._G = GitFlow()
        self._J = jenkinsapi.jenkins.Jenkins(self._get_jenkins_url(),
                username, password)

    def trigger_deploy_job(self, environ, cause=None):
        return self._get_deploy_job(environ).invoke(
                securitytoken=self._get_deploy_job_token(environ), cause=cause)

    def _get_jenkins_url(self):
        prev_handler = None

        def handler(signum, frame):
            try:
                self._G.delete('gitflow.jenkins.url')
                prev_handler(signum, frame)
            except:
                pass

        prev_handler = signal.signal(signal.SIGINT, handler)

        def is_valid(value):
            try:
                return requests.get(value).status_code != 404
            except Exception as ex:
                sys.stderr.write(str(ex) + '\n\n')
                return False

        try:
            value = ask('gitflow.jenkins.url',
                        'Insert the Jenkins server url: ',
                        set_globally=True, is_valid=is_valid)
        except EOFError:
            raise SystemExit('Operation canceled')

        signal.signal(signal.SIGINT, prev_handler)
        return value

    def _get_deploy_job(self, environ):
        job_name = self.get_deploy_job_name(environ)
        if job_name in self._J:
            return self._J[job_name]
        raise DeployJobNotFoundError(job_name)

    def get_deploy_job_name(self, environ):
        return pick('gitflow.jenkins.deployjobname-' + environ,
                'Jenkins jobs as the deploy job',
                lambda: [(k, k) for k in self._J.keys()])

    def _get_deploy_job_token(self, environ):
        req = 'Insert the security token for Jenkins job {0}: ' \
              .format(self.get_deploy_job_name(environ))
        raw = ask('gitflow.jenkins.deployjobtoken-' + environ, req, secret=True)

    def get_url_for_next_invocation(self, environ):
        prefix = self._get_jenkins_url()
        if prefix[-1] != '/':
            prefix += '/'
        job = self._get_deploy_job(environ)
        job_name = self.get_deploy_job_name(environ)
        build_number = job.get_next_build_number()
        return urlparse.urljoin(prefix, 'job/{0}/{1}/'.format(job_name, build_number))

    @classmethod
    def from_prompt(cls):
        username = None
        password = None
        while username is None or username == '':
            username = raw_input('Jenkins username: ')
        while password is None or password == '':
            password = getpass.getpass('Jenkins password: ')
        return cls(username, password)
