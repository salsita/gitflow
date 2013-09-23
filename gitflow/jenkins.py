import ConfigParser
import jenkinsapi.jenkins
import getpass
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

    def trigger_deploy_job(self, branch, environment, cause=None):
        params = {'branch': branch, 'environment': environment}
        return self._get_deploy_job().invoke(
                securitytoken=self._get_deploy_job_token(),
                build_params=params, cause=cause)

    def _get_jenkins_url(self):
        return ask('gitflow.jenkins.url',
                'Insert the Jenkins server url: ', set_globally=True)

    def _get_deploy_job(self):
        job_name = self.get_deploy_job_name()
        if job_name in self._J:
            return self._J[job_name]
        raise DeployJobNotFoundError(job_name)

    def get_deploy_job_name(self):
        return pick('gitflow.jenkins.deployjobname',
                'Jenkins jobs as the deploy job',
                lambda: [(k, k) for k in self._J.keys()])

    def _get_deploy_job_token(self):
        req = 'Insert the security token for Jenkins job {0}: ' \
              .format(self.get_deploy_job_name())
        raw = ask('gitflow.jenkins.deployjobtoken', req, secret=True)

    def get_url_for_next_invocation(self):
        prefix = self._get_jenkins_url()
        if prefix[-1] != '/':
            prefix += '/'
        job = self._get_deploy_job()
        job_name = self.get_deploy_job_name()
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
